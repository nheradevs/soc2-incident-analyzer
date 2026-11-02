"""Report composition: deterministic report plus optional assisted rewriting.

`compose_report` always renders the nine sections of both versions from the
brief. When an OpenAI-compatible provider is configured, the narrative sections
(sections 1, 6 and 7) are rewritten from the brief and verified by the guard;
everything else (evidence lists, the rule-written justification and the
mandatory limitations) stays exactly as the rules produced it.

An unavailable provider is never a failure of the report: the payload states
whether assisted writing is `no_configurada`, `deshabilitada_por_error` or
`aplicada`, and the report keeps its full content in all three cases.
"""

from __future__ import annotations

from typing import Any

from app.reporting.brief import prompt_text
from app.reporting.guard import GuardContext, resolve
from app.reporting.narrative import (
    NARRATIVE_APPLIED,
    NARRATIVE_DISABLED_BY_ERROR,
    NARRATIVE_NOT_CONFIGURED,
    NARRATIVE_PARTIAL,
    NOT_CONFIGURED_REASON,
    NarrativeClient,
)
from app.reporting.templates import VERSION_LABEL_ES, VERSIONS, render_sections

# Sections whose wording is prose about the analysis. The rest are lists or
# mandatory rule-written statements and never pass through the model.
NARRATIVE_SECTIONS: tuple[str, ...] = (
    "resumen-ejecutivo",
    "impacto-organizacion",
    "plan-de-accion",
)

INSTRUCTIONS: dict[str, dict[str, str]] = {
    "resumen-ejecutivo": {
        "ejecutiva": (
            "Reescribe el resumen ejecutivo para una audiencia directiva: lenguaje de "
            "negocio, sin identificadores de evento ni Log_ID, conservando todas las "
            "cifras, la ventana temporal y los incidentes del borrador."
        ),
        "tecnica": (
            "Reescribe el resumen ejecutivo para un analista de seguridad: conserva todas "
            "las cifras, la ventana temporal y la distribución por criticidad del "
            "borrador. Puedes citar un Log_ID solo si aparece en los hechos."
        ),
    },
    "impacto-organizacion": {
        "ejecutiva": (
            "Reescribe el impacto organizacional en lenguaje claro para la dirección, "
            "manteniendo la criticidad de cada incidente y la advertencia de validación "
            "cuando exista."
        ),
        "tecnica": (
            "Reescribe el impacto organizacional conservando la criticidad de cada "
            "incidente, el alcance observado y la advertencia de validación cuando exista."
        ),
    },
    "plan-de-accion": {
        "ejecutiva": (
            "Reescribe el plan de acción en lenguaje claro, conservando las tres fases "
            "(Investigar, Contener, Remediar) y una entrada por incidente."
        ),
        "tecnica": (
            "Reescribe el plan de acción conservando las tres fases (Investigar, "
            "Contener, Remediar), el orden de las acciones y una entrada por incidente."
        ),
    },
}

NOT_CONFIGURED_NOTE = (
    "Nota: la redacción asistida por IA no está configurada en esta instalación; el "
    "informe completo se genera con el motor de reglas a partir de los datos analizados."
)
NOT_APPLIED_NOTE = (
    "Nota: la redacción asistida por IA no se aplicó en todas las secciones; las que no "
    "la reciben conservan la redacción determinística."
)
PARTIAL_REASON = "Una o más secciones conservan la redacción determinística."


def section_context(brief: dict[str, Any], version: str, section_key: str) -> GuardContext:
    """Allowed citations and real levels for one section of one version."""
    levels = {incident["id"]: incident["level"] for incident in brief["incidents"]}
    if version == "ejecutiva":
        allowed = frozenset()
    else:
        allowed = frozenset(
            log_id
            for incident in brief["incidents"]
            for log_id in incident["evidence"]
        )
    return GuardContext(
        known_incident_levels=levels,
        allowed_log_ids=allowed,
        single_incident=None,
        version=version,
        section=section_key,
    )


def _combined_state(states: list[str], enabled: bool) -> str:
    if not enabled or not states:
        return NARRATIVE_NOT_CONFIGURED
    if all(state == NARRATIVE_APPLIED for state in states):
        return NARRATIVE_APPLIED
    if any(state == NARRATIVE_APPLIED for state in states):
        return NARRATIVE_PARTIAL
    return NARRATIVE_DISABLED_BY_ERROR


def _motivo(state: str) -> str | None:
    if state == NARRATIVE_NOT_CONFIGURED:
        return NOT_CONFIGURED_REASON
    if state == NARRATIVE_APPLIED:
        return None
    return PARTIAL_REASON


def _assisted_note(state: str) -> str:
    return NOT_CONFIGURED_NOTE if state == NARRATIVE_NOT_CONFIGURED else NOT_APPLIED_NOTE


def _render_version(
    brief: dict[str, Any],
    *,
    version: str,
    client: NarrativeClient,
    facts: str,
    accepted: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, int]]:
    sections = render_sections(brief, version)
    states: list[str] = []
    counts = {"requests": 0, "applied": 0, "failed": 0}

    for item in sections:
        if item["key"] not in NARRATIVE_SECTIONS:
            continue
        if not client.enabled:
            item["narrative"] = NARRATIVE_NOT_CONFIGURED
            item["narrative_reason"] = NOT_CONFIGURED_REASON
            states.append(NARRATIVE_NOT_CONFIGURED)
            continue

        counts["requests"] += 1
        narrative = client.rewrite(
            instruction=INSTRUCTIONS[item["key"]][version],
            source="\n".join(item["body"]),
            facts=facts,
        )
        if narrative.status != NARRATIVE_APPLIED:
            item["narrative"] = NARRATIVE_DISABLED_BY_ERROR
            item["narrative_reason"] = narrative.reason
            counts["failed"] += 1
            states.append(NARRATIVE_DISABLED_BY_ERROR)
            continue

        resolution = resolve(
            narrative.text,
            fallback=list(item["body"]),
            context=section_context(brief, version, item["key"]),
        )
        item["body"] = resolution.body
        item["narrative"] = resolution.narrative
        if resolution.guard.accepted:
            counts["applied"] += 1
            item["narrative_reason"] = None
            states.append(NARRATIVE_APPLIED)
            accepted.append({"version": version, "section": item["key"]})
        else:
            counts["failed"] += 1
            item["narrative_reason"] = (
                "Se descartó la redacción propuesta: " + " ".join(resolution.guard.reasons)
            )
            states.append(NARRATIVE_DISABLED_BY_ERROR)
            rejected.append(
                {
                    "version": version,
                    "section": item["key"],
                    "reasons": list(resolution.guard.reasons),
                }
            )

    state = _combined_state(states, client.enabled)
    if state != NARRATIVE_APPLIED:
        notes = next(
            item for item in sections if item["key"] == "recomendaciones-generales"
        )
        notes["body"] = [*notes["body"], _assisted_note(state)]

    payload = {
        "key": version,
        "label": VERSION_LABEL_ES[version],
        "narrative_status": state,
        "sections": sections,
    }
    return payload, counts


def compose_report(brief: dict[str, Any], *, client: NarrativeClient) -> dict[str, Any]:
    """Build the JSON-serialisable report of both versions for one analysis."""
    facts = prompt_text(brief)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    versions: dict[str, Any] = {}
    states: list[str] = []
    requests = applied = failed = 0

    for version in VERSIONS:
        payload, counts = _render_version(
            brief,
            version=version,
            client=client,
            facts=facts,
            accepted=accepted,
            rejected=rejected,
        )
        versions[version] = payload
        states.append(payload["narrative_status"])
        requests += counts["requests"]
        applied += counts["applied"]
        failed += counts["failed"]

    state = _combined_state(states, client.enabled)
    return {
        "narrative": {
            **client.describe(),
            "estado": state,
            "motivo": _motivo(state),
            "solicitudes": requests,
            "secciones_aplicadas": applied,
            "secciones_con_error": failed,
        },
        "guard": {
            "aceptadas": accepted,
            "rechazadas": rejected,
            "secciones_aceptadas": applied,
            "secciones_rechazadas": len(rejected),
        },
        "scope": brief["scope"],
        "versions": versions,
    }
