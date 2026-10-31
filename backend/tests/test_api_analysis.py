"""Dashboard payload and incident drill-down (FSD RF4 / S3).

Two things are pinned here. First, the payload is *computed*: the six incidents
of the real export, the expected level distribution, a series that sums exactly
to the analysed events, outbound volume that only names external destinations,
and an account ranking that reports the principals it leaves out. Second, the
drill-down joins the cited `Log_ID`s back to the stored frame, so the UI shows
the same row an analyst reads in the export.

Determinism is a requirement of its own: two consecutive analyses of one frame
must return the same payload, including list order, and the cached result must
not survive the arrival of a new export.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.api.analysis as analysis_module
from app.api.session import session_store
from app.detection.models import CATEGORIES
from app.ingest.loader import REQUIRED_COLUMNS, load_export
from app.main import app
from app.risk.matrix import LEVEL_RANK

EXPORT = Path(__file__).resolve().parents[2] / "SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

NO_SESSION_MESSAGE = (
    "Todavía no se ha cargado ningún archivo. Suba un export .xlsx y vuelva a intentarlo."
)
EXCLUDED_PRINCIPALS = {"-", "IIS APPPOOL\\DefaultAppPool"}


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """Isolated process state: no leftover frame and no leftover cached analysis."""
    session_store.clear()
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    session_store.clear()


@pytest.fixture(scope="module")
def frame() -> pd.DataFrame:
    """The normalized export, to check evidence rows against the real frame."""
    return load_export(EXPORT)


def upload(client: TestClient, path: Path | None = None) -> None:
    source = path or EXPORT
    response = client.post(
        "/api/upload",
        files={"file": (source.name, source.read_bytes(), XLSX_MIME)},
    )
    assert response.status_code == 200, response.text


def analyze(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/analyze")
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture()
def dashboard(client: TestClient) -> dict[str, Any]:
    upload(client)
    return analyze(client)


def write_benign_export(path: Path) -> Path:
    """A schema-complete export with no detectable incident.

    Four identical internal logons: no external origin, no privileged account,
    no repeated description to flag as rare. Detection must find nothing, which
    is what makes the empty sections meaningful.
    """
    width = 4
    columns: dict[str, list[Any]] = {
        column: [f"{column}-{index}" for index in range(width)]
        for column in REQUIRED_COLUMNS
    }
    columns["Timestamp"] = [f"2026-10-23 08:0{index}:00" for index in range(width)]
    columns["Event_ID"] = [4624] * width
    columns["Hostname"] = ["WS-001"] * width
    columns["User"] = ["CORP\\analyst"] * width
    columns["Source_IP"] = ["10.10.1.50"] * width
    columns["Destination"] = ["DC-01"] * width
    columns["Log_Source"] = ["Security"] * width
    columns["Event_Description"] = ["An account was successfully logged on"] * width
    columns["Process_CommandLine"] = [None] * width
    columns["Result"] = ["Success"] * width
    columns["Severity"] = ["Informational"] * width
    pd.DataFrame(columns).to_excel(path, index=False)
    return path


def test_analyze_before_upload_is_a_conflict_in_spanish(client: TestClient) -> None:
    response = client.post("/api/analyze")

    assert response.status_code == 409
    assert response.json()["detail"] == NO_SESSION_MESSAGE


def test_drilldown_before_upload_is_a_conflict_in_spanish(client: TestClient) -> None:
    response = client.get("/api/incidents/INC-20261023-0820")

    assert response.status_code == 409
    assert response.json()["detail"] == NO_SESSION_MESSAGE


def test_payload_has_exactly_the_four_dashboard_sections(dashboard: dict[str, Any]) -> None:
    assert set(dashboard) == {"coverage", "risk", "charts", "incidents"}


def test_real_export_yields_six_incidents_with_the_expected_levels(
    dashboard: dict[str, Any],
) -> None:
    incidents = dashboard["incidents"]

    assert len(incidents) == 6
    assert dashboard["coverage"]["incidents"] == 6
    assert {item["level"] for item in incidents} == {"crítico", "alto"}
    distribution = {
        level["level"]: level["incidents"] for level in dashboard["risk"]["levels"]
    }
    assert distribution == {"crítico": 4, "alto": 2, "medio": 0, "bajo": 0}


def test_risk_levels_keep_the_fixed_order_and_key_names(dashboard: dict[str, Any]) -> None:
    levels = dashboard["risk"]["levels"]

    assert [level["level"] for level in levels] == ["crítico", "alto", "medio", "bajo"]
    assert [level["level_key"] for level in levels] == ["critical", "high", "medium", "low"]
    assert dashboard["risk"]["incidents_total"] == sum(level["incidents"] for level in levels)
    assert dashboard["risk"]["findings_total"] == sum(level["findings"] for level in levels)
    assert dashboard["risk"]["findings_total"] == dashboard["coverage"]["findings"] == 46


def test_every_incident_summary_carries_title_window_count_and_entities(
    dashboard: dict[str, Any],
) -> None:
    for incident in dashboard["incidents"]:
        assert set(incident) == {
            "id",
            "title",
            "level",
            "level_key",
            "categories",
            "categories_labels",
            "first_seen",
            "last_seen",
            "event_count",
            "entities",
            "requires_validation",
        }
        assert incident["id"].startswith("INC-")
        assert incident["title"]
        assert incident["first_seen"] <= incident["last_seen"]
        assert incident["event_count"] > 0
        assert set(incident["entities"]) == {"users", "hosts", "source_ips", "shares"}
        assert len(incident["categories"]) == len(incident["categories_labels"])


def test_incidents_are_ordered_by_severity_then_time(dashboard: dict[str, Any]) -> None:
    incidents = dashboard["incidents"]

    assert [item["level"] for item in incidents] == [
        "crítico",
        "crítico",
        "crítico",
        "crítico",
        "alto",
        "alto",
    ]
    ranks = [LEVEL_RANK[item["level"]] for item in incidents]
    assert ranks == sorted(ranks, reverse=True)
    critical_ids = [item["id"] for item in incidents if item["level"] == "crítico"]
    assert critical_ids == sorted(critical_ids)


def test_hour_series_covers_only_the_export_window_and_sums_every_event(
    dashboard: dict[str, Any],
) -> None:
    series = dashboard["charts"]["events_by_hour"]

    assert dashboard["coverage"]["events_analysed"] == 715
    assert sum(bucket["events"] for bucket in series) == 715
    assert [bucket["hour"] for bucket in series] == [
        "2026-10-23T07:00:00",
        "2026-10-23T08:00:00",
        "2026-10-23T09:00:00",
        "2026-10-23T10:00:00",
        "2026-10-23T11:00:00",
        "2026-10-23T12:00:00",
        "2026-10-23T13:00:00",
    ]
    assert [bucket["label"] for bucket in series][0] == "07:00"
    assert [bucket["label"] for bucket in series][-1] == "13:00"


def test_time_window_matches_the_export(dashboard: dict[str, Any]) -> None:
    window = dashboard["coverage"]["time_window"]

    assert window["start"] == "2026-10-23T07:46:07"
    assert window["end"] == "2026-10-23T13:44:06"
    assert window["duration_minutes"] == 358
    assert window["hours"] == 7
    assert dashboard["coverage"]["events_without_timestamp"] == 0


def test_category_coverage_lists_the_six_required_categories(
    dashboard: dict[str, Any],
) -> None:
    coverage = dashboard["coverage"]
    categories = coverage["categories"]

    assert [row["category"] for row in categories] == list(CATEGORIES)
    assert all(row["label"] for row in categories)
    assert sum(row["findings"] for row in categories) == 46
    assert set(coverage["covered_categories"]) | set(coverage["uncovered_categories"]) == set(
        CATEGORIES
    )
    assert not set(coverage["covered_categories"]) & set(coverage["uncovered_categories"])


def test_attack_types_are_counted_from_the_findings(dashboard: dict[str, Any]) -> None:
    attack_types = dashboard["charts"]["attack_types"]

    assert attack_types
    assert sum(item["findings"] for item in attack_types) == 46
    assert sum(item["events"] for item in attack_types) >= 46
    by_code = {item["code"]: item for item in attack_types}
    assert by_code["D7"]["label"] == "Exfiltración"
    assert by_code["D7"]["findings"] == 1
    assert all(item["label"] for item in attack_types)


def test_top_hosts_use_the_canonical_hostname(dashboard: dict[str, Any]) -> None:
    top_hosts = dashboard["charts"]["top_hosts"]

    hosts = [item["host"] for item in top_hosts]
    assert "DC01" in hosts
    assert "DC-01" not in hosts
    assert sum(item["events"] for item in top_hosts) == 715
    assert hosts[0] == "DC01"
    assert top_hosts[0]["events"] == 121


def test_top_accounts_exclude_and_report_anonymous_and_machine_principals(
    dashboard: dict[str, Any],
) -> None:
    charts = dashboard["charts"]

    accounts = [item["user"] for item in charts["top_users"]]
    assert not EXCLUDED_PRINCIPALS & set(accounts)
    assert "svc_backup" in accounts
    assert "IIS APPPOOL\\DefaultAppPool" not in accounts
    assert "-" not in accounts

    excluded = {item["principal"]: item for item in charts["excluded_accounts"]}
    assert set(excluded) == EXCLUDED_PRINCIPALS
    assert excluded["-"]["kind"] == "anonymous"
    assert excluded["-"]["events"] == 21
    assert excluded["-"]["reason"] == "principal anónimo"
    assert excluded["IIS APPPOOL\\DefaultAppPool"]["kind"] == "machine"
    assert excluded["IIS APPPOOL\\DefaultAppPool"]["events"] == 1
    assert excluded["IIS APPPOOL\\DefaultAppPool"]["reason"] == (
        "cuenta de servicio o de máquina"
    )

    accounted = sum(item["events"] for item in charts["top_users"]) + sum(
        item["events"] for item in charts["excluded_accounts"]
    )
    assert accounted == 715


def test_outbound_volume_only_names_external_destinations(dashboard: dict[str, Any]) -> None:
    outbound = dashboard["charts"]["outbound_by_destination"]
    items = {item["destination"]: item for item in outbound["items"]}

    assert set(items) == {"198.51.100.88", "203.0.113.88"}
    assert items["198.51.100.88"]["bytes_out"] == 253305558
    assert items["198.51.100.88"]["events"] == 22
    assert items["198.51.100.88"]["port"] == 443
    assert items["203.0.113.88"]["bytes_out"] == 0
    assert items["203.0.113.88"]["events_with_bytes"] == 0
    assert outbound["total_bytes"] == 253305558
    assert outbound["total_events"] == 23


def test_charts_do_not_rank_source_ips_as_a_risk_indicator(dashboard: dict[str, Any]) -> None:
    charts = dashboard["charts"]

    assert set(charts) == {
        "events_by_hour",
        "top_hosts",
        "top_users",
        "excluded_accounts",
        "attack_types",
        "outbound_by_destination",
    }
    assert "top_source_ips" not in charts


def test_drilldown_returns_evidence_rows_from_the_frame(
    client: TestClient, dashboard: dict[str, Any], frame: pd.DataFrame
) -> None:
    known_ids = set(frame["Log_ID"])

    for summary in dashboard["incidents"]:
        detail = client.get(f"/api/incidents/{summary['id']}").json()

        assert detail["id"] == summary["id"]
        assert detail["level"] == summary["level"]
        assert detail["evidence_missing"] == []
        assert detail["risk"]["justification"]
        assert detail["findings"]
        for finding in detail["findings"]:
            rows = finding["evidence_rows"]
            assert rows
            assert {row["Log_ID"] for row in rows} == set(finding["evidence"])
            assert set(row["Log_ID"] for row in rows) <= known_ids
            assert finding["risk"]["justification"]
            for row in rows:
                # Original columns plus the derived ones, like the export table.
                assert set(row) == set(frame.columns)


def test_drilldown_exposes_the_classification_block(
    dashboard: dict[str, Any], client: TestClient
) -> None:
    incident_id = dashboard["incidents"][0]["id"]

    detail = client.get(f"/api/incidents/{incident_id}").json()

    assert set(detail["risk"]) == {
        "level",
        "level_key",
        "impact",
        "confidence",
        "event_count",
        "requires_validation",
        "justification",
    }
    assert detail["level"] == detail["risk"]["level"]
    assert detail["categories_labels"]
    assert detail["narrative"]
    assert set(detail["entities"]) == {"users", "hosts", "source_ips", "shares"}
    assert detail["evidence_log_ids"] == detail["evidence"]


def test_drilldown_of_an_unknown_incident_is_a_spanish_404(
    client: TestClient, dashboard: dict[str, Any]
) -> None:
    response = client.get("/api/incidents/INC-9999-0000")

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "No existe un incidente con el identificador «INC-9999-0000»."
    )


def test_two_consecutive_analyses_return_the_same_payload(client: TestClient) -> None:
    upload(client)

    first = analyze(client)
    second = analyze(client)

    assert first == second


def test_drilldown_is_deterministic(client: TestClient, dashboard: dict[str, Any]) -> None:
    incident_id = dashboard["incidents"][0]["id"]

    first = client.get(f"/api/incidents/{incident_id}").json()
    second = client.get(f"/api/incidents/{incident_id}").json()

    assert first == second


def test_analysis_is_cached_for_the_session(
    client: TestClient, dashboard: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second call must not re-run detection: the session keeps the result."""

    def explode(_frame: pd.DataFrame) -> None:
        raise AssertionError("detection ran twice for the same frame")

    monkeypatch.setattr(analysis_module, "detect", explode)

    assert analyze(client) == dashboard


def test_a_new_upload_discards_the_cached_analysis(
    client: TestClient, dashboard: dict[str, Any], tmp_path: Path
) -> None:
    previous_incident = dashboard["incidents"][0]["id"]
    upload(client, write_benign_export(tmp_path / "benign.xlsx"))

    replaced = analyze(client)

    assert replaced["incidents"] == []
    assert replaced["coverage"]["events_analysed"] == 4
    assert client.get(f"/api/incidents/{previous_incident}").status_code == 404


def test_benign_export_produces_empty_sections_with_computed_zeros(
    client: TestClient, tmp_path: Path
) -> None:
    upload(client, write_benign_export(tmp_path / "benign.xlsx"))

    body = analyze(client)

    assert body["coverage"]["incidents"] == 0
    assert body["coverage"]["findings"] == 0
    assert body["coverage"]["covered_categories"] == []
    assert body["coverage"]["uncovered_categories"] == list(CATEGORIES)
    assert [level["incidents"] for level in body["risk"]["levels"]] == [0, 0, 0, 0]
    assert sum(bucket["events"] for bucket in body["charts"]["events_by_hour"]) == 4
    assert body["charts"]["attack_types"] == []
    assert body["charts"]["outbound_by_destination"] == {
        "items": [],
        "total_events": 0,
        "total_bytes": 0,
    }
    assert body["charts"]["top_users"] == [{"user": "analyst", "events": 4}]
    assert body["charts"]["excluded_accounts"] == []
    assert body["charts"]["top_hosts"] == [{"host": "WS001", "events": 4}]


def test_event_table_still_works_after_an_analysis(client: TestClient) -> None:
    upload(client)

    analyze(client)

    assert client.get("/api/events").json()["total"] == 715
    assert client.get("/api/health").json() == {"status": "ok"}
