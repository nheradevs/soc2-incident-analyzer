"""Structured brief: the only material assisted writing may use (FSD RF5 / S8).

`build_brief` copies the already-decided facts of the analysis (incident level
and rule-written justification, each finding with its code, Spanish title,
entity counts, evidence `Log_ID`s and the quantity its detector measured) into
one JSON-serialisable object. The model is given this object plus the
deterministic draft; it never receives the export and never chooses a finding,
a level or a count.

`prompt_text` renders the same facts as a compact Spanish list for the prompt.
It is derived only from the brief, so the prompt cannot leak a fact the report
guard has not seen.
"""

from __future__ import annotations

from typing import Any

from app.api.analysis import Analysis
from app.detection.context import count_es, minutes_between
from app.detection.exfiltration import megabytes
from app.detection.models import CATEGORY_LABEL_ES
from app.ingest.normalize import ip_class

# The export does not declare account type (FSD §7.4, limitation 8); a name that
# follows the service convention is reported as a *possibility*, never as a fact.
SERVICE_NAME_MARKERS = ("svc",)


def date_of(iso: str | None) -> str:
    """2026-10-23T07:46:07 → 23/10/2026."""
    return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}" if iso else ""


def clock_of(iso: str | None) -> str:
    """2026-10-23T07:46:07 → 07:46:07."""
    return iso[11:19] if iso else ""


def _service_name_accounts(users: list[str]) -> list[str]:
    return sorted(
        user
        for user in users
        if any(marker in user.lower() for marker in SERVICE_NAME_MARKERS)
    )


def _finding_brief(finding: dict[str, Any]) -> dict[str, Any]:
    risk = finding["risk"]
    measured = finding.get("measured_bytes")
    return {
        "id": finding["id"],
        "code": finding["code"],
        "title": finding["title"],
        "category": finding["category"],
        "category_label": CATEGORY_LABEL_ES.get(finding["category"], finding["category"]),
        "event_count": finding["event_count"],
        "first_seen": finding["first_seen"],
        "last_seen": finding["last_seen"],
        "start": clock_of(finding["first_seen"]),
        "end": clock_of(finding["last_seen"]),
        "evidence": list(finding["evidence"]),
        "level": risk["level"],
        "level_key": risk["level_key"],
        "impact": risk["impact"],
        "confidence": risk["confidence"],
        "requires_validation": bool(risk["requires_validation"]),
        "measured_bytes": measured,
        "measured_label": megabytes(measured) if measured is not None else None,
        "rationale": finding["rationale"],
        "justification": risk["justification"],
        "entities": dict(finding["entities"]),
    }


def _incident_brief(incident: dict[str, Any]) -> dict[str, Any]:
    risk = incident["risk"]
    entities = incident["entities"]
    sources = entities["source_ips"]
    return {
        "id": incident["id"],
        "title": incident["title"],
        "level": risk["level"],
        "level_key": risk["level_key"],
        "impact": risk["impact"],
        "confidence": risk["confidence"],
        "requires_validation": bool(risk["requires_validation"]),
        "justification": risk["justification"],
        "narrative": incident["narrative"],
        "categories": list(incident["categories"]),
        "categories_labels": list(incident["categories_labels"]),
        "event_count": incident["event_count"],
        "first_seen": incident["first_seen"],
        "last_seen": incident["last_seen"],
        "date": date_of(incident["first_seen"]),
        "start": clock_of(incident["first_seen"]),
        "end": clock_of(incident["last_seen"]),
        "duration_minutes": minutes_between(incident["first_seen"], incident["last_seen"]),
        "entities": dict(entities),
        "external_sources": sorted(
            source for source in sources if ip_class(source) == "external"
        ),
        "internal_sources": sorted(
            source for source in sources if ip_class(source) != "external"
        ),
        "evidence": list(incident["evidence"]),
        "findings": [_finding_brief(finding) for finding in incident["findings"]],
    }


def build_brief(analysis: Analysis) -> dict[str, Any]:
    """Turn the classified analysis into the closed set of report facts."""
    dashboard = analysis.dashboard
    coverage = dashboard["coverage"]
    window = coverage["time_window"]
    risk = dashboard["risk"]
    categories = coverage["categories"]
    incidents = [
        _incident_brief(analysis.incidents[summary["id"]])
        for summary in dashboard["incidents"]
    ]

    scope = {
        "events_analysed": coverage["events_analysed"],
        "incidents": coverage["incidents"],
        "findings": coverage["findings"],
        "first_seen": window["start"],
        "last_seen": window["end"],
        "date": date_of(window["start"]),
        "start": clock_of(window["start"]),
        "end": clock_of(window["end"]),
        "duration_minutes": window["duration_minutes"],
        "levels": [dict(level) for level in risk["levels"]],
        "categories": [dict(category) for category in categories],
        "categories_covered": [
            category["category"] for category in categories if category["findings"]
        ],
        "categories_covered_labels": [
            category["label"] for category in categories if category["findings"]
        ],
        "categories_uncovered_labels": [
            category["label"] for category in categories if not category["findings"]
        ],
        "users": list(risk["affected"]["users"]),
        "hosts": list(risk["affected"]["hosts"]),
        "external_sources": list(risk["affected"]["external_sources"]),
        "service_name_accounts": _service_name_accounts(risk["affected"]["users"]),
        "incident_ids": [incident["id"] for incident in incidents],
    }
    return {"scope": scope, "incidents": incidents}


def _names(values: list[str], empty: str = "sin datos") -> str:
    return ", ".join(values) if values else empty


def prompt_text(brief: dict[str, Any]) -> str:
    """Render the brief as the Spanish fact sheet the model is allowed to use."""
    scope = brief["scope"]
    lines = [
        "ALCANCE DEL ANÁLISIS",
        f"- Eventos analizados: {count_es(scope['events_analysed'])}",
        f"- Ventana: {scope['first_seen']} → {scope['last_seen']} "
        f"({count_es(scope['duration_minutes'])} minutos) del {scope['date']}",
        f"- Incidentes: {count_es(scope['incidents'])}; "
        f"hallazgos: {count_es(scope['findings'])}",
        "- Distribución por criticidad: "
        + ", ".join(f"{level['level']} {level['incidents']}" for level in scope["levels"]),
        f"- Cuentas afectadas: {_names(scope['users'])}",
        f"- Equipos afectados: {_names(scope['hosts'])}",
        f"- IPs externas de origen: {_names(scope['external_sources'])}",
        "",
        "INCIDENTES",
    ]
    for incident in brief["incidents"]:
        entities = incident["entities"]
        lines.extend(
            [
                f"- {incident['id']} · {incident['title']} · criticidad "
                f"{incident['level']} (impacto {incident['impact']} × confianza "
                f"{incident['confidence']}); requiere validación: "
                f"{'sí' if incident['requires_validation'] else 'no'}",
                f"  Ventana: {incident['start']} → {incident['end']} del "
                f"{incident['date']} ({count_es(incident['duration_minutes'])} min); "
                f"eventos: {count_es(incident['event_count'])}",
                f"  Cuentas: {_names(entities['users'])}; "
                f"equipos: {_names(entities['hosts'])}; "
                f"recursos compartidos: {_names(entities['shares'])}",
                f"  IPs externas: {_names(incident['external_sources'])}; "
                f"IPs internas observadas: {_names(incident['internal_sources'])}",
                f"  Evidencia (Log_ID): {_names(incident['evidence'])}",
            ]
        )
        for finding in incident["findings"]:
            measured = (
                f"; medido: {finding['measured_label']}"
                if finding["measured_label"]
                else ""
            )
            lines.append(
                f"  - {finding['code']} · {finding['title']} · "
                f"{count_es(finding['event_count'])} eventos · criticidad "
                f"{finding['level']}{measured} · Log_ID: {_names(finding['evidence'])}"
            )
    return "\n".join(lines)
