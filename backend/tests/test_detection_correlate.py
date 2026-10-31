"""Correlation of findings into incidents (FSD RF2, §8).

Findings become one incident only when they share a normalized entity **and**
the resulting window stays inside 30 minutes. These tests pin the window
behaviour, the refusal to chain findings that share nothing, and the INC-2
kill chain on the real export.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.detection import detect
from app.detection.correlator import correlate
from app.detection.models import Entities, Finding
from app.ingest.loader import load_export

DAY = datetime(2026, 10, 23)
EXPORT = Path(__file__).resolve().parents[2] / "SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx"


def finding(
    code: str = "D1a",
    category: str = "brute-force",
    *,
    minute: int,
    duration: int = 0,
    user: str = "jlopez",
    host: str = "DC01",
    ip: str = "203.0.113.74",
    log_ids: tuple[str, ...] | None = None,
    severity_hint: str = "high",
    requires_validation: bool = False,
) -> Finding:
    first_seen = DAY + timedelta(minutes=minute)
    evidence = log_ids if log_ids is not None else (f"EVT-{minute:05d}",)
    return Finding(
        id=f"{code}:{minute:04d}:{user}",
        code=code,
        category=category,
        title=f"{code} sobre {user}",
        entities=Entities(users=(user,), hosts=(host,), source_ips=(ip,), shares=()),
        event_count=len(evidence),
        first_seen=first_seen,
        last_seen=first_seen + timedelta(minutes=duration),
        evidence=evidence,
        severity_hint=severity_hint,
        requires_validation=requires_validation,
        rationale=f"Hallazgo {code} sobre {user}.",
    )


def test_findings_sharing_an_entity_inside_the_window_form_one_incident() -> None:
    incidents = correlate(
        [
            finding("D1a", "brute-force", minute=0, log_ids=("EVT-00001",)),
            finding("D4", "command-execution", minute=29, log_ids=("EVT-00002",)),
        ]
    )

    assert len(incidents) == 1
    incident = incidents[0]
    assert [item.code for item in incident.findings] == ["D1a", "D4"]
    assert incident.categories == ("brute-force", "command-execution")
    assert incident.evidence == ("EVT-00001", "EVT-00002")
    assert incident.event_count == 2


def test_findings_beyond_the_thirty_minute_window_stay_separate() -> None:
    incidents = correlate(
        [
            finding("D1a", "brute-force", minute=0),
            finding("D4", "command-execution", minute=31),
        ]
    )

    assert len(incidents) == 2


def test_findings_without_a_shared_entity_do_not_correlate() -> None:
    incidents = correlate(
        [
            finding("D1a", "brute-force", minute=0),
            finding(
                "D4",
                "command-execution",
                minute=5,
                user="aperez",
                host="FSC01",
                ip="198.51.100.77",
            ),
        ]
    )

    assert len(incidents) == 2


def test_findings_sharing_only_a_host_do_not_correlate() -> None:
    """Several users touch the same file server within half an hour: host overlap
    alone is not evidence of one intrusion."""
    incidents = correlate(
        [
            finding("D3", "privilege-escalation", minute=0, user="mruiz", host="FSSRV01",
                    ip="10.10.1.14"),
            finding("D4", "command-execution", minute=5, user="admin", host="FSSRV01",
                    ip="198.51.100.77"),
        ]
    )

    assert len(incidents) == 2
    assert {item.findings[0].code for item in incidents} == {"D3", "D4"}


def test_findings_sharing_an_account_correlate_across_hosts() -> None:
    incidents = correlate(
        [
            finding("D1a", "brute-force", minute=0, user="admin", host="APPSRV01",
                    ip="198.51.100.77"),
            finding("D5", "lateral-movement", minute=5, user="admin", host="FSSRV01",
                    ip="10.10.2.15"),
        ]
    )

    assert len(incidents) == 1
    assert [item.code for item in incidents[0].findings] == ["D1a", "D5"]


def test_findings_sharing_a_source_ip_correlate_across_accounts() -> None:
    incidents = correlate(
        [
            finding("D6", "other-anomaly", minute=0, user="anonimo", host="WEB01",
                    ip="192.0.2.91"),
            finding("D4", "command-execution", minute=5, user="IIS APPPOOL\\DefaultAppPool",
                    host="APPSRV01", ip="192.0.2.91"),
        ]
    )

    assert len(incidents) == 1
    assert [item.code for item in incidents[0].findings] == ["D6", "D4"]


def test_the_chain_stops_when_the_window_would_grow_beyond_thirty_minutes() -> None:
    """A shared user is not enough: the incident window itself must fit 30 min."""
    incidents = correlate(
        [
            finding("D1a", "brute-force", minute=0),
            finding("D2", "suspicious-logon", minute=25),
            finding("D4", "command-execution", minute=55),
        ]
    )

    assert [len(incident.findings) for incident in incidents] == [2, 1]
    assert incidents[1].findings[0].code == "D4"


def test_incident_inherits_the_strongest_hint_and_the_need_for_validation() -> None:
    incidents = correlate(
        [
            finding("D6", "other-anomaly", minute=0, severity_hint="low", requires_validation=True),
            finding("D7", "other-anomaly", minute=10, severity_hint="critical"),
        ]
    )

    assert len(incidents) == 1
    assert incidents[0].severity_hint == "critical"
    assert incidents[0].requires_validation is True
    assert incidents[0].categories == ("other-anomaly",)


def test_incidents_are_ordered_by_first_seen_and_are_deterministic() -> None:
    findings = [
        finding("D1a", "brute-force", minute=40),
        finding("D1a", "brute-force", minute=0),
        finding("D1a", "brute-force", minute=20, user="aperez"),
    ]

    first_run = correlate(findings)
    second_run = correlate(list(reversed(findings)))

    assert [incident.first_seen for incident in first_run] == sorted(
        incident.first_seen for incident in first_run
    )
    assert [incident.id for incident in first_run] == [incident.id for incident in second_run]
    assert [incident.evidence for incident in first_run] == [
        incident.evidence for incident in second_run
    ]


@pytest.fixture(scope="module")
def incidents():
    return detect(load_export(EXPORT))


def incident_citing(incidents, log_id: str):
    matches = [incident for incident in incidents if log_id in incident.evidence]
    assert len(matches) == 1, f"{log_id} aparece en {len(matches)} incidentes"
    return matches[0]


def test_inc2_correlates_into_one_incident_from_brute_force_to_exfiltration(incidents) -> None:
    """INC-2 (FSD §8): RDP brute force → logon → privileges → commands → lateral
    movement → outbound connection. The export only shows an *allowed* outbound
    connection, so the narrative may not claim that data left the network."""
    incident = incident_citing(incidents, "EVT-00188")

    for log_id in ("EVT-00188", "EVT-00198", "EVT-00225", "EVT-00235"):
        assert log_id in incident.evidence

    codes = {item.code for item in incident.findings}
    assert {"D1a", "D1c", "D1d", "D2", "D3", "D4", "D5", "D6"} <= codes
    assert incident.categories[0] == "brute-force"
    assert "lateral-movement" in incident.categories
    assert "other-anomaly" in incident.categories

    narrative = incident.narrative
    assert "fuerza bruta" in narrative
    assert "movimiento lateral" in narrative
    assert narrative.index("fuerza bruta") < narrative.index("movimiento lateral")
    assert incident.first_seen >= DAY.replace(hour=9, minute=0)
    assert incident.last_seen <= DAY.replace(hour=9, minute=30)
    assert not incident.requires_validation
