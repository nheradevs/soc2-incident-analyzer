"""D1a-D1d: brute force, password spray, external exposure, post-compromise logon.

Thresholds come from the measured baseline (FSD §6), not from taste: the normal
traffic of the export never puts more than 2 failures on one account inside 10
minutes, and never fails a logon from an external IP at all. That is why D1c
exists separately from D1a: the RDP attack in INC-2 has only 4 attempts, so a
pure counting rule would miss it, while "external origin" flags it on the first
failure.
"""

from __future__ import annotations

import pandas as pd

from app.detection.context import (
    build_finding,
    by_event,
    chain,
    compact,
    count_es,
    hhmmss,
    minutes_between,
    slug,
    text,
    window_end,
)
from app.detection.models import Finding

D1A_WINDOW = pd.Timedelta(minutes=10)
D1A_MIN_FAILURES = 3

D1B_WINDOW = pd.Timedelta(minutes=15)
D1B_MIN_FAILURES = 5
D1B_MIN_ACCOUNTS = 3

D1D_WINDOW = pd.Timedelta(minutes=15)


def _failures(events: pd.DataFrame | None) -> pd.DataFrame:
    return by_event(events, ("4625",))


def _origins(rows: pd.DataFrame) -> str:
    origins = sorted({text(value) for value in rows["Source_IP"].tolist()} - {""})
    return ", ".join(origins) if origins else "origen no registrado"


def d1a_directed_brute_force(events: pd.DataFrame | None) -> list[Finding]:
    """≥3 failed logons (4625) for the same account inside 10 minutes."""
    failures = _failures(events)
    if failures.empty:
        return []

    findings: list[Finding] = []
    for user, group in failures.groupby("user_norm", sort=True):
        if not text(user):
            continue
        rows = group.reset_index(drop=True)
        timestamps = rows["timestamp"].tolist()
        index = 0
        while index < len(timestamps):
            end = window_end(timestamps, index, D1A_WINDOW)
            block = rows.iloc[index : end + 1]
            if len(block) >= D1A_MIN_FAILURES:
                block_start = block["timestamp"].iloc[0]
                block_end = block["timestamp"].iloc[-1]
                findings.append(
                    build_finding(
                        code="D1a",
                        category="brute-force",
                        title=f"Fuerza bruta dirigida contra la cuenta {user}",
                        rows=block,
                        severity_hint="high",
                        rationale=(
                            f"{count_es(len(block))} inicios de sesión fallidos (4625) sobre la "
                            f"cuenta «{user}» entre {hhmmss(block_start)} y {hhmmss(block_end)} "
                            f"({minutes_between(block_start, block_end)} min), desde "
                            f"{_origins(block)}. Umbral: ≥{D1A_MIN_FAILURES} fallos de la misma "
                            f"cuenta en {int(D1A_WINDOW.total_seconds() // 60)} min."
                        ),
                        key=f"{slug(user)}@{compact(block_start)}",
                    )
                )
                index = end + 1
            else:
                index += 1
    return findings


def d1b_password_spray(events: pd.DataFrame | None) -> list[Finding]:
    """≥5 failed logons from one external IP against ≥3 accounts inside 15 minutes."""
    failures = _failures(events)
    if failures.empty:
        return []

    external = failures[failures["ip_class"] == "external"]
    if external.empty:
        return []

    findings: list[Finding] = []
    for source_ip, group in external.groupby("Source_IP", sort=True):
        rows = group.reset_index(drop=True)
        timestamps = rows["timestamp"].tolist()
        index = 0
        while index < len(timestamps):
            end = window_end(timestamps, index, D1B_WINDOW)
            block = rows.iloc[index : end + 1]
            accounts = sorted({text(value) for value in block["user_norm"].tolist()} - {""})
            if len(block) < D1B_MIN_FAILURES or len(accounts) < D1B_MIN_ACCOUNTS:
                index += 1
                continue
            block_start = block["timestamp"].iloc[0]
            block_end = block["timestamp"].iloc[-1]
            findings.append(
                build_finding(
                    code="D1b",
                    category="brute-force",
                    title=(
                        f"Password spray desde {source_ip} contra "
                        f"{count_es(len(accounts))} cuentas"
                    ),
                    rows=block,
                    severity_hint="high",
                    rationale=(
                        f"{count_es(len(block))} inicios de sesión fallidos (4625) desde la IP "
                        f"externa {source_ip} contra {count_es(len(accounts))} cuentas distintas "
                        f"({', '.join(accounts)}) entre {hhmmss(block_start)} y "
                        f"{hhmmss(block_end)}. Umbral: ≥{D1B_MIN_FAILURES} fallos contra "
                        f"≥{D1B_MIN_ACCOUNTS} cuentas en "
                        f"{int(D1B_WINDOW.total_seconds() // 60)} min."
                    ),
                    key=f"{slug(source_ip)}@{compact(block_start)}",
                )
            )
            index = end + 1
    return findings


def d1c_external_exposure(events: pd.DataFrame | None) -> list[Finding]:
    """Any 4625 whose source is external, even when the count is low (FSD §6)."""
    failures = _failures(events)
    if failures.empty:
        return []

    external = failures[failures["ip_class"] == "external"]
    if external.empty:
        return []

    findings: list[Finding] = []
    for (source_ip, host), group in external.groupby(["Source_IP", "host_norm"], sort=True):
        for block in chain(group.reset_index(drop=True)):
            logon_types = sorted(
                {int(value) for value in block["logon_type"].tolist() if not pd.isna(value)}
            )
            detail = (
                f" LogonType observado: {', '.join(str(value) for value in logon_types)}."
                if logon_types
                else ""
            )
            findings.append(
                build_finding(
                    code="D1c",
                    category="brute-force",
                    title=f"Intento de inicio de sesión fallido desde la IP externa {source_ip}",
                    rows=block,
                    severity_hint="high",
                    rationale=(
                        f"{count_es(len(block))} inicio(s) de sesión fallido(s) (4625) desde la IP "
                        f"externa {source_ip} en el equipo {text(host)} entre "
                        f"{hhmmss(block['timestamp'].iloc[0])} y "
                        f"{hhmmss(block['timestamp'].iloc[-1])}. La línea base medida no registra "
                        f"ningún fallo desde una IP externa, así que el origen externo eleva la "
                        f"severidad aunque el conteo sea bajo.{detail}"
                    ),
                    key=f"{slug(source_ip)}@{slug(text(host))}@{compact(block['timestamp'].iloc[0])}",
                )
            )
    return findings


def d1d_post_compromise_logon(events: pd.DataFrame | None) -> list[Finding]:
    """A successful 4624 within 15 minutes after a D1a/D1b block, same IP/account."""
    failures = _failures(events)
    successes = by_event(events, ("4624",))
    if failures.empty or successes.empty:
        return []

    findings: list[Finding] = []
    for position, row in enumerate(successes.itertuples()):
        source_ip = text(row.Source_IP)
        account = text(row.user_norm)
        window_start = row.timestamp - D1D_WINDOW
        recent = failures[
            (failures["Source_IP"] == source_ip)
            & (failures["timestamp"] >= window_start)
            & (failures["timestamp"] <= row.timestamp)
        ]
        if recent.empty:
            continue

        own_failures = recent[recent["user_norm"] == account]
        accounts = {text(value) for value in recent["user_norm"].tolist()} - {""}
        directed = len(own_failures) >= D1A_MIN_FAILURES
        sprayed = len(recent) >= D1B_MIN_FAILURES and len(accounts) >= D1B_MIN_ACCOUNTS
        if not (directed or sprayed):
            continue

        if directed:
            basis = f"{count_es(len(own_failures))} fallos previos contra la misma cuenta"
        else:
            basis = (
                f"{count_es(len(recent))} fallos previos contra {count_es(len(accounts))} "
                f"cuentas (spray)"
            )
        gap_from_first = minutes_between(recent["timestamp"].iloc[0], row.timestamp)
        gap_from_last = minutes_between(recent["timestamp"].iloc[-1], row.timestamp)
        findings.append(
            build_finding(
                code="D1d",
                category="brute-force",
                title=f"Inicio de sesión exitoso después de fallos desde {source_ip}",
                rows=pd.concat([recent, successes.iloc[[position]]]),
                severity_hint="critical",
                rationale=(
                    f"Inicio de sesión exitoso (4624) de la cuenta «{account}» desde "
                    f"{source_ip} a las {hhmmss(row.timestamp)}, {gap_from_first} min después del "
                    f"primer fallo del bloque y a {gap_from_last} min del último: {basis}. Los "
                    f"registros muestran que el intento prosperó; no muestran qué se hizo con la "
                    f"sesión."
                ),
                key=f"{slug(account)}@{compact(row.timestamp)}",
            )
        )
    return findings
