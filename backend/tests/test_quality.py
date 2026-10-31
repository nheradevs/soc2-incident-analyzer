"""Data-quality report contract (RF1, FSD §3 and §4).

The report is what the UI shows right after an upload, so its keys and its
measured numbers are part of the API contract: they are asserted against the
real export, and against a tiny synthetic frame for the error paths.
"""

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from app.ingest.loader import load_export
from app.ingest.quality import quality_report

EXPORT = Path(__file__).resolve().parents[2] / "SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx"


@pytest.fixture(scope="module")
def events() -> pd.DataFrame:
    return load_export(EXPORT)


def test_report_pins_the_shape_of_the_real_export(events: pd.DataFrame) -> None:
    report = quality_report(events)

    assert report["row_count"] == 715
    assert report["column_count"] == 12
    assert report["detected_columns"][0] == "Log_ID"
    assert "host_norm" not in report["detected_columns"]
    assert "event_id_norm" not in report["detected_columns"]


def test_report_counts_nulls_per_detected_column(events: pd.DataFrame) -> None:
    """FSD §3: Destination 262 nulls, Process_CommandLine 560, the rest none."""
    null_counts = quality_report(events)["null_counts"]

    assert null_counts["Destination"] == 262
    assert null_counts["Process_CommandLine"] == 560
    assert null_counts["Timestamp"] == 0
    assert null_counts["Log_ID"] == 0
    assert len(null_counts) == 12


def test_report_flags_trap_4_4_dc01_duplicate_spellings(events: pd.DataFrame) -> None:
    """`DC-01` and `DC01` are one machine written two ways (91 + 30 rows)."""
    duplicates = quality_report(events)["duplicate_hosts"]

    assert len(duplicates) == 1
    assert duplicates[0] == {
        "host_norm": "DC01",
        "spellings": ["DC-01", "DC01"],
        "spelling_counts": {"DC-01": 91, "DC01": 30},
        "row_count": 121,
    }


def test_report_exposes_trap_4_1_mixed_event_id_types(events: pd.DataFrame) -> None:
    """`Event_ID` mixes 672 ints with 43 named ids."""
    types = quality_report(events)["event_id_types"]

    assert types["mixed"] is True
    assert types["numeric_count"] == 672
    assert types["named_count"] == 43
    assert types["named_ids"] == {"HTTP_ACCESS": 21, "PROXY_ACCESS": 22}
    assert types["raw_types"] == {"int": 672, "str": 43}


def test_report_confirms_every_real_timestamp_parsed(events: pd.DataFrame) -> None:
    """FSD §3: all 715 timestamps parse; the report says so instead of guessing."""
    assert quality_report(events)["timestamp_parse_failures"] == {
        "count": 0,
        "log_ids": [],
    }


def test_report_keys_are_stable_and_json_serializable(events: pd.DataFrame) -> None:
    report = quality_report(events)

    assert set(report) == {
        "row_count",
        "column_count",
        "detected_columns",
        "null_counts",
        "duplicate_hosts",
        "event_id_types",
        "timestamp_parse_failures",
    }
    assert json.loads(json.dumps(report, ensure_ascii=False)) == report


def test_report_flags_bad_rows_in_a_small_frame() -> None:
    """A raw (un-normalized) frame is enough: the report does its own derivation."""
    frame = pd.DataFrame(
        {
            "Log_ID": ["EVT-00001", "EVT-00002", "EVT-00003"],
            "Timestamp": ["2026-10-23 07:46:07", "no-es-fecha", "2026-10-23 08:00:00"],
            "Hostname": ["DC-01", "DC01", "WS-018"],
            "Event_ID": [4625, "PROXY_ACCESS", 4624],
            "Destination": ["DC-01", None, "WEB-01:443"],
        }
    )

    report = quality_report(frame)

    assert report["row_count"] == 3
    assert report["duplicate_hosts"] == [
        {
            "host_norm": "DC01",
            "spellings": ["DC-01", "DC01"],
            "spelling_counts": {"DC-01": 1, "DC01": 1},
            "row_count": 2,
        }
    ]
    assert report["timestamp_parse_failures"] == {"count": 1, "log_ids": ["EVT-00002"]}
    assert report["event_id_types"]["numeric_count"] == 2
    assert report["event_id_types"]["named_ids"] == {"PROXY_ACCESS": 1}
    assert report["null_counts"]["Destination"] == 1


def test_report_serializes_a_half_empty_frame_without_guessing() -> None:
    """Missing columns are reported as zero findings, never invented."""
    report: dict[str, Any] = quality_report(pd.DataFrame({"Log_ID": ["EVT-00001"]}))

    assert report["row_count"] == 1
    assert report["detected_columns"] == ["Log_ID"]
    assert report["duplicate_hosts"] == []
    assert report["timestamp_parse_failures"] == {"count": 0, "log_ids": []}
    assert report["event_id_types"]["mixed"] is False
    assert report["event_id_types"]["named_ids"] == {}
