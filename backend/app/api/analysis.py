"""Dashboard payload and incident drill-down (FSD RF4 / S3).

Everything here is derived from two inputs: the normalized frame the upload
endpoint stored and the classification of the detection engine. No number is
hardcoded and nothing is estimated, so the dashboard cannot disagree with the
report: both read the same frame and the same `risk` blocks.

Two FSD rules are enforced by the shape of the payload, not by convention:

* there is no "top source IPs" section. FSD §4.8 records that `Source_IP` does
  not resolve to a single host and is not attacker infrastructure in this
  export, so outbound volume is grouped by **external destination** only;
* the account ranking counts people. Anonymous principals and machine/service
  accounts are excluded *and reported*, because silently dropping them would
  hide part of the traffic.

Determinism: every ranking sorts by count and then by its own key, the series
covers exactly the hours of the export's own window, and no wall-clock value
enters the payload. The same frame always produces the same JSON.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.api.serialization import json_value
from app.detection.engine import detect
from app.detection.models import CATEGORIES, CATEGORY_LABEL_ES
from app.ingest.normalize import ip_class
from app.risk.classifier import classify
from app.risk.matrix import LEVEL_KEY, LEVEL_RANK, LEVELS

# Chart buckets are one hour wide: the export spans 5 h 58 min, so a finer grain
# would invent resolution the logs do not have.
HOUR_FREQUENCY = "h"

# `Destination` shapes that can carry network volume. A UNC share is internal by
# construction and its `dest_host` is a host name, never an external address.
VOLUME_DESTINATION_TYPES = frozenset({"endpoint", "host"})

# Why a principal is not counted as a person (FSD §4.5). Reported next to the
# excluded principal, so the exclusion is auditable.
EXCLUSION_REASON_ES = {
    "anonymous": "principal anónimo",
    "machine": "cuenta de servicio o de máquina",
}

# Spanish name of each detection rule, used by the "attack types" chart. It is a
# presentation table only: counts always come from the findings.
ATTACK_TYPE_LABEL_ES = {
    "D1a": "Fuerza bruta dirigida",
    "D1b": "Password spray",
    "D1c": "Exposición externa",
    "D1d": "Compromiso posterior al ataque",
    "D2": "Inicio de sesión sospechoso",
    "D3": "Escalamiento de privilegios",
    "D4": "Ejecución de comandos y procesos",
    "D5": "Movimiento lateral",
    "D6": "Otra anomalía",
    "D7": "Exfiltración",
}


@dataclass(frozen=True, slots=True)
class Analysis:
    """Dashboard payload plus the full drill-down of every incident."""

    dashboard: dict[str, Any]
    incidents: dict[str, dict[str, Any]]


def _text(value: Any) -> str:
    return "" if value is None or pd.isna(value) else str(value).strip()


def _ranking(values: pd.Series, key: str) -> list[dict[str, Any]]:
    """Count occurrences of one column, ranked by count then by value."""
    counts = values.astype("string").fillna("").value_counts()
    items = [
        {key: label, "events": int(count)}
        for label, count in counts.items()
        if _text(label)
    ]
    return sorted(items, key=lambda item: (-item["events"], item[key]))


def _hour_series(frame: pd.DataFrame) -> tuple[list[dict[str, Any]], int]:
    """Events per hour, from the first to the last hour of the export itself.

    Rows without a parsed timestamp cannot be placed in a bucket; they are
    counted and returned separately instead of being spread over the chart.
    """
    stamps = frame["timestamp"].dropna()
    if stamps.empty:
        return [], int(len(frame))

    hours = stamps.dt.floor(HOUR_FREQUENCY)
    counts = hours.value_counts()
    series = [
        {
            "hour": bucket.isoformat(),
            "label": bucket.strftime("%H:%M"),
            "events": int(counts.get(bucket, 0)),
        }
        for bucket in pd.date_range(hours.min(), hours.max(), freq=HOUR_FREQUENCY)
    ]
    return series, int(len(frame) - len(stamps))


def _time_window(frame: pd.DataFrame, hours: int) -> dict[str, Any]:
    stamps = frame["timestamp"].dropna()
    if stamps.empty:
        return {"start": None, "end": None, "duration_minutes": 0, "hours": 0}
    start, end = stamps.min(), stamps.max()
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "duration_minutes": int(round((end - start).total_seconds() / 60)),
        "hours": hours,
    }


def _account_ranking(frame: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Human accounts, plus the principals left out and why.

    `principal_type` is the normalization layer's verdict (FSD §4.5) and is
    reused as-is: a second regex here would drift from the one the detectors use.
    """
    principals = frame["principal_type"].astype("string").fillna("")
    people = frame[principals == "human"]
    excluded_rows = frame[principals != "human"]

    grouped = excluded_rows.groupby(["principal_type", "User"], dropna=False).size()
    exclusions = [
        {
            "principal": _text(principal),
            "kind": str(kind),
            "reason": EXCLUSION_REASON_ES.get(str(kind), str(kind)),
            "events": int(count),
        }
        for (kind, principal), count in grouped.items()
    ]
    exclusions.sort(key=lambda item: (-item["events"], item["kind"], item["principal"]))
    return _ranking(people["user_norm"], "user"), exclusions


def _outbound_volume(frame: pd.DataFrame) -> dict[str, Any]:
    """Volume sent to external destinations, grouped by address and port.

    Only addresses can be classified (FSD §4.8): an external host name has no
    knowable position in the network, so it is not presented as an external
    destination. Rows without `bytes_out` still count as an event but contribute
    no volume, which is why `events_with_bytes` is published next to `bytes_out`.
    """
    destinations = frame["dest_host"].astype("string").fillna("")
    external = frame["dest_type"].isin(VOLUME_DESTINATION_TYPES) & destinations.map(
        lambda value: ip_class(value) == "external"
    )

    groups: dict[tuple[str, int | None], dict[str, int]] = {}
    for row in frame[external].itertuples():
        port = None if pd.isna(row.dest_port) else int(row.dest_port)
        entry = groups.setdefault(
            (str(row.dest_host), port),
            {"events": 0, "events_with_bytes": 0, "bytes_out": 0},
        )
        entry["events"] += 1
        if not pd.isna(row.bytes_out):
            entry["bytes_out"] += int(row.bytes_out)
            entry["events_with_bytes"] += 1

    items = [
        {"destination": destination, "port": port, **entry}
        for (destination, port), entry in groups.items()
    ]
    items.sort(key=lambda item: (-item["bytes_out"], item["destination"], item["port"] or 0))
    return {
        "items": items,
        "total_events": sum(item["events"] for item in items),
        "total_bytes": sum(item["bytes_out"] for item in items),
    }


def _categories(classified: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detection coverage by category, with the six categories always present."""
    findings: Counter[str] = Counter()
    incidents: Counter[str] = Counter()
    for incident in classified:
        incidents.update(incident["categories"])
        findings.update(finding["category"] for finding in incident["findings"])
    return [
        {
            "category": category,
            "label": CATEGORY_LABEL_ES[category],
            "findings": findings[category],
            "incidents": incidents[category],
        }
        for category in CATEGORIES
    ]


def _attack_types(classified: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: Counter[str] = Counter()
    evidence: dict[str, set[str]] = defaultdict(set)
    for incident in classified:
        for finding in incident["findings"]:
            findings[finding["code"]] += 1
            evidence[finding["code"]].update(finding["evidence"])
    items = [
        {
            "code": code,
            "label": ATTACK_TYPE_LABEL_ES.get(code, code),
            "findings": count,
            "events": len(evidence[code]),
        }
        for code, count in findings.items()
    ]
    items.sort(key=lambda item: (-item["findings"], item["code"]))
    return items


def _risk_summary(classified: list[dict[str, Any]]) -> dict[str, Any]:
    incidents: Counter[str] = Counter(item["risk"]["level"] for item in classified)
    findings: Counter[str] = Counter(
        finding["risk"]["level"] for item in classified for finding in item["findings"]
    )
    return {
        "levels": [
            {
                "level": level,
                "level_key": LEVEL_KEY[level],
                "incidents": incidents[level],
                "findings": findings[level],
            }
            for level in LEVELS
        ],
        "incidents_total": int(len(classified)),
        "findings_total": sum(findings.values()),
        "affected": _affected(classified),
    }


def _affected(classified: list[dict[str, Any]]) -> dict[str, Any]:
    """Entities touched by an incident; source IPs only when they are external."""
    users: set[str] = set()
    hosts: set[str] = set()
    external_sources: set[str] = set()
    for incident in classified:
        entities = incident["entities"]
        users.update(entities["users"])
        hosts.update(entities["hosts"])
        external_sources.update(
            source_ip
            for source_ip in entities["source_ips"]
            if ip_class(source_ip) == "external"
        )
    return {
        "users": sorted(users),
        "hosts": sorted(hosts),
        "external_sources": sorted(external_sources),
    }


def _incident_summary(incident: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": incident["id"],
        "title": incident["title"],
        "level": incident["risk"]["level"],
        "level_key": incident["risk"]["level_key"],
        "categories": incident["categories"],
        "categories_labels": [
            CATEGORY_LABEL_ES.get(category, category) for category in incident["categories"]
        ],
        "first_seen": incident["first_seen"],
        "last_seen": incident["last_seen"],
        "event_count": incident["event_count"],
        "entities": incident["entities"],
        "requires_validation": incident["requires_validation"],
    }


def _incident_order(incident: dict[str, Any]) -> tuple[int, str, str]:
    """Most severe first, then chronological, then by id: a total order."""
    return (-LEVEL_RANK[incident["risk"]["level"]], incident["first_seen"], incident["id"])


def _log_index(frame: pd.DataFrame) -> pd.DataFrame:
    """Rows addressable by `Log_ID`, the key every finding cites.

    `drop=False` keeps the key as a column: the evidence rows shown to the
    analyst must look exactly like the export, `Log_ID` included.
    """
    return frame.drop_duplicates(subset="Log_ID", keep="first").set_index(
        "Log_ID", drop=False
    )


def _evidence_rows(index: pd.DataFrame, log_ids: list[str]) -> list[dict[str, Any]]:
    """The cited rows, in citation order, with every column the export has."""
    known = index.index
    return [
        {column: json_value(value) for column, value in index.loc[log_id].items()}
        for log_id in log_ids
        if log_id in known
    ]


def _drilldown(incident: dict[str, Any], index: pd.DataFrame) -> dict[str, Any]:
    """Classification, findings and the joined evidence rows of one incident."""
    payload = dict(incident)
    payload["level"] = incident["risk"]["level"]
    payload["level_key"] = incident["risk"]["level_key"]
    payload["categories_labels"] = [
        CATEGORY_LABEL_ES.get(category, category) for category in incident["categories"]
    ]
    payload["evidence_log_ids"] = list(incident["evidence"])

    known = index.index
    missing: set[str] = set()
    findings: list[dict[str, Any]] = []
    for finding in incident["findings"]:
        cited = [log_id for log_id in finding["evidence"]]
        missing.update(log_id for log_id in cited if log_id not in known)
        findings.append({**finding, "evidence_rows": _evidence_rows(index, cited)})

    payload["findings"] = findings
    payload["evidence_missing"] = sorted(missing)
    return payload


def analyze(frame: pd.DataFrame) -> Analysis:
    """Detect, classify and shape the dashboard payload of one frame."""
    ordered = sorted(classify(detect(frame)), key=_incident_order)
    index = _log_index(frame)
    series, without_timestamp = _hour_series(frame)
    top_users, excluded_accounts = _account_ranking(frame)
    categories = _categories(ordered)

    dashboard = {
        "coverage": {
            "events_analysed": int(len(frame)),
            "events_without_timestamp": without_timestamp,
            "incidents": len(ordered),
            "findings": sum(len(incident["findings"]) for incident in ordered),
            "time_window": _time_window(frame, len(series)),
            "categories": categories,
            "covered_categories": [row["category"] for row in categories if row["findings"]],
            "uncovered_categories": [
                row["category"] for row in categories if not row["findings"]
            ],
        },
        "risk": _risk_summary(ordered),
        "charts": {
            "events_by_hour": series,
            "top_hosts": _ranking(frame["host_norm"], "host"),
            "top_users": top_users,
            "excluded_accounts": excluded_accounts,
            "attack_types": _attack_types(ordered),
            "outbound_by_destination": _outbound_volume(frame),
        },
        "incidents": [_incident_summary(incident) for incident in ordered],
    }
    return Analysis(
        dashboard=dashboard,
        incidents={incident["id"]: _drilldown(incident, index) for incident in ordered},
    )
