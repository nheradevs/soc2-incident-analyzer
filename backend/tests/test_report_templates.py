"""Deterministic report templates (FSD RF5 / S5).

The report has two Spanish versions with the same nine mandatory sections
(FSD §7.4 adds `Limitaciones` to the eight of the client requirement). These
tests pin the structure, that every number is computed from the real export,
that only the technical version cites `Log_ID`s, and that the deterministic
path is byte-stable across runs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from app.api.analysis import analyze
from app.config import Settings
from app.ingest.loader import load_export
from app.reporting.brief import build_brief
from app.reporting.compose import compose_report
from app.reporting.narrative import NarrativeClient
from app.reporting.templates import (
    SECTION_KEYS,
    SECTION_TITLES,
    VERSIONS,
    render_sections,
)

EXPORT = Path(__file__).resolve().parents[2] / "SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx"
LOG_ID = re.compile(r"EVT-[0-9]+")


@pytest.fixture(scope="module")
def brief() -> dict[str, Any]:
    return build_brief(analyze(load_export(EXPORT)))


def section(sections: list[dict[str, Any]], key: str) -> dict[str, Any]:
    return next(item for item in sections if item["key"] == key)


def text_of(sections: list[dict[str, Any]], key: str) -> str:
    return "\n".join(section(sections, key)["body"])


def all_text(sections: list[dict[str, Any]]) -> str:
    return "\n".join(paragraph for item in sections for paragraph in item["body"])


def test_both_versions_render_the_nine_mandatory_sections_in_order(
    brief: dict[str, Any],
) -> None:
    for version in VERSIONS:
        sections = render_sections(brief, version)

        assert [item["number"] for item in sections] == list(range(1, 10))
        assert [item["key"] for item in sections] == list(SECTION_KEYS)
        assert [item["title"] for item in sections] == [
            f"{number}. {title}"
            for number, title in enumerate(SECTION_TITLES, start=1)
        ]
        assert all(item["body"] for item in sections)
        assert all(paragraph.strip() for item in sections for paragraph in item["body"])


def test_section_titles_are_the_eight_of_the_requirement_plus_limitations() -> None:
    assert SECTION_TITLES == (
        "Resumen ejecutivo",
        "Hallazgos identificados",
        "Explicación técnica de cada hallazgo",
        "Evidencias encontradas en los logs",
        "Criticidad y justificación",
        "Posible impacto en la organización",
        "Plan de acción: investigar → contener → remediar",
        "Recomendaciones generales de seguridad",
        "Limitaciones del análisis",
    )
    assert VERSIONS == ("ejecutiva", "tecnica")


def test_technical_summary_uses_the_measured_numbers_of_the_export(
    brief: dict[str, Any],
) -> None:
    text = text_of(render_sections(brief, "tecnica"), "resumen-ejecutivo")

    assert "715" in text
    assert "46" in text
    assert "6 incidentes" in text
    assert "Distribución por criticidad: crítico 4, alto 2, medio 0, bajo 0." in text
    assert "07:46:07" in text
    assert "13:44:06" in text
    assert "5 h 58 min" in text
    assert "23/10/2026" in text


def test_executive_summary_states_the_same_numbers_in_business_language(
    brief: dict[str, Any],
) -> None:
    text = text_of(render_sections(brief, "ejecutiva"), "resumen-ejecutivo")

    assert "715" in text
    assert "6 incidentes" in text
    assert "4 críticos y 2 altos" in text
    assert "07:46:07" in text
    assert "13:44:06" in text


def test_every_incident_appears_in_the_findings_section_of_both_versions(
    brief: dict[str, Any],
) -> None:
    titles = [incident["title"] for incident in brief["incidents"]]
    assert len(titles) == 6

    for version in VERSIONS:
        text = text_of(render_sections(brief, version), "hallazgos-identificados")
        for title in titles:
            assert title in text


def test_technical_version_explains_each_finding_with_its_log_ids(
    brief: dict[str, Any],
) -> None:
    sections = render_sections(brief, "tecnica")
    text = text_of(sections, "explicacion-tecnica")
    known = {log_id for incident in brief["incidents"] for log_id in incident["evidence"]}

    cited = set(LOG_ID.findall(text))
    assert len(cited) > 20
    assert cited <= known
    assert "D1b" in text
    assert "EVT-00057" in text


def test_technical_evidence_section_cites_every_evidence_row(
    brief: dict[str, Any],
) -> None:
    text = text_of(render_sections(brief, "tecnica"), "evidencias-logs")
    known = {log_id for incident in brief["incidents"] for log_id in incident["evidence"]}
    expected_total = sum(len(incident["evidence"]) for incident in brief["incidents"])

    cited = LOG_ID.findall(text)
    assert len(cited) == expected_total == 110
    assert set(cited) == known


def test_executive_version_never_spams_log_ids(brief: dict[str, Any]) -> None:
    text = all_text(render_sections(brief, "ejecutiva"))

    assert LOG_ID.findall(text) == []
    assert "No se incluyen identificadores técnicos" in text


def test_technical_criticality_section_repeats_the_classifier_justification(
    brief: dict[str, Any],
) -> None:
    text = text_of(render_sections(brief, "tecnica"), "criticidad-justificacion")

    for incident in brief["incidents"]:
        assert incident["level"] in text
        assert incident["justification"][:60] in text


def test_executive_criticality_section_states_the_matrix_factors(
    brief: dict[str, Any],
) -> None:
    text = text_of(render_sections(brief, "ejecutiva"), "criticidad-justificacion")

    assert "impacto potencial" in text
    for incident in brief["incidents"]:
        assert incident["level"] in text


def test_impact_section_states_the_observed_scope_and_the_validation_caveat(
    brief: dict[str, Any],
) -> None:
    text = text_of(render_sections(brief, "tecnica"), "impacto-organizacion")
    validated = [incident for incident in brief["incidents"] if incident["requires_validation"]]

    assert "impacto posible" in text
    assert validated, "the real export has one ambiguous incident (FSD §8, INC-6)"
    for incident in validated:
        assert incident["id"] in text
    assert "validación" in text


def test_action_plan_has_the_three_phases_for_every_incident(
    brief: dict[str, Any],
) -> None:
    text = text_of(render_sections(brief, "tecnica"), "plan-de-accion")

    assert text.count("Investigar:") == 6
    assert text.count("Contener:") == 6
    assert text.count("Remediar:") == 6
    for incident in brief["incidents"]:
        assert incident["id"] in text


def test_recommendations_are_derived_from_the_categories_that_fired(
    brief: dict[str, Any],
) -> None:
    text = text_of(render_sections(brief, "tecnica"), "recomendaciones-generales")

    assert text.count("• ") >= 6
    assert "multifactor" in text
    assert "tipo de cuenta" in text
    assert "C:\\ProgramData" in text


def test_limitations_section_lists_the_eight_documented_limitations(
    brief: dict[str, Any],
) -> None:
    body = section(render_sections(brief, "tecnica"), "limitaciones-analisis")["body"]

    assert len(body) == 8
    assert [paragraph.split(".", 1)[0] for paragraph in body] == [
        str(number) for number in range(1, 9)
    ]
    text = "\n".join(body)
    assert "5 h 58 min" in text
    assert "RFC 5737" in text
    assert "Severity" in text
    assert "tipo de cuenta" in text
    assert "backupsvc" in text


def test_report_bodies_contain_no_placeholders(brief: dict[str, Any]) -> None:
    for version in VERSIONS:
        text = all_text(render_sections(brief, version))
        assert "{" not in text
        assert "}" not in text
        assert "TODO" not in text
        assert "None" not in text


def test_composed_report_without_a_key_keeps_every_section(brief: dict[str, Any]) -> None:
    client = NarrativeClient(Settings(nan_api_key=""))

    body = compose_report(brief, client=client)

    assert body["narrative"]["estado"] == "no_configurada"
    for version in body["versions"].values():
        assert version["narrative_status"] == "no_configurada"
        assert len(version["sections"]) == 9
        assert all(item["body"] for item in version["sections"])
        assert all(
            item["narrative"] in {"no_configurada", "plantilla"}
            for item in version["sections"]
        )


def test_rendering_the_same_brief_twice_is_byte_stable(brief: dict[str, Any]) -> None:
    first = render_sections(brief, "tecnica")
    second = render_sections(brief, "tecnica")

    assert first == second
    assert json.dumps(first, ensure_ascii=False) == json.dumps(second, ensure_ascii=False)


def test_composed_report_is_byte_stable_without_ai(brief: dict[str, Any]) -> None:
    client = NarrativeClient(Settings(nan_api_key=""))

    first = compose_report(brief, client=client)
    second = compose_report(brief, client=client)

    assert first == second
    assert json.dumps(first, ensure_ascii=False) == json.dumps(second, ensure_ascii=False)
