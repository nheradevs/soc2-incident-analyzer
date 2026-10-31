"""Correlation of findings into incidents (FSD RF2).

Two findings belong to the same incident when they share at least one account
(`user_norm`) or one source IP **and** the incident window they would form stays
inside 30 minutes. The host is never a correlation key on its own: on a file
server several legitimate users touch the same machine inside half an hour, so
host overlap alone is not evidence of one intrusion.

Findings are never chained transitively: a chain that would span more than 30
minutes starts a new incident, because the whole export is only 5 h 58 min long
and a week-long "incident" would say nothing.

Incident ids are derived from the moment they start (`INC-20261023-0820`), never
from a position in a list: the `INC-1` … `INC-6` labels of FSD §8 are editorial
references verified by evidence, and re-using them at runtime would point at
different incidents.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.detection.context import count_es, hhmmss, minutes_between
from app.detection.models import (
    CATEGORIES,
    CATEGORY_LABEL_ES,
    Entities,
    Finding,
    Incident,
    merge_entities,
    strongest_hint,
)

CORRELATION_WINDOW = pd.Timedelta(minutes=30)


@dataclass
class _Cluster:
    findings: list[Finding] = field(default_factory=list)
    keys: set[str] = field(default_factory=set)
    first_seen: pd.Timestamp | None = None
    last_seen: pd.Timestamp | None = None


def match_keys(entities: Entities) -> set[str]:
    """The entities two findings may be correlated through.

    Accounts and source IPs only: a shared host (or share) is context, not
evidence that the same actor did both things.
    """
    return {f"user:{value}" for value in entities.users} | {
        f"ip:{value}" for value in entities.source_ips
    }


def _categories_of(findings: list[Finding]) -> tuple[str, ...]:
    observed = {finding.category for finding in findings}
    ordered = [category for category in CATEGORIES if category in observed]
    return tuple(ordered)


def _narrative(
    findings: list[Finding],
    categories: tuple[str, ...],
    entities: Entities,
    first_seen: pd.Timestamp,
    last_seen: pd.Timestamp,
    event_count: int,
    requires_validation: bool,
) -> str:
    codes: dict[str, list[str]] = {category: [] for category in categories}
    for finding in findings:
        if finding.code not in codes[finding.category]:
            codes[finding.category].append(finding.code)

    chain = " → ".join(
        f"{CATEGORY_LABEL_ES[category]} ({', '.join(codes[category])})" for category in categories
    )
    parts = [f"Secuencia observada: {chain}."]
    parts.append(
        f"{count_es(event_count)} eventos distintos entre {hhmmss(first_seen)} y "
        f"{hhmmss(last_seen)} ({minutes_between(first_seen, last_seen)} min) del "
        f"{first_seen:%d/%m/%Y}, en {count_es(len(findings))} hallazgo(s) correlacionados."
    )
    if entities.users:
        parts.append(f"Cuentas involucradas: {', '.join(entities.users)}.")
    if entities.hosts:
        parts.append(f"Equipos involucrados: {', '.join(entities.hosts)}.")
    if entities.source_ips:
        parts.append(f"Direcciones IP de origen observadas: {', '.join(entities.source_ips)}.")
    if entities.shares:
        parts.append(f"Recursos compartidos: {', '.join(entities.shares)}.")
    if requires_validation:
        parts.append(
            "Parte del comportamiento también es compatible con actividad administrativa o de "
            "respaldo: requiere validación humana antes de concluir un compromiso."
        )
    parts.append(
        "La narrativa se limita a lo que los registros muestran; la ausencia de un evento no "
        "prueba que no haya ocurrido."
    )
    return " ".join(parts)


def _build(cluster: _Cluster) -> Incident:
    findings = sorted(cluster.findings, key=lambda finding: (finding.first_seen, finding.id))
    entities = merge_entities([finding.entities for finding in findings])
    categories = _categories_of(findings)
    evidence = tuple(
        dict.fromkeys(log_id for finding in findings for log_id in finding.evidence)
    )
    first_seen = min(finding.first_seen for finding in findings)
    last_seen = max(finding.last_seen for finding in findings)
    requires_validation = any(finding.requires_validation for finding in findings)
    title = " → ".join(CATEGORY_LABEL_ES[category] for category in categories)

    return Incident(
        id=f"INC-{first_seen:%Y%m%d-%H%M}",
        title=title[:1].upper() + title[1:],
        findings=tuple(findings),
        entities=entities,
        categories=categories,
        event_count=len(evidence),
        first_seen=first_seen,
        last_seen=last_seen,
        evidence=evidence,
        severity_hint=strongest_hint([finding.severity_hint for finding in findings]),
        requires_validation=requires_validation,
        narrative=_narrative(
            findings,
            categories,
            entities,
            first_seen,
            last_seen,
            len(evidence),
            requires_validation,
        ),
    )


def correlate(findings: list[Finding]) -> list[Incident]:
    """Group findings into incidents, deterministically."""
    ordered = sorted(
        findings, key=lambda finding: (finding.first_seen, finding.last_seen, finding.id)
    )
    clusters: list[_Cluster] = []

    for finding in ordered:
        keys = match_keys(finding.entities)
        best: _Cluster | None = None
        best_score = 0
        for cluster in clusters:
            first_seen = min(cluster.first_seen, finding.first_seen)
            last_seen = max(cluster.last_seen, finding.last_seen)
            if last_seen - first_seen > CORRELATION_WINDOW:
                continue
            shared = len(cluster.keys & keys)
            if shared > best_score:
                best, best_score = cluster, shared
        if best is None:
            clusters.append(
                _Cluster(
                    findings=[finding],
                    keys=set(keys),
                    first_seen=finding.first_seen,
                    last_seen=finding.last_seen,
                )
            )
            continue
        best.findings.append(finding)
        best.keys |= keys
        best.first_seen = min(best.first_seen, finding.first_seen)
        best.last_seen = max(best.last_seen, finding.last_seen)

    clusters.sort(
        key=lambda cluster: (cluster.first_seen, min(item.id for item in cluster.findings))
    )
    return [_build(cluster) for cluster in clusters]
