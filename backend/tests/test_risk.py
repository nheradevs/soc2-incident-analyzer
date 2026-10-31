"""Risk classification (FSD RF3): impact × evidence confidence, rule-written Spanish.

The matrix is exercised against the six incidents of the real export. Two
mutation tests rewrite the SIEM `Severity` column in opposite directions and show
that the classification never reads it, and a boundary test pins the rule that a
single evidence row can never support `crítico`.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pandas as pd
import pytest

from app.detection import detect
from app.detection.models import Incident
from app.ingest.loader import load_export
from app.risk import LEVELS, classify

EXPORT = Path(__file__).resolve().parents[2] / "SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx"


@pytest.fixture(scope="module")
def events() -> pd.DataFrame:
    return load_export(EXPORT)


@pytest.fixture(scope="module")
def incidents(events):
    return detect(events)


@pytest.fixture(scope="module")
def assessments(incidents):
    return classify(incidents)


def incident_citing(assessments, log_id: str):
    matches = [incident for incident in assessments if log_id in incident["evidence"]]
    assert len(matches) == 1, f"{log_id} aparece en {len(matches)} incidentes"
    return matches[0]


def every_risk(assessments):
    for incident in assessments:
        yield incident["risk"]
        for finding in incident["findings"]:
            yield finding["risk"]


def raw_finding(incidents, log_id: str, code: str):
    matches = [
        finding
        for incident in incidents
        for finding in incident.findings
        if finding.code == code and log_id in finding.evidence
    ]
    assert len(matches) == 1, f"{code}/{log_id} aparece en {len(matches)} hallazgos"
    return matches[0]


def incident_with(finding) -> Incident:
    """Single-finding incident, to classify a hand-edited finding on its own."""
    return Incident(
        id=f"INC-TEST-{finding.id}",
        title=finding.title,
        findings=(finding,),
        entities=finding.entities,
        categories=(finding.category,),
        event_count=len(finding.evidence),
        first_seen=finding.first_seen,
        last_seen=finding.last_seen,
        evidence=finding.evidence,
        severity_hint=finding.severity_hint,
        requires_validation=finding.requires_validation,
        narrative="",
    )


def test_all_four_levels_are_reachable(assessments) -> None:
    observed = {risk["level"] for risk in every_risk(assessments)}

    assert observed == set(LEVELS)
    assert all(risk["justification"].strip() for risk in every_risk(assessments))


def test_every_level_states_why_it_is_that_level_and_not_the_next(assessments) -> None:
    for risk in every_risk(assessments):
        justification = risk["justification"]

        assert risk["level"] in justification
        assert risk["impact"] in justification
        if risk["level"] == LEVELS[0]:
            assert "nivel máximo" in justification
        else:
            next_level = LEVELS[LEVELS.index(risk["level"]) - 1]
            assert f"No alcanza «{next_level}»" in justification


def test_a_finding_with_a_single_evidence_row_cannot_be_critical(assessments) -> None:
    single_row = [risk for risk in every_risk(assessments) if risk["event_count"] == 1]

    assert single_row, "el export no produjo ningún hallazgo de una sola fila"
    assert all(risk["level"] != LEVELS[0] for risk in single_row)


def test_a_single_row_with_maximum_impact_is_capped_at_high(incidents) -> None:
    finding = raw_finding(incidents, "EVT-00188", "D1d")
    trimmed = dataclasses.replace(finding, event_count=1, evidence=finding.evidence[-1:])
    risk = classify([incident_with(trimmed)])[0]["findings"][0]["risk"]

    assert risk["impact"] == LEVELS[0]
    assert risk["level"] == LEVELS[1]
    assert "una única fila" in risk["justification"]


def test_the_ambiguous_service_account_incident_is_not_critical(assessments) -> None:
    incident = incident_citing(assessments, "EVT-00284")
    risk = incident["risk"]

    assert risk["requires_validation"] is True
    assert risk["level"] != LEVELS[0]
    justification = risk["justification"].lower()
    assert "validación" in justification
    assert "no se presenta como compromiso confirmado" in justification


def test_requires_validation_downgrades_an_otherwise_critical_finding(incidents) -> None:
    finding = raw_finding(incidents, "EVT-00435", "D7")
    confirmed = classify([incident_with(finding)])[0]["findings"][0]["risk"]
    ambiguous = classify([incident_with(dataclasses.replace(finding, requires_validation=True))])
    ambiguous_risk = ambiguous[0]["findings"][0]["risk"]

    assert confirmed["level"] == LEVELS[0]
    assert ambiguous_risk["level"] == LEVELS[1]
    assert "no se presenta como compromiso confirmado" in ambiguous_risk["justification"]


def test_an_informational_siem_severity_still_yields_critical_findings(events, assessments) -> None:
    rewritten = events.assign(Severity="Informational")
    rerun = classify(detect(rewritten))

    assert set(rewritten["Severity"]) == {"Informational"}
    assert "crítico" in {risk["level"] for risk in every_risk(rerun)}
    assert [item["risk"] for item in rerun] == [item["risk"] for item in assessments]


def test_a_high_siem_severity_does_not_inflate_a_low_classification(events, assessments) -> None:
    rewritten = events.assign(Severity="High")
    rerun = classify(detect(rewritten))

    assert set(rewritten["Severity"]) == {"High"}
    assert "bajo" in {risk["level"] for risk in every_risk(rerun)}
    assert [item["risk"] for item in rerun] == [item["risk"] for item in assessments]


def test_the_rdp_kill_chain_incident_is_critical(assessments) -> None:
    incident = incident_citing(assessments, "EVT-00188")
    risk = incident["risk"]

    assert risk["level"] == LEVELS[0]
    assert "compromiso" in risk["justification"].lower()
    assert "nivel máximo" in risk["justification"]


def test_the_proxy_exfiltration_incident_cites_the_measured_byte_count(assessments) -> None:
    incident = incident_citing(assessments, "EVT-00428")
    risk = incident["risk"]

    assert risk["level"] in {LEVELS[0], LEVELS[1]}
    assert "253,3 MB" in risk["justification"]
    assert "22" in risk["justification"]


def test_the_exfiltration_finding_carries_the_measured_byte_count(incidents) -> None:
    finding = raw_finding(incidents, "EVT-00435", "D7")

    assert finding.measured_bytes == 253_305_558
    assert finding.to_dict()["measured_bytes"] == 253_305_558


def test_the_exfiltration_level_does_not_depend_on_the_rationale_wording(incidents) -> None:
    """The level is read from `measured_bytes`; rewording the prose changes nothing."""
    finding = raw_finding(incidents, "EVT-00435", "D7")
    baseline = classify([incident_with(finding)])[0]["findings"][0]["risk"]
    reworded = dataclasses.replace(
        finding, rationale="Redacción completamente distinta, sin ninguna cifra."
    )
    rerun = classify([incident_with(reworded)])[0]["findings"][0]["risk"]

    assert baseline["level"] == LEVELS[0]
    assert rerun == baseline


def test_prose_megabytes_are_never_measured_as_volume(incidents) -> None:
    """A rationale that still says 253,3 MB is not a measurement on its own."""
    finding = raw_finding(incidents, "EVT-00435", "D7")
    prose_only = dataclasses.replace(finding, measured_bytes=None)
    risk = classify([incident_with(prose_only)])[0]["findings"][0]["risk"]

    assert "253,3 MB" in prose_only.rationale
    assert risk["impact"] == LEVELS[1]
    assert risk["level"] != LEVELS[0]


def test_the_web_shell_incident_is_critical(assessments) -> None:
    incident = incident_citing(assessments, "EVT-00599")
    governing = next(
        finding
        for finding in incident["findings"]
        if finding["id"].startswith("D4:iis-apppool")
    )

    assert governing["risk"]["level"] == LEVELS[0]
    assert incident["risk"]["level"] == LEVELS[0]
    assert len(governing["evidence"]) >= 2
    assert "EVT-00571" in governing["evidence"]


def test_the_spray_incident_names_the_external_address_as_the_attack_origin(
    assessments,
) -> None:
    """FSD §4.8: internal addresses are observed assets, never attacker origin."""
    incident = incident_citing(assessments, "EVT-00057")
    justification = incident["risk"]["justification"]
    internal_ips = ("10.10.1.22", "10.10.1.31", "10.10.1.44", "10.10.2.15")

    assert "IP externa como origen del ataque (203.0.113.74)" in justification
    origin_part, _, internal_part = justification.partition(
        "IPs internas observadas en la evidencia, no orígenes del ataque"
    )
    for internal_ip in internal_ips:
        assert internal_ip not in origin_part
        assert internal_ip in internal_part


def test_every_incident_and_finding_gets_a_level_and_a_justification(assessments) -> None:
    assert assessments, "no hay incidentes clasificados"

    for incident in assessments:
        assert incident["risk"]["level"] in LEVELS
        assert incident["risk"]["justification"].strip()
        assert incident["findings"]
        for finding in incident["findings"]:
            assert finding["risk"]["level"] in LEVELS
            assert finding["risk"]["justification"].strip()
            assert finding["risk"]["justification"].strip() != incident["risk"]["justification"]


def test_the_classification_is_plain_json_serialisable_dicts(assessments) -> None:
    payload = json.dumps(assessments)

    assert json.loads(payload)[0]["risk"]["level"] in LEVELS


def test_the_classification_is_deterministic_and_keeps_the_incident_order(incidents) -> None:
    first = classify(incidents)
    second = classify(incidents)

    assert first == second
    assert [item["id"] for item in first] == [incident.id for incident in incidents]
