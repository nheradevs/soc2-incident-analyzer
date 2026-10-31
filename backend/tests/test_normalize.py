"""Normalization contract (FSD §4).

Each test pins one data trap from the FSD. If one of these regresses, a
detector silently stops seeing the attack, so they are deliberately explicit
about the exact trap they cover.
"""

import pandas as pd
import pytest

from app.ingest.normalize import normalize


def frame(**columns: list) -> pd.DataFrame:
    """Build a minimal one-column-per-key frame with a valid row count."""
    width = len(next(iter(columns.values())))
    base = {name: [None] * width for name in ("Log_ID", "Timestamp", "Hostname")}
    for index in range(width):
        base["Log_ID"][index] = f"EVT-{index:05d}"
        base["Timestamp"][index] = "2026-10-23 07:46:07"
        base["Hostname"][index] = "WS-018"
    base.update(columns)
    return pd.DataFrame(base)


def test_trap_4_1_event_id_is_always_text() -> None:
    """Event_ID arrives as int *and* str; a type mismatch returns zero rows."""
    df = frame(Event_ID=[4625, "PROXY_ACCESS", " HTTP_ACCESS"])

    result = normalize(df)

    assert result["event_id_norm"].tolist() == ["4625", "PROXY_ACCESS", "HTTP_ACCESS"]
    assert result["event_family"].tolist() == ["windows", "proxy", "web"]


def test_trap_4_2_timestamp_becomes_datetime() -> None:
    """Timestamp arrives as object; correlation needs real datetimes."""
    df = frame(Timestamp=["2026-10-23 07:46:07", "2026-10-23 13:44:06"])

    result = normalize(df)

    assert result["timestamp"].dtype.kind == "M"
    assert result["timestamp"].iloc[0].hour == 7
    assert result["timestamp"].iloc[1].hour == 13


def test_trap_4_3_result_semantics_are_unified_per_source() -> None:
    """Result mixes Success/Failure, HTTP codes and Proxy verdicts."""
    df = frame(Result=["Success", "Failure", "200", "404", "500", "Allowed"])

    result = normalize(df)

    assert result["result_norm"].tolist() == [
        "success",
        "failure",
        "http_2xx",
        "http_4xx",
        "http_5xx",
        "allowed",
    ]
    assert result["is_failure"].tolist() == [False, True, False, True, True, False]


def test_trap_4_4_dc_host_spellings_collapse_to_one_entity() -> None:
    """`DC-01` and `DC01` are the same machine."""
    df = frame(Hostname=["DC-01", "DC01", "dc01", "WS-018"])

    result = normalize(df)

    assert result["host_norm"].tolist()[:3] == ["DC01", "DC01", "DC01"]
    assert result["host_norm"].tolist()[3] == "WS018"


def test_trap_4_5_principal_type_separates_humans_from_specials() -> None:
    """`-` is anonymous and `IIS APPPOOL\\*` is a machine account, not a person."""
    df = frame(
        User=["CORP\\jlopez", "-", "IIS APPPOOL\\DefaultAppPool", "CORP\\backupsvc"]
    )

    result = normalize(df)

    assert result["principal_type"].tolist() == ["human", "anonymous", "machine", "human"]
    assert result["user_norm"].tolist() == [
        "jlopez",
        "",
        "IIS APPPOOL\\DefaultAppPool",
        "backupsvc",
    ]


def test_trap_4_6_destination_is_split_into_type_host_and_port() -> None:
    """Destination mixes hostnames, host:port, ip:port and UNC paths."""
    df = frame(
        Destination=[
            "DC-01",
            "WEB-01:443",
            "203.0.113.88:443",
            "\\\\FS-SRV01\\Finance",
            None,
        ]
    )

    result = normalize(df)

    assert result["dest_type"].tolist() == ["host", "endpoint", "endpoint", "share", "none"]
    assert result["dest_host"].tolist() == ["DC01", "WEB01", "203.0.113.88", "FSSRV01", ""]
    assert result["dest_port"].isna().tolist() == [True, False, False, True, True]
    assert result["dest_port"].iloc[1] == 443
    assert result["dest_port"].iloc[2] == 443


@pytest.mark.parametrize(
    ("source_ip", "expected"),
    [
        ("10.10.1.22", "internal"),
        ("10.10.3.18", "internal"),
        ("198.51.100.77", "external"),
        ("203.0.113.74", "external"),
        ("192.0.2.91", "external"),
    ],
)
def test_trap_4_8_ip_class_flags_every_non_rfc1918_source(
    source_ip: str, expected: str
) -> None:
    """Traffic from outside the corporate ranges is the real discriminator."""
    result = normalize(frame(Source_IP=[source_ip]))

    assert result["ip_class"].iloc[0] == expected


def test_trap_4_8_does_not_invent_host_from_ip() -> None:
    """Source_IP never resolves to a hostname: the column must not be faked."""
    result = normalize(frame(Source_IP=["10.10.2.15"]))

    assert "source_host" not in result.columns


def test_normalize_keeps_original_columns_untouched() -> None:
    """Derived columns are additive: evidence must stay citable verbatim."""
    df = frame(Event_ID=[4625], Hostname=["DC-01"])

    result = normalize(df)

    assert result["Event_ID"].iloc[0] == 4625
    assert result["Hostname"].iloc[0] == "DC-01"
