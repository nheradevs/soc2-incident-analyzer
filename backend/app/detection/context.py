"""Pure helpers shared by the detectors: selection, evidence and entities.

Every detector selects its own rows; this module only turns a selection into a
`Finding` in one consistent way (same ordering, same evidence, same entity
extraction), so a new rule cannot invent a different evidence shape.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from app.detection.models import Entities, Finding

# Findings of one rule are chained while consecutive events are this close. It is
# the same 15-minute tolerance the brute-force and spray rules use, so one attack
# seen twice is reported once instead of once per event.
FINDING_GAP = pd.Timedelta(minutes=15)

_SLUG_NOISE = re.compile(r"[^A-Za-z0-9]+")


def text(value: Any) -> str:
    return "" if value is None or pd.isna(value) else str(value).strip()


def slug(value: str) -> str:
    return _SLUG_NOISE.sub("-", value).strip("-").lower() or "sin-entidad"


def compact(timestamp: Any) -> str:
    """Stable, sortable key for a timestamp: 2026-10-23 09:06:00 → 20261023T090600."""
    return pd.Timestamp(timestamp).strftime("%Y%m%dT%H%M%S")


def hhmmss(timestamp: Any) -> str:
    return pd.Timestamp(timestamp).strftime("%H:%M:%S")


def minutes_between(first: Any, last: Any) -> int:
    return int(round((pd.Timestamp(last) - pd.Timestamp(first)).total_seconds() / 60))


def count_es(value: int) -> str:
    """Spanish thousands separator: 1234 → 1.234."""
    return f"{value:,}".replace(",", ".")


def ordered(rows: pd.DataFrame) -> pd.DataFrame:
    """Deterministic row order: time first, `Log_ID` as the tie-breaker."""
    if rows.empty:
        return rows
    return rows.sort_values(["timestamp", "Log_ID"], kind="stable").reset_index(drop=True)


def selection(events: pd.DataFrame | None, expression: pd.Series | None = None) -> pd.DataFrame:
    """Rows of one event family, with unusable timestamps dropped.

    An empty selection keeps the columns of the frame, so callers can filter a
    selection that turned out to be empty without special-casing it.
    """
    if events is None or events.empty:
        return pd.DataFrame()
    rows = events if expression is None else events[expression]
    if rows.empty:
        return events.iloc[0:0]
    return ordered(rows.dropna(subset=["timestamp"]))


def by_event(events: pd.DataFrame | None, event_ids: tuple[str, ...]) -> pd.DataFrame:
    if events is None or events.empty:
        return pd.DataFrame()
    return selection(events, events["event_id_norm"].isin(event_ids))


def window_end(timestamps: list, index: int, window: pd.Timedelta) -> int:
    """Last row of the closed window that starts at `index` (thresholds are inclusive)."""
    end = index
    while end + 1 < len(timestamps) and timestamps[end + 1] - timestamps[index] <= window:
        end += 1
    return end


def chain(rows: pd.DataFrame, max_gap: pd.Timedelta = FINDING_GAP) -> list[pd.DataFrame]:
    """Split ordered rows into groups whose consecutive events are close in time."""
    if rows.empty:
        return []
    blocks: list[pd.DataFrame] = []
    start = 0
    timestamps = rows["timestamp"].tolist()
    for index in range(1, len(timestamps)):
        if timestamps[index] - timestamps[index - 1] > max_gap:
            blocks.append(rows.iloc[start:index])
            start = index
    blocks.append(rows.iloc[start:])
    return [block for block in blocks if not block.empty]


def entities_of(rows: pd.DataFrame) -> Entities:
    def values(column: str) -> tuple[str, ...]:
        if column not in rows:
            return ()
        found = {text(value) for value in rows[column].tolist()}
        return tuple(sorted(value for value in found if value))

    return Entities(
        users=values("user_norm"),
        hosts=values("host_norm"),
        source_ips=values("Source_IP"),
        shares=values("share"),
    )


def build_finding(
    *,
    code: str,
    category: str,
    title: str,
    rows: pd.DataFrame,
    severity_hint: str,
    rationale: str,
    key: str,
    requires_validation: bool = False,
    measured_bytes: int | None = None,
) -> Finding:
    """Turn a rule's own selection into a finding with exact evidence."""
    evidence_rows = ordered(rows.dropna(subset=["timestamp"]))
    log_ids = tuple(dict.fromkeys(evidence_rows["Log_ID"].astype(str).tolist()))
    return Finding(
        id=f"{code}:{key}",
        code=code,
        category=category,
        title=title,
        entities=entities_of(evidence_rows),
        event_count=len(evidence_rows),
        first_seen=evidence_rows["timestamp"].iloc[0].to_pydatetime(),
        last_seen=evidence_rows["timestamp"].iloc[-1].to_pydatetime(),
        evidence=log_ids,
        severity_hint=severity_hint,
        requires_validation=requires_validation,
        rationale=rationale,
        measured_bytes=measured_bytes,
    )
