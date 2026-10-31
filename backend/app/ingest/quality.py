"""Data-quality report for a loaded SIEM export (RF1, FSD §3 and §4).

The report states what the file *contains*: a metric that cannot be measured is
reported as zero known findings instead of a guess (S8). Keys are stable
English identifiers and every value is JSON-serializable, so the frontend can
render the report as-is.

The functions accept a raw frame as well as a normalized one: when the derived
columns are absent they are recomputed with the same helpers `normalize` uses,
never with a second, divergent implementation.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from app.ingest.normalize import event_id_norm, host_norm
from app.ingest.parse import FIELD_COLUMNS

# Columns produced by `normalize` + `parse`. Kept explicit so an unknown column
# in the workbook is reported as detected (it is source data) rather than
# silently mistaken for a derived one.
_NORMALIZE_DERIVED_COLUMNS = (
    "event_id_norm",
    "event_family",
    "timestamp",
    "host_norm",
    "principal_type",
    "user_norm",
    "ip_class",
    "dest_type",
    "dest_host",
    "dest_port",
    "result_norm",
    "is_failure",
)
DERIVED_COLUMNS = frozenset({*_NORMALIZE_DERIVED_COLUMNS, *FIELD_COLUMNS})

_NUMERIC_EVENT_ID = re.compile(r"^\d+$")


def detected_columns(frame: pd.DataFrame) -> list[str]:
    """Return the workbook columns, in file order, without the derived ones."""
    return [column for column in frame.columns if column not in DERIVED_COLUMNS]


def _host_norms(frame: pd.DataFrame) -> pd.Series:
    if "host_norm" in frame:
        return frame["host_norm"]
    return frame["Hostname"].map(host_norm)


def _event_ids(frame: pd.DataFrame) -> pd.Series:
    values = frame["event_id_norm"] if "event_id_norm" in frame else frame["Event_ID"].map(
        event_id_norm
    )
    return values.astype("string").fillna("")


def _timestamps(frame: pd.DataFrame) -> pd.Series | None:
    if "timestamp" in frame:
        return frame["timestamp"]
    if "Timestamp" in frame:
        return pd.to_datetime(frame["Timestamp"], errors="coerce")
    return None


def _null_counts(frame: pd.DataFrame) -> dict[str, int]:
    return {
        column: int(frame[column].isna().sum()) for column in detected_columns(frame)
    }


def _duplicate_hosts(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Trap 4.4: raw spellings that collapse to one `host_norm` (e.g. DC-01/DC01)."""
    if "Hostname" not in frame:
        return []

    raw = frame["Hostname"].astype("string").fillna("")
    findings: list[dict[str, Any]] = []
    for normalized, group in frame.groupby(_host_norms(frame), sort=True, dropna=False):
        spellings = sorted(set(raw.loc[group.index]))
        if len(spellings) < 2:
            continue
        counts = raw.loc[group.index].value_counts()
        findings.append(
            {
                "host_norm": str(normalized),
                "spellings": spellings,
                "spelling_counts": {spelling: int(counts[spelling]) for spelling in spellings},
                "row_count": int(len(group)),
            }
        )

    findings.sort(key=lambda finding: (-finding["row_count"], finding["host_norm"]))
    return findings


def _event_id_types(frame: pd.DataFrame) -> dict[str, Any]:
    """Trap 4.1: `Event_ID` mixes numeric Windows ids with named source ids."""
    empty: dict[str, Any] = {
        "mixed": False,
        "numeric_count": 0,
        "named_count": 0,
        "named_ids": {},
        "raw_types": {},
    }
    if "Event_ID" not in frame:
        return empty

    normalized = _event_ids(frame)
    numeric = normalized.str.fullmatch(_NUMERIC_EVENT_ID).fillna(False)
    named = normalized[~numeric & (normalized != "")]

    raw_types = frame["Event_ID"].map(lambda value: type(value).__name__).value_counts()
    named_ids = named.value_counts()
    numeric_count = int(numeric.sum())

    return {
        "mixed": numeric_count > 0 and len(named) > 0,
        "numeric_count": numeric_count,
        "named_count": int(len(named)),
        "named_ids": {str(key): int(named_ids[key]) for key in sorted(named_ids.index)},
        "raw_types": {str(key): int(raw_types[key]) for key in sorted(raw_types.index)},
    }


def _timestamp_parse_failures(frame: pd.DataFrame) -> dict[str, Any]:
    """Trap 4.2: rows whose `Timestamp` could not become a `datetime`."""
    stamps = _timestamps(frame)
    if stamps is None:
        return {"count": 0, "log_ids": []}

    failed = stamps.isna()
    if "Log_ID" in frame:
        log_ids = [str(value) for value in frame.loc[failed, "Log_ID"]]
    else:
        log_ids = [str(position) for position in frame.index[failed]]
    return {"count": int(failed.sum()), "log_ids": log_ids}


def quality_report(events: pd.DataFrame) -> dict[str, Any]:
    """Summarize the data-quality findings of one loaded export.

    Never raises on a sparse or synthetic frame: a missing column is reported as
    no findings rather than a fabricated count.
    """
    columns = detected_columns(events)
    return {
        "row_count": int(len(events)),
        "column_count": len(columns),
        "detected_columns": columns,
        "null_counts": _null_counts(events),
        "duplicate_hosts": _duplicate_hosts(events),
        "event_id_types": _event_id_types(events),
        "timestamp_parse_failures": _timestamp_parse_failures(events),
    }
