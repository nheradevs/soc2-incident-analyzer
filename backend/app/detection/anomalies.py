"""D6: other anomalies — rarity, bulk object reads and out-of-window persistence.

Two calibrations of FSD §6 live here:

* bulk reads are reported with `requires_validation=True`, because `backupsvc`
  also reads Finance legitimately: the detector flags the pattern, not a verdict;
* the description-rarity rule skips `4698`/`7045`, which the persistence rule
  already reports, so one event is never reported twice by the same detector.
"""

from __future__ import annotations

from datetime import time

import pandas as pd

from app.detection.context import (
    build_finding,
    by_event,
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

RARITY_EXCLUDED_EVENTS = ("4698", "7045")

BULK_EVENTS = ("4663",)
BULK_MIN_OBJECTS = 11  # strictly more than 10 objects
BULK_WINDOW = pd.Timedelta(minutes=5)

PERSISTENCE_EVENTS = ("4698", "7045")
PERSISTENCE_LABEL = {
    "4698": "tarea programada creada",
    "7045": "servicio instalado en el sistema",
}
MAINTENANCE_WINDOW = (time(2, 0), time(6, 0))


def _rarity(events: pd.DataFrame) -> list[Finding]:
    counts = events["Event_Description"].value_counts()
    unique = {description for description, count in counts.items() if count == 1}
    if not unique:
        return []

    rows = selection(
        events,
        events["Event_Description"].isin(unique)
        & ~events["event_id_norm"].isin(RARITY_EXCLUDED_EVENTS),
    )
    total = count_es(len(events))
    findings: list[Finding] = []
    for position, row in enumerate(rows.itertuples()):
        description = text(row.Event_Description)
        findings.append(
            build_finding(
                code="D6",
                category="other-anomaly",
                title=f"Evento {text(row.event_id_norm)} con descripción única en el export",
                rows=rows.iloc[[position]],
                severity_hint="low",
                rationale=(
                    f"El texto «{description}» aparece una sola vez en los {total} eventos del "
                    f"export ({text(row.event_id_norm)}, equipo {text(row.host_norm)}, cuenta "
                    f"«{text(row.user_norm) or 'sin identificar'}», {hhmmss(row.timestamp)}). La "
                    f"rareza de la descripción solo indica que el evento se aparta del resto: hay "
                    f"que leerlo en contexto antes de concluir nada."
                ),
                key=f"{slug(description)[:40]}@{compact(row.timestamp)}",
            )
        )
    return findings


def _objects(rows: pd.DataFrame) -> pd.DataFrame:
    """Only rows that name the object can be counted as distinct objects."""
    named = rows["file_path"].map(lambda value: bool(text(value)))
    return rows[named].reset_index(drop=True)


def _bulk_reads(events: pd.DataFrame) -> list[Finding]:
    reads = _objects(by_event(events, BULK_EVENTS))
    if reads.empty:
        return []

    findings: list[Finding] = []
    for user, group in reads.groupby("user_norm", sort=True):
        if not text(user):
            continue
        rows = group.reset_index(drop=True)
        keys = [text(value) for value in rows["file_path"].tolist()]
        timestamps = rows["timestamp"].tolist()
        index = 0
        while index < len(timestamps):
            end = window_end(timestamps, index, BULK_WINDOW)
            window = rows.iloc[index : end + 1]
            objects = len(set(keys[index : end + 1]))
            if objects >= BULK_MIN_OBJECTS:
                block_start = window["timestamp"].iloc[0]
                block_end = window["timestamp"].iloc[-1]
                host = text(window["host_norm"].iloc[0])
                findings.append(
                    build_finding(
                        code="D6",
                        category="other-anomaly",
                        title="Lectura masiva y regular de objetos",
                        rows=window,
                        severity_hint="medium",
                        requires_validation=True,
                        rationale=(
                            f"{count_es(objects)} objetos distintos accedidos (4663) por la cuenta "
                            f"«{text(user)}» en {host} entre {hhmmss(block_start)} y "
                            f"{hhmmss(block_end)} ({minutes_between(block_start, block_end)} min), "
                            f"en {count_es(len(window))} eventos. El mismo patrón lo produce una "
                            f"herramienta de backup legítima sobre el mismo recurso: requiere "
                            f"validación antes de tratarlo como exfiltración."
                        ),
                        key=f"{slug(text(user))}@{slug(host)}@{compact(block_start)}",
                    )
                )
                index = end + 1
            else:
                index += 1
    return findings


def _persistence(events: pd.DataFrame) -> list[Finding]:
    created = by_event(events, PERSISTENCE_EVENTS)
    if created.empty:
        return []

    start, end = MAINTENANCE_WINDOW
    findings: list[Finding] = []
    for position, row in enumerate(created.itertuples()):
        moment = row.timestamp.time()
        if start <= moment <= end:
            continue
        detail_parts = [
            f"{label}={text(value)}"
            for label, value in (
                ("TaskName", row.task_name),
                ("ServiceName", row.service_name),
                ("ImagePath", row.image_path),
            )
            if text(value)
        ]
        detail = f" Detalle registrado: {'; '.join(detail_parts)}." if detail_parts else ""
        findings.append(
            build_finding(
                code="D6",
                category="other-anomaly",
                title="Persistencia creada fuera de la ventana de mantenimiento",
                rows=created.iloc[[position]],
                severity_hint="high",
                rationale=(
                    f"Evento {text(row.event_id_norm)} "
                    f"({PERSISTENCE_LABEL.get(text(row.event_id_norm), 'persistencia')}) en "
                    f"{text(row.host_norm)} a las {hhmmss(row.timestamp)} por la cuenta "
                    f"«{text(row.user_norm) or 'sin identificar'}», fuera de la ventana de "
                    f"mantenimiento declarada ({start:%H:%M}–{end:%H:%M}).{detail} El evento crea "
                    f"ejecución automática; los registros no muestran qué ejecuta el binario "
                    f"instalado."
                ),
                key=f"{slug(text(row.event_id_norm))}@{compact(row.timestamp)}",
            )
        )
    return findings


def d6_anomalies(events: pd.DataFrame | None) -> list[Finding]:
    if events is None or events.empty:
        return []
    return [*_rarity(events), *_bulk_reads(events), *_persistence(events)]
