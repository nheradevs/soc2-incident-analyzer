"""Integration check against the real client export (FSD §3, §4, §8).

These assertions are the measured facts from the FSD. If normalization or
parsing regress, one of them breaks: a detector would then either miss a real
incident or invent evidence that is not in the file.
"""

from pathlib import Path

import pandas as pd
import pytest

from app.ingest.loader import SchemaError, load_export

EXPORT = Path(__file__).resolve().parents[2] / "SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx"


@pytest.fixture(scope="module")
def events() -> pd.DataFrame:
    return load_export(EXPORT)


def test_the_export_is_present_and_has_the_expected_shape(events: pd.DataFrame) -> None:
    assert EXPORT.exists(), f"falta el fixture de entrada: {EXPORT}"
    assert events.shape[0] == 715
    assert {"event_id_norm", "host_norm", "ip_class", "result_norm"} <= set(events.columns)


def test_trap_4_4_dc_duplicate_collapses_to_ten_hosts(events: pd.DataFrame) -> None:
    assert events["Hostname"].nunique() == 11
    assert events["host_norm"].nunique() == 10


def test_trap_4_1_mixed_event_ids_survive_as_text(events: pd.DataFrame) -> None:
    assert events["event_id_norm"].str.fullmatch(r"\d+").sum() == 672
    assert (events["event_id_norm"] == "PROXY_ACCESS").sum() == 22
    assert (events["event_id_norm"] == "HTTP_ACCESS").sum() == 21


def test_trap_4_3_failures_span_verdicts_and_http_codes(events: pd.DataFrame) -> None:
    """102 Security verdicts + 6 x 404 + 9 x 500 = 117 unified failures."""
    assert (events["result_norm"] == "failure").sum() == 102
    assert events["is_failure"].sum() == 117
    assert set(events["result_norm"].unique()) == {
        "success",
        "failure",
        "allowed",
        "http_2xx",
        "http_4xx",
        "http_5xx",
    }


def test_trap_4_8_only_three_source_addresses_are_external(events: pd.DataFrame) -> None:
    external = sorted(events.loc[events["ip_class"] == "external", "Source_IP"].unique())

    assert external == ["192.0.2.91", "198.51.100.77", "203.0.113.74"]


def test_trap_4_5_no_principal_is_mistaken_for_a_person(events: pd.DataFrame) -> None:
    anonymous = events[events["principal_type"] == "anonymous"]

    assert set(anonymous["Log_Source"]) == {"IIS"}
    assert (events["principal_type"] == "machine").sum() == 1


def test_lateral_hop_is_only_visible_through_the_prose(events: pd.DataFrame) -> None:
    hop = events[events["Log_ID"] == "EVT-00225"].iloc[0]

    assert hop["lateral_source"] == "APP-SRV01"
    assert hop["logon_type"] == 3


def test_proxy_exfiltration_volume_is_measurable(events: pd.DataFrame) -> None:
    proxy = events[events["event_id_norm"] == "PROXY_ACCESS"]

    assert len(proxy) == 22
    assert proxy["bytes_out"].sum() == 253_305_558
    assert proxy["bytes_out"].sum() > 253_000_000


def test_persistence_artifacts_are_extracted(events: pd.DataFrame) -> None:
    task = events[events["Log_ID"] == "EVT-00523"].iloc[0]
    service = events[events["Log_ID"] == "EVT-00524"].iloc[0]

    assert task["task_name"] == "\\Microsoft\\Windows\\UpdateCheck"
    assert task["script_path"] == "C:\\ProgramData\\updatecheck.ps1"
    assert service["service_name"] == "WinUpdateHelper"
    assert service["image_path"] == "C:\\ProgramData\\wuhelper.exe"


def test_redacted_payloads_are_flagged_not_guessed(events: pd.DataFrame) -> None:
    redacted = events[events["payload_redacted"]]

    assert set(redacted["Log_ID"]) == {"EVT-00198", "EVT-00280"}


def test_unknown_schema_is_rejected_with_a_readable_error(tmp_path: Path) -> None:
    path = tmp_path / "random.xlsx"
    pd.DataFrame({"foo": [1], "bar": [2]}).to_excel(path, index=False)

    with pytest.raises(SchemaError, match="Faltan columnas"):
        load_export(path)
