"""D3: privilege escalation.

`4672` (special privileges assigned) is normal on domain controllers: 7 of the 8
events in the export are internal. The detector therefore only fires when the
privilege event is correlated with an external origin, or when the same account
from the same source IP really failed in a burst, then succeeded, and only
afterwards received privileges. A lone internal `4672` is baseline and reports
nothing (FSD §6).

The burst threshold is the D1a one (`D1A_MIN_FAILURES` failures inside
`D1A_WINDOW`): FSD §6 measures at most 2 failures per account per 10 minutes as
normal behaviour, so one mistyped password followed by a normal logon is not an
escalation either.
"""

from __future__ import annotations

import pandas as pd

from app.detection.brute_force import D1A_MIN_FAILURES, D1A_WINDOW
from app.detection.context import (
    build_finding,
    by_event,
    compact,
    hhmmss,
    slug,
    text,
    window_end,
)
from app.detection.models import Finding

D3_WINDOW = pd.Timedelta(minutes=15)


def _recent_burst(failures: pd.DataFrame) -> pd.DataFrame | None:
    """Most recent run of `D1A_MIN_FAILURES` failures inside `D1A_WINDOW`, if any.

    `failures` is already time-ordered and filtered to one account, one source IP
    and the `D3_WINDOW` preceding the privilege event, so the D1a threshold is
    applied to the failures that this privilege event could be escalated by.
    """
    timestamps = failures["timestamp"].tolist()
    for index in range(len(timestamps) - 1, -1, -1):
        end = window_end(timestamps, index, D1A_WINDOW)
        if end - index + 1 >= D1A_MIN_FAILURES:
            return failures.iloc[index : end + 1]
    return None


def d3_privilege_escalation(events: pd.DataFrame | None) -> list[Finding]:
    privileges = by_event(events, ("4672",))
    if privileges.empty:
        return []

    failures = by_event(events, ("4625",))
    successes = by_event(events, ("4624",))

    findings: list[Finding] = []
    for position, row in enumerate(privileges.itertuples()):
        account = text(row.user_norm)
        source_ip = text(row.Source_IP)
        event_rows = privileges.iloc[[position]]

        if text(row.ip_class) == "external":
            findings.append(
                build_finding(
                    code="D3",
                    category="privilege-escalation",
                    title=f"Privilegios especiales desde la IP externa {source_ip}",
                    rows=event_rows,
                    severity_hint="high",
                    rationale=(
                        f"Asignación de privilegios especiales (4672) a «{account}» en "
                        f"{text(row.host_norm)} a las {hhmmss(row.timestamp)} desde la IP externa "
                        f"{source_ip}. El privilegio se otorga a una sesión que no proviene de la "
                        f"red interna."
                    ),
                    key=f"{slug(account)}@{compact(row.timestamp)}",
                )
            )
            continue

        window_start = row.timestamp - D3_WINDOW
        recent_failures = failures[
            (failures["Source_IP"] == source_ip)
            & (failures["user_norm"] == account)
            & (failures["timestamp"] >= window_start)
            & (failures["timestamp"] < row.timestamp)
        ]
        if recent_failures.empty:
            continue

        burst = _recent_burst(recent_failures)
        if burst is None:
            continue

        failure = burst.iloc[-1]
        between = successes[
            (successes["Source_IP"] == source_ip)
            & (successes["user_norm"] == account)
            & (successes["timestamp"] > failure["timestamp"])
            & (successes["timestamp"] <= row.timestamp)
        ]
        if between.empty:
            continue

        success = between.iloc[-1]
        findings.append(
            build_finding(
                code="D3",
                category="privilege-escalation",
                title=f"Fallo, éxito y privilegios para la cuenta {account}",
                rows=pd.concat([burst, between.tail(1), event_rows]),
                severity_hint="high",
                rationale=(
                    f"La cuenta «{account}» acumuló {len(burst)} inicios de sesión fallidos "
                    f"(4625) entre {hhmmss(burst['timestamp'].iloc[0])} y "
                    f"{hhmmss(failure['timestamp'])}, entró correctamente (4624) a las "
                    f"{hhmmss(success['timestamp'])} y recibió privilegios especiales (4672) a las "
                    f"{hhmmss(row.timestamp)}, todo desde {source_ip} en "
                    f"{text(row.host_norm)}. Un 4672 interno aislado es línea base; esta secuencia "
                    f"fallo → éxito → privilegios no lo es. Umbral: ≥{D1A_MIN_FAILURES} fallos de "
                    f"la misma cuenta en {int(D1A_WINDOW.total_seconds() // 60)} min."
                ),
                key=f"{slug(account)}@{compact(row.timestamp)}",
            )
        )
    return findings
