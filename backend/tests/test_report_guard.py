"""Anti-hallucination guard (FSD RF5 / S8).

The model rewrites, it never analyses. A rewritten section is accepted only when
every `Log_ID` it cites belongs to the evidence of the section, every `INC-`
identifier it names exists in the analysis, and every criticality it asserts
matches the classifier. Anything else falls back to the deterministic text of
that section and records the reason.
"""

from __future__ import annotations

from app.reporting.brief import build_brief
from app.reporting.guard import GuardContext, check, resolve

INCIDENT = "INC-20261023-0820"
VALIDATED = "INC-20261023-0936"
LEVELS = {INCIDENT: "crítico", VALIDATED: "alto"}
ALLOWED = frozenset({"EVT-00057", "EVT-00123"})
FALLBACK = ["Texto determinístico del apartado."]


def context(**overrides: object) -> GuardContext:
    values: dict[str, object] = {
        "known_incident_levels": LEVELS,
        "allowed_log_ids": ALLOWED,
        "single_incident": None,
        "version": "tecnica",
        "section": "explicacion-tecnica",
    }
    values.update(overrides)
    return GuardContext(**values)  # type: ignore[arg-type]


def test_a_completion_citing_an_unknown_log_id_is_rejected_and_falls_back() -> None:
    draft = f"El incidente {INCIDENT} acumula EVT-99999 y mantiene criticidad crítico."

    resolution = resolve(draft, fallback=FALLBACK, context=context())

    assert resolution.guard.accepted is False
    assert resolution.narrative == "deshabilitada_por_error"
    assert resolution.body == FALLBACK
    assert any("EVT-99999" in reason for reason in resolution.guard.reasons)


def test_a_completion_citing_an_existing_log_id_is_accepted() -> None:
    draft = f"El incidente {INCIDENT} se sustenta en EVT-00057 y EVT-00123."

    resolution = resolve(draft, fallback=FALLBACK, context=context())

    assert resolution.guard.accepted is True
    assert resolution.narrative == "aplicada"
    assert resolution.body == [draft]
    assert resolution.guard.reasons == ()
    assert resolution.guard.log_ids == ("EVT-00057", "EVT-00123")


def test_a_log_id_from_another_incident_is_rejected() -> None:
    draft = f"El incidente {INCIDENT} cita EVT-00428, que pertenece a otro incidente."

    resolution = resolve(draft, fallback=FALLBACK, context=context())

    assert resolution.guard.accepted is False
    assert any("EVT-00428" in reason for reason in resolution.guard.reasons)


def test_a_log_id_is_forbidden_in_the_executive_version_even_when_it_exists() -> None:
    draft = f"El incidente {INCIDENT} se sustenta en EVT-00057."

    resolution = resolve(
        draft,
        fallback=FALLBACK,
        context=context(version="ejecutiva", allowed_log_ids=frozenset()),
    )

    assert resolution.guard.accepted is False
    assert any("EVT-00057" in reason for reason in resolution.guard.reasons)


def test_a_completion_naming_an_unknown_incident_is_rejected() -> None:
    draft = "El incidente INC-9999-0000 afecta a las cuentas de administración."

    resolution = resolve(draft, fallback=FALLBACK, context=context())

    assert resolution.guard.accepted is False
    assert any("INC-9999-0000" in reason for reason in resolution.guard.reasons)


def test_the_guard_never_accepts_a_level_that_contradicts_the_classifier() -> None:
    draft = f"El incidente {INCIDENT} tiene criticidad bajo y requiere atención inmediata."

    resolution = resolve(draft, fallback=FALLBACK, context=context())

    assert resolution.guard.accepted is False
    assert resolution.body == FALLBACK
    assert any("bajo" in reason and "crítico" in reason for reason in resolution.guard.reasons)


def test_the_guard_accepts_the_level_the_classifier_assigned() -> None:
    draft = f"El incidente {INCIDENT} tiene criticidad crítico."

    resolution = resolve(draft, fallback=FALLBACK, context=context())

    assert resolution.guard.accepted is True


def test_a_level_assertion_without_an_incident_is_rejected_when_levels_differ() -> None:
    draft = "Todos los incidentes del informe son de criticidad bajo."

    resolution = resolve(draft, fallback=FALLBACK, context=context())

    assert resolution.guard.accepted is False
    assert any("criticidad" in reason for reason in resolution.guard.reasons)


def test_a_level_assertion_without_an_incident_is_accepted_when_all_share_it() -> None:
    draft = "La criticidad es alto en este apartado y no hay otros niveles implicados."

    resolution = resolve(
        draft,
        fallback=FALLBACK,
        context=context(known_incident_levels={VALIDATED: "alto"}),
    )

    assert resolution.guard.accepted is True


def test_several_incidents_sharing_a_level_can_share_one_assertion() -> None:
    draft = f"{INCIDENT} y {VALIDATED} mantienen criticidad alto en este apartado."

    resolution = resolve(
        draft,
        fallback=FALLBACK,
        context=context(known_incident_levels={INCIDENT: "alto", VALIDATED: "alto"}),
    )

    assert resolution.guard.accepted is True


def test_text_without_citations_or_levels_is_accepted() -> None:
    draft = "Se recomienda revisar la configuración de acceso remoto del servidor."

    resolution = resolve(draft, fallback=FALLBACK, context=context())

    assert resolution.guard.accepted is True
    assert resolution.body == [draft]


def test_an_empty_completion_is_rejected() -> None:
    resolution = resolve("   \n  ", fallback=FALLBACK, context=context())

    assert resolution.guard.accepted is False
    assert resolution.body == FALLBACK
    assert resolution.narrative == "deshabilitada_por_error"


def test_the_guard_is_deterministic_for_the_same_input() -> None:
    draft = f"El incidente {INCIDENT} cita EVT-99999 con criticidad bajo."

    first = check(draft, context())
    second = check(draft, context())

    assert first == second


def test_the_brief_cannot_be_used_as_a_source_of_unknown_levels() -> None:
    """Guard contexts are built from the brief, never from the model output."""
    from pathlib import Path

    from app.api.analysis import analyze
    from app.ingest.loader import load_export
    from app.reporting.compose import section_context

    export = Path(__file__).resolve().parents[2] / (
        "SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx"
    )
    brief = build_brief(analyze(load_export(export)))
    ctx = section_context(brief, "ejecutiva", "resumen-ejecutivo")

    assert ctx.allowed_log_ids == frozenset()
    assert set(ctx.known_incident_levels) == {item["id"] for item in brief["incidents"]}
    assert set(ctx.known_incident_levels.values()) == {
        item["level"] for item in brief["incidents"]
    }
