"""Free-text extraction (FSD §4.7).

The export carries its semantics inside two prose columns, with no dedicated
fields for logon type, lateral source, share, task, service, byte counts or
URI. This module recovers what is recoverable and leaves the rest missing:
an invented value would read as evidence.

Both prose columns are searched: `Event_Description` holds the Windows event
narrative (`LogonType=10; RDP`, `source=APP-SRV01`) while
`Process_CommandLine` carries the structured payload of task and service
events (`TaskName=...`, `ServiceName=...`, `ImagePath=...`).
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

_LOGON_TYPE = re.compile(r"LogonType=(\d+)")
_LATERAL_SOURCE = re.compile(r"source=([A-Za-z0-9._-]+)")
_BYTES_OUT = re.compile(r"bytes_out=(\d+)")
_URI = re.compile(r"uri=(\S+)")
_TASK_NAME = re.compile(r"TaskName=([^;]+)")
_SCRIPT_PATH = re.compile(r"-File\s+([^;\s]+)")
_SERVICE_NAME = re.compile(r"ServiceName=([^;]+)")
_IMAGE_PATH = re.compile(r"ImagePath=([^;]+)")
_SHARE_FILE = re.compile(r"file share access:\s*(.+)$", re.IGNORECASE)
_FILE_ACCESS = re.compile(r"^File access:\s*(.+)$", re.IGNORECASE)
_UNC = re.compile(r"^\\\\[^\\]+\\[^\\]+")
_REDACTED = re.compile(r"redacted", re.IGNORECASE)

FIELD_COLUMNS = (
    "logon_type",
    "lateral_source",
    "task_name",
    "service_name",
    "image_path",
    "file_path",
    "command_norm",
    "bytes_out",
    "uri",
    "script_path",
    "payload_redacted",
    "share",
)


def _text(value: Any) -> str:
    return "" if value is None or pd.isna(value) else str(value).strip()


def _search(pattern: re.Pattern[str], *values: Any) -> str | None:
    for value in values:
        match = pattern.search(_text(value))
        if match:
            return match.group(1).strip()
    return None


def _file_path(description: Any, command: Any) -> str | None:
    found = _search(_SHARE_FILE, description)
    if found is not None:
        return found
    match = _FILE_ACCESS.match(_text(command))
    return match.group(1).strip() if match else None


def _share(destination: Any) -> str | None:
    match = _UNC.match(_text(destination))
    return match.group(0) if match else None


def _row_fields(description: Any, command: Any, destination: Any) -> dict[str, Any]:
    logon_type = _search(_LOGON_TYPE, description)
    bytes_out = _search(_BYTES_OUT, command)
    return {
        "logon_type": None if logon_type is None else int(logon_type),
        "lateral_source": _search(_LATERAL_SOURCE, description),
        "task_name": _search(_TASK_NAME, command, description),
        "service_name": _search(_SERVICE_NAME, command, description),
        "image_path": _search(_IMAGE_PATH, command, description),
        "file_path": _file_path(description, command),
        "command_norm": _text(command),
        "bytes_out": None if bytes_out is None else int(bytes_out),
        "uri": _search(_URI, command),
        "script_path": _search(_SCRIPT_PATH, command),
        # FSD §7.4: payloads are redacted at the source, so they cannot be read.
        "payload_redacted": bool(_REDACTED.search(_text(command))),
        "share": _share(destination),
    }


def parse(df: pd.DataFrame) -> pd.DataFrame:
    """Add the semantic columns extracted from the prose columns of a SIEM export."""
    descriptions = df["Event_Description"] if "Event_Description" in df else [None] * len(df)
    commands = df["Process_CommandLine"] if "Process_CommandLine" in df else [None] * len(df)
    destinations = df["Destination"] if "Destination" in df else [None] * len(df)

    extracted = pd.DataFrame(
        [
            _row_fields(description, command, destination)
            for description, command, destination in zip(
                descriptions, commands, destinations, strict=True
            )
        ],
        index=df.index,
    )
    extracted["logon_type"] = extracted["logon_type"].astype("Int64")
    extracted["bytes_out"] = extracted["bytes_out"].astype("Int64")

    return pd.concat([df, extracted], axis=1)
