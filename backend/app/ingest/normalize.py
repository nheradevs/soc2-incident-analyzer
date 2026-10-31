"""Structural normalization of a SIEM export (FSD §4, traps 4.1-4.6 and 4.8).

The rules here never drop or rewrite the original columns: they only add
derived ones, so every finding can still cite the exact row it came from.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any

import pandas as pd

_WINDOWS_FAMILY_EVENT = re.compile(r"^\d+$")
_EVENT_FAMILY_BY_NAME = {"PROXY_ACCESS": "proxy", "HTTP_ACCESS": "web"}

_HTTP_RESULT = re.compile(r"^([1-5])\d{2}$")
_RESULT_BY_NAME = {"success": "success", "failure": "failure", "allowed": "allowed"}

_HOST_NOISE = re.compile(r"[^A-Z0-9]")
_LOGON_NAME = re.compile(r"^(?:IIS APPPOOL|NT AUTHORITY|NT SERVICE)\\")
_MACHINE_USER = re.compile(r"\$$")

_PRIVATE_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)


def _text(value: Any) -> str:
    return "" if value is None or pd.isna(value) else str(value).strip()


def host_norm(value: Any) -> str:
    """Collapse hostname spellings: `DC-01`, `DC01` and `dc01` are one entity."""
    return _HOST_NOISE.sub("", _text(value).upper())


def _host_or_ip(value: str) -> str:
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return host_norm(value)


def event_id_norm(value: Any) -> str:
    """Trap 4.1: `Event_ID` is int for Windows events and str for other sources."""
    return _text(value)


def event_family(value: Any) -> str:
    raw = event_id_norm(value)
    if _WINDOWS_FAMILY_EVENT.match(raw):
        return "windows"
    return _EVENT_FAMILY_BY_NAME.get(raw.upper(), "other")


def result_norm(value: Any) -> str:
    """Trap 4.3: Security sends verdicts, IIS sends codes, Proxy sends verdicts."""
    raw = _text(value).lower()
    if raw in _RESULT_BY_NAME:
        return _RESULT_BY_NAME[raw]
    match = _HTTP_RESULT.match(raw)
    if match:
        return f"http_{match.group(1)}xx"
    return "other"


def _is_failure(normalized: str) -> bool:
    return normalized in {"failure", "http_4xx", "http_5xx"}


def principal_type(value: Any) -> str:
    """Trap 4.5: `-` and service principals are not people."""
    raw = _text(value)
    if raw in {"", "-"}:
        return "anonymous"
    if _LOGON_NAME.match(raw) or _MACHINE_USER.search(raw):
        return "machine"
    return "human"


def user_norm(value: Any) -> str:
    raw = _text(value)
    if principal_type(raw) == "human":
        return raw.split("\\")[-1]
    return "" if principal_type(raw) == "anonymous" else raw


def ip_class(value: Any) -> str:
    """Trap 4.8: only the address family is knowable, never the hostname."""
    raw = _text(value)
    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        return "unknown"
    if any(address in network for network in _PRIVATE_NETWORKS):
        return "internal"
    return "external"


def _split_destination(value: Any) -> tuple[str, str, int | None]:
    """Trap 4.6: `Destino` mixes host, host:port, ip:port and UNC shares."""
    raw = _text(value)
    if not raw:
        return "none", "", None

    if raw.startswith("\\\\"):
        parts = [segment for segment in raw.lstrip("\\").split("\\") if segment]
        return "share", host_norm(parts[0]) if parts else "", None

    if ":" in raw:
        host, _, port = raw.rpartition(":")
        if port.isdigit():
            return "endpoint", _host_or_ip(host), int(port)

    return "host", _host_or_ip(raw), None


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Add the derived columns every downstream rule depends on."""
    result = df.copy()

    if "Event_ID" in result:
        result["event_id_norm"] = result["Event_ID"].map(event_id_norm)
        result["event_family"] = result["Event_ID"].map(event_family)
    if "Timestamp" in result:
        result["timestamp"] = pd.to_datetime(result["Timestamp"], errors="coerce")
    if "Hostname" in result:
        result["host_norm"] = result["Hostname"].map(host_norm)
    if "User" in result:
        result["principal_type"] = result["User"].map(principal_type)
        result["user_norm"] = result["User"].map(user_norm)
    if "Source_IP" in result:
        result["ip_class"] = result["Source_IP"].map(ip_class)
    if "Destination" in result:
        split = result["Destination"].map(_split_destination)
        result["dest_type"] = split.map(lambda item: item[0])
        result["dest_host"] = split.map(lambda item: item[1])
        result["dest_port"] = pd.array([item[2] for item in split], dtype="Int64")
    if "Result" in result:
        result["result_norm"] = result["Result"].map(result_norm)
        result["is_failure"] = result["result_norm"].map(_is_failure)

    return result
