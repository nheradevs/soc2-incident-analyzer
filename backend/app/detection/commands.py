"""D4: suspicious commands and processes (blacklist over `command_norm`).

The export redacts encoded payloads at the source (`[REDACTED_SYNTHETIC]`,
`<base64_redacted>`), so a finding may say that a payload is encoded and unknown,
never what it did (FSD §7.4).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import partial
from typing import Any

import pandas as pd

from app.detection.context import (
    build_finding,
    chain,
    compact,
    count_es,
    hhmmss,
    selection,
    slug,
    text,
)
from app.detection.models import Finding


@dataclass(frozen=True, slots=True)
class CommandPattern:
    key: str
    title: str
    pattern: re.Pattern[str]
    severity_hint: str
    requires_validation: bool
    note: str


_PATTERNS: tuple[CommandPattern, ...] = (
    CommandPattern(
        key="powershell-codificado",
        title="PowerShell con comando codificado",
        pattern=re.compile(r"-enc\b|-encodedcommand", re.IGNORECASE),
        severity_hint="high",
        requires_validation=False,
        note=(
            "El payload está codificado y redactado en el origen: no es posible determinar qué "
            "ejecutaba el comando."
        ),
    ),
    CommandPattern(
        key="vssadmin-delete-shadows",
        title="Eliminación de copias de sombra con vssadmin",
        pattern=re.compile(r"vssadmin(?:\.exe)?\s+delete\s+shadows", re.IGNORECASE),
        severity_hint="high",
        requires_validation=True,
        note=(
            "La eliminación de copias de sombra es compatible con herramientas de backup "
            "legítimas, por lo que requiere validación antes de concluir un compromiso."
        ),
    ),
    CommandPattern(
        key="net-view",
        title="Enumeración de recursos compartidos con net view",
        pattern=re.compile(r"net(?:\.exe)?\s+view\b", re.IGNORECASE),
        severity_hint="medium",
        requires_validation=False,
        note="La enumeración de recursos compartidos se usa para elegir el siguiente objetivo.",
    ),
    CommandPattern(
        key="whoami",
        title="Ejecución de whoami",
        pattern=re.compile(r"\bwhoami\b", re.IGNORECASE),
        severity_hint="medium",
        requires_validation=False,
        note="El comando identifica la cuenta con la que se ejecuta el proceso.",
    ),
    CommandPattern(
        key="archivo-comprimido",
        title="Creación de archivo comprimido en ruta pública",
        pattern=re.compile(
            r"(?=.*\b(?:7z|tar)(?:\.exe)?\b)(?=.*c:\\(?:users\\public|temp)\\)",
            re.IGNORECASE,
        ),
        severity_hint="high",
        requires_validation=False,
        note=(
            "Comprimir información hacia una carpeta pública es un paso habitual de preparación "
            "de exfiltración; los registros no muestran qué se hizo después con el archivo."
        ),
    ),
    CommandPattern(
        key="programdata",
        title="Ejecución desde C:\\ProgramData",
        pattern=re.compile(r"c:\\programdata\\", re.IGNORECASE),
        severity_hint="medium",
        requires_validation=False,
        note=(
            "C:\\ProgramData es una ruta escribible por usuarios sin privilegios y se usa para "
            "ocultar ejecutables y scripts."
        ),
    ),
)

_IIS_PRINCIPAL = re.compile(r"^IIS APPPOOL\\", re.IGNORECASE)
_IIS_PARENT_IN_TEXT = re.compile(r"parent=IIS APPPOOL\\", re.IGNORECASE)

# A process row proves that a process started; it does not prove that the page
# which started it answered. When the frame also holds the successful request to
# a server-side script on the same host shortly before the process, that request
# is the evidence that the shell endpoint was reachable and executed, so the
# finding must cite it instead of resting on one row.
SHELL_REQUEST_LOOKBACK = pd.Timedelta(minutes=15)

# A request path with one of these suffixes reaches executable server code, so a
# 2xx answer means the script ran (FSD §4.3: IIS `Result` is `result_norm`).
_EXECUTABLE_PAGE_SUFFIXES = (
    ".aspx",
    ".asp",
    ".ashx",
    ".asmx",
    ".ascx",
    ".php",
    ".php5",
    ".jsp",
    ".jspx",
    ".do",
    ".action",
    ".cgi",
    ".pl",
)


def _executable_page(command: str) -> bool:
    path = command.strip().split("?", 1)[0].split("#", 1)[0].lower()
    return path.endswith(_EXECUTABLE_PAGE_SUFFIXES)


def _successful_page_requests(events: pd.DataFrame) -> pd.DataFrame:
    """Web rows that reached executable server code and answered 2xx."""
    web = selection(events, events["event_family"] == "web")
    if web.empty:
        return web
    mask = (web["result_norm"] == "http_2xx") & web["command_norm"].map(
        lambda value: _executable_page(text(value))
    )
    return selection(web, mask)


def _shell_request(requests: pd.DataFrame, host: str, process_start: Any) -> pd.DataFrame:
    """Nearest successful request to a server-side script before the process."""
    if requests.empty:
        return requests
    same_host = requests["host_norm"] == host
    lookback = (requests["timestamp"] < process_start) & (
        process_start - requests["timestamp"] <= SHELL_REQUEST_LOOKBACK
    )
    candidates = selection(requests, same_host & lookback)
    return candidates.iloc[-1:] if not candidates.empty else candidates


def _shell_request_note(request: pd.Series) -> str:
    return (
        f" La solicitud «{text(request['command_norm'])}» ({request['Log_ID']}) alcanzó un "
        f"script del servidor y respondió {text(request['Result'])} a las "
        f"{hhmmss(request['timestamp'])}: el endpoint de la web shell respondió, aunque el "
        f"registro no muestra qué devolvió."
    )


def _matches(command: str, pattern: CommandPattern) -> bool:
    return bool(pattern.pattern.search(command))


def _quote(block: pd.DataFrame) -> str:
    if bool(block["payload_redacted"].any()):
        return ""
    command = text(block["command_norm"].iloc[0])
    return f" Línea de comandos registrada: «{command}»." if command else ""


def _match_mask(events: pd.DataFrame, pattern: CommandPattern) -> pd.Series:
    matcher = partial(_matches, pattern=pattern)
    return events["command_norm"].map(lambda value: matcher(text(value)))


def _finding_for(
    pattern: CommandPattern,
    block: pd.DataFrame,
    user: str,
    host: str,
) -> Finding:
    validation = (
        " Requiere validación humana." if pattern.requires_validation else ""
    )
    return build_finding(
        code="D4",
        category="command-execution",
        title=pattern.title,
        rows=block,
        severity_hint=pattern.severity_hint,
        requires_validation=pattern.requires_validation,
        rationale=(
            f"{pattern.title}: {count_es(len(block))} evento(s) en {host} por "
            f"«{user or 'cuenta no identificada'}» entre {hhmmss(block['timestamp'].iloc[0])} y "
            f"{hhmmss(block['timestamp'].iloc[-1])}.{_quote(block)} {pattern.note}{validation}"
        ),
        key=(
            f"{pattern.key}@{slug(user or 'anonimo')}@{slug(host)}"
            f"@{compact(block['timestamp'].iloc[0])}"
        ),
    )


def _iis_spawned_processes(events: pd.DataFrame) -> list[Finding]:
    processes = selection(events, events["event_id_norm"] == "4688")
    if processes.empty:
        return []

    masks = [
        processes["user_norm"].map(lambda value: bool(_IIS_PRINCIPAL.match(text(value)))),
        processes["Event_Description"].map(
            lambda value: bool(_IIS_PARENT_IN_TEXT.search(text(value)))
        ),
    ]
    mask = masks[0]
    for extra in masks[1:]:
        mask = mask | extra
    matched = selection(processes, mask)
    if matched.empty:
        return []

    findings: list[Finding] = []
    shell_requests = _successful_page_requests(events)
    for (user, host), group in matched.groupby(["user_norm", "host_norm"], sort=True):
        for block in chain(group.reset_index(drop=True)):
            request = _shell_request(shell_requests, text(host), block["timestamp"].iloc[0])
            rows = block
            note = ""
            if not request.empty:
                rows = pd.concat([request, block], ignore_index=True)
                note = _shell_request_note(request.iloc[0])
            findings.append(
                build_finding(
                    code="D4",
                    category="command-execution",
                    title="Proceso creado por el grupo de aplicaciones de IIS",
                    rows=rows,
                    severity_hint="critical",
                    rationale=(
                        f"Proceso creado (4688) en {text(host)} por el principal de IIS "
                        f"«{text(user)}» a las {hhmmss(block['timestamp'].iloc[0])}; "
                        f"{count_es(len(rows))} evento(s) en total.{_quote(block)}{note} Un "
                        f"servidor web no debería lanzar procesos interactivos, así que el "
                        f"evento es compatible con la ejecución de una web shell. Los registros "
                        f"muestran el proceso lanzado, no el contenido de la página que lo "
                        f"provocó."
                    ),
                    key=(
                        f"{slug(text(user))}@{slug(text(host))}"
                        f"@{compact(block['timestamp'].iloc[0])}"
                    ),
                )
            )
    return findings


def d4_command_execution(events: pd.DataFrame | None) -> list[Finding]:
    if events is None or events.empty:
        return []

    findings: list[Finding] = []
    for pattern in _PATTERNS:
        matched = selection(events, _match_mask(events, pattern))
        if matched.empty:
            continue
        for (user, host), group in matched.groupby(["user_norm", "host_norm"], sort=True):
            for block in chain(group.reset_index(drop=True)):
                findings.append(_finding_for(pattern, block, text(user), text(host)))
    findings.extend(_iis_spawned_processes(events))
    return findings
