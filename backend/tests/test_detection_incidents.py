"""Regression fixture: the six incidents measured in the real export (FSD §8).

Each incident is located by a `Log_ID` that belongs to it, then the detector
codes and a sample of the expected evidence are asserted. The last tests are
properties of the whole run: no invented evidence, a lone internal `4672` is
not an incident, and two runs of the same frame are identical.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.detection import detect
from app.detection.privilege import d3_privilege_escalation
from app.ingest.loader import load_export

EXPORT = Path(__file__).resolve().parents[2] / "SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx"


@pytest.fixture(scope="module")
def events() -> pd.DataFrame:
    return load_export(EXPORT)


@pytest.fixture(scope="module")
def incidents(events):
    return detect(events)


def incident_citing(incidents, log_id: str):
    matches = [incident for incident in incidents if log_id in incident.evidence]
    assert len(matches) == 1, f"{log_id} aparece en {len(matches)} incidentes"
    return matches[0]


@pytest.fixture(scope="module")
def d3_findings(events):
    return d3_privilege_escalation(events)


def codes_of(incident) -> set[str]:
    return {finding.code for finding in incident.findings}


def test_inc1_password_spray_then_successful_logon_and_privileges(incidents) -> None:
    """INC-1: 33 `4625 bad password` over 8 accounts from 203.0.113.74."""
    incident = incident_citing(incidents, "EVT-00123")

    for log_id in ("EVT-00057", "EVT-00111", "EVT-00123", "EVT-00126"):
        assert log_id in incident.evidence

    assert {"D1a", "D1b", "D1c", "D1d", "D2", "D3"} <= codes_of(incident)
    assert incident.categories[0] == "brute-force"
    assert "privilege-escalation" in incident.categories
    assert incident.requires_validation is False


def test_inc2_kill_chain_over_rdp_is_one_incident(incidents) -> None:
    """INC-2: 198.51.100.77 → APP-SRV01 → FS-SRV01, 09:02 → 09:21."""
    incident = incident_citing(incidents, "EVT-00188")

    for log_id in ("EVT-00188", "EVT-00198", "EVT-00225", "EVT-00235"):
        assert log_id in incident.evidence

    assert {"D1a", "D1c", "D1d", "D2", "D3", "D4", "D5", "D6"} <= codes_of(incident)
    assert "lateral-movement" in incident.categories
    assert {"admin"} <= set(incident.entities.users)
    assert {"APPSRV01", "FSSRV01"} <= set(incident.entities.hosts)


def test_inc3_web_shell_command_execution(incidents) -> None:
    """INC-3: the .aspx web shell returns 200 and the app pool spawns a process."""
    incident = incident_citing(incidents, "EVT-00571")

    assert "EVT-00599" in incident.evidence
    assert "D4" in codes_of(incident)
    assert {"WEB01"} <= set(incident.entities.hosts)


def test_the_web_shell_finding_cites_the_shell_request_that_answered_2xx(
    incidents, events
) -> None:
    """INC-3: the process row alone is a single piece of evidence. The finding must
    also cite the `HTTP_ACCESS` row that proves the shell endpoint answered 2xx."""
    incident = incident_citing(incidents, "EVT-00599")
    governing = next(
        finding for finding in incident.findings if finding.id.startswith("D4:iis-apppool")
    )

    assert "EVT-00571" in governing.evidence
    assert len(governing.evidence) >= 2

    cited = events[events["Log_ID"].astype(str).isin(governing.evidence)]
    web = cited[cited["event_family"] == "web"]
    assert set(web["result_norm"]) == {"http_2xx"}
    assert set(web["host_norm"]) == {"WEB01"}
    assert "/uploads/test.aspx" in " ".join(web["command_norm"].astype(str))
    assert "EVT-00573" not in governing.evidence
    assert "EVT-00574" not in governing.evidence


def test_inc4_staging_archive_and_proxy_exfiltration(incidents) -> None:
    """INC-4: 7z staging on WS-018 then 22 HTTPS POST to 198.51.100.88."""
    incident = incident_citing(incidents, "EVT-00428")

    for log_id in ("EVT-00435", "EVT-00460"):
        assert log_id in incident.evidence

    assert {"D4", "D7"} <= codes_of(incident)
    exfiltration = next(finding for finding in incident.findings if finding.code == "D7")
    assert exfiltration.event_count == 22
    assert "198.51.100.88" in exfiltration.rationale
    assert exfiltration.measured_bytes == 253_305_558
    assert "measured_bytes" in exfiltration.to_dict()
    assert {"WS018"} <= set(incident.entities.hosts)
    assert {"rrojas"} <= set(incident.entities.users)


def test_inc5_persistence_with_masquerading(incidents) -> None:
    """INC-5: scheduled task and service installed outside the maintenance window."""
    incident = incident_citing(incidents, "EVT-00523")

    for log_id in ("EVT-00524", "EVT-00564"):
        assert log_id in incident.evidence

    assert {"D4", "D6"} <= codes_of(incident)
    assert {"helpdesk"} <= set(incident.entities.users)


def test_inc6_service_account_case_is_reported_as_requiring_validation(incidents) -> None:
    """INC-6: ambiguous by design (FSD §8). The logs show shadow copies being
    deleted; they do not show encryption, so ransomware must not be claimed."""
    incident = incident_citing(incidents, "EVT-00284")

    for log_id in ("EVT-00280", "EVT-00309", "EVT-00314"):
        assert log_id in incident.evidence

    assert {"D4", "D6"} <= codes_of(incident)
    assert incident.requires_validation is True
    bulk_read = next(
        finding
        for finding in incident.findings
        if finding.code == "D6" and finding.requires_validation
    )
    assert bulk_read.requires_validation is True
    assert "validación" in incident.narrative.lower()
    assert "ransomware" not in incident.narrative.lower()


def test_inc1_spray_incident_keeps_all_of_its_detectors(incidents) -> None:
    """INC-1: the spray cluster is found by D1a/D1b/D1c/D1d/D2/D3 and cites the
    successful logon and the privileged logon that follow the spray."""
    incident = incident_citing(incidents, "EVT-00057")

    assert {"D1a", "D1b", "D1c", "D1d", "D2", "D3"} <= codes_of(incident)
    for log_id in ("EVT-00111", "EVT-00123", "EVT-00126"):
        assert log_id in incident.evidence


def test_inc2_does_not_absorb_unrelated_internal_privilege_activity(incidents) -> None:
    """The `mruiz` 4672 is one baseline failure followed by a normal logon on a
    shared file server: it is neither an escalation nor part of the RDP attack."""
    incident = incident_citing(incidents, "EVT-00188")

    assert "mruiz" not in incident.entities.users
    assert "10.10.1.14" not in incident.entities.source_ips
    assert "mruiz" not in incident.narrative
    assert "10.10.1.14" not in incident.narrative
    assert {"admin"} <= set(incident.entities.users)


def test_no_d3_finding_cites_the_baseline_privilege_event(d3_findings) -> None:
    """FSD §6: only the two external-origin 4672 events are escalations."""
    cited = {log_id for finding in d3_findings for log_id in finding.evidence}

    assert cited == {"EVT-00126", "EVT-00193"}
    assert "EVT-00216" not in cited


def test_the_export_holds_exactly_the_six_incident_clusters(incidents) -> None:
    """FSD §8: six distinct clusters were verified by reading the file."""
    assert len(incidents) == 6


def test_no_finding_cites_evidence_that_is_not_in_the_frame(incidents, events) -> None:
    known = set(events["Log_ID"].astype(str))
    cited = {
        log_id
        for incident in incidents
        for finding in incident.findings
        for log_id in finding.evidence
    }

    assert cited <= known
    assert cited, "el motor no citó ninguna evidencia"


def test_a_lone_internal_privilege_event_produces_no_finding(incidents) -> None:
    """`EVT-00240` is an isolated internal `4672`: baseline, not an escalation."""
    cited = {
        log_id
        for incident in incidents
        for finding in incident.findings
        for log_id in finding.evidence
    }

    assert "EVT-00240" not in cited
    assert "EVT-00388" not in cited


def test_the_same_frame_always_produces_the_same_findings(events, incidents) -> None:
    second_run = detect(events)

    def signature(collection):
        return [
            (incident.id, incident.first_seen, incident.last_seen, incident.evidence)
            for incident in collection
        ]

    assert signature(second_run) == signature(incidents)
    for incident in incidents:
        first_seen = [finding.first_seen for finding in incident.findings]
        assert first_seen == sorted(first_seen)
    first_seen = [incident.first_seen for incident in incidents]
    assert first_seen == sorted(first_seen)


def test_every_finding_declares_a_known_category_and_evidence(incidents) -> None:
    allowed = {
        "brute-force",
        "suspicious-logon",
        "privilege-escalation",
        "command-execution",
        "lateral-movement",
        "other-anomaly",
    }

    for incident in incidents:
        for finding in incident.findings:
            assert finding.category in allowed
            assert finding.code.startswith("D")
            assert finding.event_count == len(finding.evidence)
            assert finding.first_seen <= finding.last_seen
            assert finding.rationale.strip()
