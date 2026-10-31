"""D5: lateral movement.

`Source_IP` never maps to a host (FSD §4.8), so the hop is only visible when the
event text names it: a `4624` of type 3 (network) or 10 (RDP) whose declared
source host differs from the machine that logged the event, followed by a share
or object access on that same machine within 10 minutes.
"""

from __future__ import annotations

import pandas as pd

from app.detection.context import build_finding, by_event, compact, hhmmss, slug, text
from app.detection.models import Finding
from app.ingest.normalize import host_norm

D5_WINDOW = pd.Timedelta(minutes=10)
D5_LOGON_TYPES = (3, 10)
D5_FOLLOW_UP_EVENTS = ("5140", "5145", "4663")


def d5_lateral_movement(events: pd.DataFrame | None) -> list[Finding]:
    logons = by_event(events, ("4624",))
    if logons.empty:
        return []

    findings: list[Finding] = []
    for position, row in enumerate(logons.itertuples()):
        if pd.isna(row.logon_type) or int(row.logon_type) not in D5_LOGON_TYPES:
            continue

        source_host = text(row.lateral_source)
        target_host = text(row.host_norm)
        if not source_host or not target_host:
            continue
        if host_norm(source_host) == target_host:
            continue

        follow_ups = events[
            (events["host_norm"] == target_host)
            & (events["event_id_norm"].isin(D5_FOLLOW_UP_EVENTS))
            & (events["timestamp"] > row.timestamp)
            & (events["timestamp"] <= row.timestamp + D5_WINDOW)
        ]
        if follow_ups.empty:
            continue

        follow_up_types = ", ".join(sorted(set(follow_ups["event_id_norm"].tolist())))
        findings.append(
            build_finding(
                code="D5",
                category="lateral-movement",
                title=f"Movimiento lateral hacia {target_host} desde {source_host}",
                rows=pd.concat([logons.iloc[[position]], follow_ups]),
                severity_hint="high",
                rationale=(
                    f"Inicio de sesión remoto (4624, LogonType={int(row.logon_type)}) de "
                    f"«{text(row.user_norm)}» en {target_host} a las {hhmmss(row.timestamp)}, con "
                    f"origen declarado {source_host}, distinto del equipo de destino. Le siguen "
                    f"{len(follow_ups)} acceso(s) a recursos ({follow_up_types}) en {target_host} "
                    f"dentro de los {int(D5_WINDOW.total_seconds() // 60)} minutos siguientes. La "
                    f"atribución del salto proviene del texto del evento, no de Source_IP."
                ),
                key=(
                    f"{slug(text(row.user_norm))}@{slug(source_host)}@{slug(target_host)}"
                    f"@{compact(row.timestamp)}"
                ),
            )
        )
    return findings
