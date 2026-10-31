"""Findings and incidents produced by the deterministic detection engine (FSD RF2).

A finding is *one* rule firing on a concrete group of log rows; an incident is a
set of findings that share a normalized entity inside the 30-minute window. Both
carry the `Log_ID` of every row that supports them, so nothing downstream has to
re-derive evidence.

`severity_hint` is a proposal built from the rule that fired, not a risk
classification: the risk matrix (FSD RF3) decides the final level and does not
read the SIEM `Severity` column.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

# The six categories required by the client requirement (S2).
CATEGORIES = (
    "brute-force",
    "suspicious-logon",
    "privilege-escalation",
    "command-execution",
    "lateral-movement",
    "other-anomaly",
)

CATEGORY_LABEL_ES = {
    "brute-force": "fuerza bruta",
    "suspicious-logon": "inicio de sesión sospechoso",
    "privilege-escalation": "escalamiento de privilegios",
    "command-execution": "ejecución de comandos",
    "lateral-movement": "movimiento lateral",
    "other-anomaly": "otra anomalía",
}

SEVERITY_LEVELS = ("low", "medium", "high", "critical")

SEVERITY_LABEL_ES = {
    "low": "bajo",
    "medium": "medio",
    "high": "alto",
    "critical": "crítico",
}


@dataclass(frozen=True, slots=True)
class Entities:
    """Normalized, comparable entities of a finding (FSD §4, traps 4.4-4.8)."""

    users: tuple[str, ...] = ()
    hosts: tuple[str, ...] = ()
    source_ips: tuple[str, ...] = ()
    shares: tuple[str, ...] = ()

    def keys(self) -> set[str]:
        """Namespaced keys: a user and a host with the same name never merge."""
        return (
            {f"user:{value}" for value in self.users}
            | {f"host:{value}" for value in self.hosts}
            | {f"ip:{value}" for value in self.source_ips}
            | {f"share:{value}" for value in self.shares}
        )

    def as_dict(self) -> dict[str, list[str]]:
        return {
            "users": list(self.users),
            "hosts": list(self.hosts),
            "source_ips": list(self.source_ips),
            "shares": list(self.shares),
        }


def merge_entities(groups: list[Entities]) -> Entities:
    users: set[str] = set()
    hosts: set[str] = set()
    source_ips: set[str] = set()
    shares: set[str] = set()
    for group in groups:
        users.update(group.users)
        hosts.update(group.hosts)
        source_ips.update(group.source_ips)
        shares.update(group.shares)
    return Entities(
        users=tuple(sorted(users)),
        hosts=tuple(sorted(hosts)),
        source_ips=tuple(sorted(source_ips)),
        shares=tuple(sorted(shares)),
    )


def strongest_hint(hints: list[str]) -> str:
    return max(hints, key=SEVERITY_LEVELS.index, default="low")


@dataclass(frozen=True, slots=True)
class Finding:
    """One detection rule applied to one group of log rows."""

    id: str
    code: str
    category: str
    title: str
    entities: Entities
    event_count: int
    first_seen: datetime
    last_seen: datetime
    evidence: tuple[str, ...]
    severity_hint: str
    requires_validation: bool
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "code": self.code,
            "category": self.category,
            "title": self.title,
            "entities": self.entities.as_dict(),
            "event_count": self.event_count,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "evidence": list(self.evidence),
            "severity_hint": self.severity_hint,
            "requires_validation": self.requires_validation,
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class Incident:
    """Findings correlated by shared entity and a window of at most 30 minutes."""

    id: str
    title: str
    findings: tuple[Finding, ...]
    entities: Entities
    categories: tuple[str, ...]
    event_count: int
    first_seen: datetime
    last_seen: datetime
    evidence: tuple[str, ...]
    severity_hint: str
    requires_validation: bool
    narrative: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "findings": [finding.to_dict() for finding in self.findings],
            "entities": self.entities.as_dict(),
            "categories": list(self.categories),
            "event_count": self.event_count,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "evidence": list(self.evidence),
            "severity_hint": self.severity_hint,
            "requires_validation": self.requires_validation,
            "narrative": self.narrative,
        }
