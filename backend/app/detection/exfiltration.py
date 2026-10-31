"""D7: exfiltration through the proxy.

The export only records proxy metadata (`bytes_out`, `uri`) for outbound HTTPS
POSTs, so the detector can measure volume and cadence towards an external
destination. It cannot read the content: a finding states how much was sent and
where, never what was sent.
"""

from __future__ import annotations

import pandas as pd

from app.detection.context import (
    build_finding,
    compact,
    count_es,
    hhmmss,
    minutes_between,
    selection,
    slug,
    text,
    window_end,
)
from app.detection.models import Finding
from app.ingest.normalize import ip_class

# Decimal megabytes, so the numbers match the measured baseline of FSD §6/§8
# (22 POST = 253,3 MB) and not a binary prefix nobody else in the project uses.
MEGABYTE = 1_000_000
D7_BYTES_THRESHOLD = 50 * MEGABYTE
D7_POST_THRESHOLD = 10
D7_WINDOW = pd.Timedelta(minutes=15)


def megabytes(value: int) -> str:
    """Spanish decimal comma, as in the FSD (253,3 MB)."""
    return f"{value / MEGABYTE:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + " MB"


def _is_post(rows: pd.DataFrame) -> pd.Series:
    return rows["Event_Description"].map(lambda value: "post" in text(value).lower())


def d7_exfiltration(events: pd.DataFrame | None) -> list[Finding]:
    if events is None or events.empty:
        return []

    external_destination = events["dest_host"].map(
        lambda value: bool(text(value)) and ip_class(text(value)) == "external"
    )
    proxy = selection(
        events, (events["event_family"] == "proxy") & external_destination
    )
    if proxy.empty:
        return []

    findings: list[Finding] = []
    for (destination, user, host), group in proxy.groupby(
        ["dest_host", "user_norm", "host_norm"], sort=True
    ):
        rows = group.reset_index(drop=True)
        timestamps = rows["timestamp"].tolist()
        bytes_out = rows["bytes_out"].fillna(0).astype("int64").tolist()
        posts = _is_post(rows).tolist()
        index = 0
        while index < len(timestamps):
            end = window_end(timestamps, index, D7_WINDOW)
            window = rows.iloc[index : end + 1]
            total = sum(bytes_out[index : end + 1])
            post_count = sum(1 for flag in posts[index : end + 1] if flag)
            if total >= D7_BYTES_THRESHOLD or post_count >= D7_POST_THRESHOLD:
                block_start = window["timestamp"].iloc[0]
                block_end = window["timestamp"].iloc[-1]
                findings.append(
                    build_finding(
                        code="D7",
                        category="other-anomaly",
                        title=f"Volumen saliente hacia {destination} desde {text(host)}",
                        rows=window,
                        severity_hint="critical",
                        rationale=(
                            f"{count_es(len(window))} solicitud(es) proxy "
                            f"({count_es(post_count)} POST) de la cuenta "
                            f"«{text(user) or 'sin identificar'}» en {text(host)} hacia "
                            f"{text(destination)} entre {hhmmss(block_start)} y "
                            f"{hhmmss(block_end)} ({minutes_between(block_start, block_end)} min), "
                            f"con {megabytes(total)} acumulados. Umbral: "
                            f"≥{megabytes(D7_BYTES_THRESHOLD)} o ≥{D7_POST_THRESHOLD} POST al "
                            f"mismo destino externo en {int(D7_WINDOW.total_seconds() // 60)} min. "
                            f"El proxy registra volumen y destino, no el contenido transferido."
                        ),
                        key=(
                            f"{slug(text(destination))}@{slug(text(user))}"
                            f"@{compact(block_start)}"
                        ),
                        measured_bytes=total,
                    )
                )
                index = end + 1
            else:
                index += 1
    return findings
