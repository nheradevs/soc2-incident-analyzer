"""D2: suspicious successful logons.

Two signals are available in this export: a `4624` whose source is an external IP
and a `4624` on an administrative account. The third signal of the design
("logon outside business hours") is **not detectable here**: the workbook has no
business-hour baseline and a single 6-hour window of one day, so any hour rule
would be invented. It is declared as a limitation instead of faked (FSD §7.4).
"""

from __future__ import annotations

import pandas as pd

from app.detection.context import build_finding, by_event, compact, hhmmss, slug, text
from app.detection.models import Finding

PRIVILEGED_ACCOUNTS = frozenset({"admin", "administrator"})


def d2_suspicious_logons(events: pd.DataFrame | None) -> list[Finding]:
    logons = by_event(events, ("4624",))
    if logons.empty:
        return []

    findings: list[Finding] = []
    for position, row in enumerate(logons.itertuples()):
        account = text(row.user_norm)
        external = text(row.ip_class) == "external"
        privileged = account.lower() in PRIVILEGED_ACCOUNTS

        reasons: list[str] = []
        if external:
            reasons.append(f"origen externo {text(row.Source_IP)}")
        if privileged:
            reasons.append(f"cuenta administrativa «{account}»")
        if not reasons:
            continue

        logon_type = ""
        if not pd.isna(row.logon_type):
            logon_type = f" LogonType={int(row.logon_type)}."
        findings.append(
            build_finding(
                code="D2",
                category="suspicious-logon",
                title=(
                    f"Inicio de sesión sospechoso de "
                    f"{account or 'cuenta no identificada'} en {text(row.host_norm)}"
                ),
                rows=logons.iloc[[position]],
                severity_hint="high" if external else "medium",
                rationale=(
                    f"Inicio de sesión exitoso (4624) de "
                    f"«{account or 'cuenta no identificada'}» en {text(row.host_norm)} a las "
                    f"{hhmmss(row.timestamp)} por {' y '.join(reasons)}.{logon_type} La línea base "
                    f"medida solo contiene logons internos de cuentas nominales, de modo que este "
                    f"evento se aparta de ella."
                ),
                key=f"{slug(account or text(row.Source_IP))}@{compact(row.timestamp)}",
            )
        )
    return findings
