"""Detection rules D1a-D7: thresholds, boundaries and the measured baseline (FSD §6).

Every rule is checked in both directions on a small synthetic frame: the exact
threshold fires, one step below it does not, and the measured baseline (FSD §6)
produces no finding at all. Frames go through the real ingest layers
(`normalize` + `parse`) so the detectors see exactly the columns they see on the
client export; no test here reads the real workbook.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from app.detection.anomalies import d6_anomalies
from app.detection.brute_force import (
    d1a_directed_brute_force,
    d1b_password_spray,
    d1c_external_exposure,
    d1d_post_compromise_logon,
)
from app.detection.commands import d4_command_execution
from app.detection.exfiltration import d7_exfiltration
from app.detection.lateral import d5_lateral_movement
from app.detection.logon import d2_suspicious_logons
from app.detection.privilege import d3_privilege_escalation
from app.ingest.normalize import normalize
from app.ingest.parse import parse

DAY = "2026-10-23"
EXTERNAL_IP = "203.0.113.74"
EXTERNAL_IP_2 = "198.51.100.77"
INTERNAL_IP = "10.10.1.22"

ALL_DETECTORS = (
    d1a_directed_brute_force,
    d1b_password_spray,
    d1c_external_exposure,
    d1d_post_compromise_logon,
    d2_suspicious_logons,
    d3_privilege_escalation,
    d4_command_execution,
    d5_lateral_movement,
    d6_anomalies,
    d7_exfiltration,
)


def frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Build a normalized frame from log rows, filling the columns they omit."""
    records = []
    for index, row in enumerate(rows):
        record: dict[str, Any] = {
            "Log_ID": f"EVT-{index + 1:05d}",
            "Timestamp": f"{DAY} 09:00:00",
            "Hostname": "DC-01",
            "Event_ID": 4624,
            "User": "CORP\\jlopez",
            "Source_IP": "10.10.1.10",
            "Destination": None,
            "Log_Source": "Security",
            "Event_Description": "An account was successfully logged on",
            "Process_CommandLine": None,
            "Result": "Success",
            "Severity": "Informational",
        }
        record.update(row)
        records.append(record)
    return parse(normalize(pd.DataFrame(records)))


def failed_logon(
    time: str,
    *,
    user: str = "jlopez",
    ip: str = INTERNAL_IP,
    host: str = "DC-01",
    logon_type: int | None = None,
) -> dict[str, Any]:
    description = "An account failed to log on"
    if logon_type is not None:
        description = f"An account failed to log on (LogonType={logon_type}; RDP)"
    return {
        "Timestamp": f"{DAY} {time}",
        "Hostname": host,
        "Event_ID": 4625,
        "User": f"CORP\\{user}",
        "Source_IP": ip,
        "Result": "Failure",
        "Event_Description": description,
    }


def successful_logon(
    time: str,
    *,
    user: str = "jlopez",
    ip: str = INTERNAL_IP,
    host: str = "DC-01",
    logon_type: int | None = None,
    source_host: str | None = None,
) -> dict[str, Any]:
    description = "An account was successfully logged on"
    if logon_type is not None:
        suffix = f"LogonType={logon_type}"
        if source_host is not None:
            suffix += f"; source={source_host}"
        description = f"An account was successfully logged on ({suffix})"
    return {
        "Timestamp": f"{DAY} {time}",
        "Hostname": host,
        "Event_ID": 4624,
        "User": f"CORP\\{user}",
        "Source_IP": ip,
        "Result": "Success",
        "Event_Description": description,
    }


def process(time: str, command: str, *, user: str = "jlopez", host: str = "APPSRV01") -> dict:
    return {
        "Timestamp": f"{DAY} {time}",
        "Hostname": host,
        "Event_ID": 4688,
        "User": f"CORP\\{user}",
        "Event_Description": "A new process has been created",
        "Process_CommandLine": command,
    }


def proxy(
    time: str,
    *,
    bytes_out: int,
    uri: str = "/upload/session/1",
    destination: str = "198.51.100.88:443",
) -> dict:
    return {
        "Timestamp": f"{DAY} {time}",
        "Hostname": "WS-018",
        "Event_ID": "PROXY_ACCESS",
        "User": "CORP\\rrojas",
        "Source_IP": "10.10.1.31",
        "Destination": destination,
        "Log_Source": "Proxy",
        "Event_Description": "HTTPS POST outbound",
        "Process_CommandLine": f"bytes_out={bytes_out} uri={uri}",
        "Result": "Allowed",
    }


def measured_baseline() -> pd.DataFrame:
    """The normal behaviour measured in the export (FSD §6): no rule may fire."""
    return frame(
        [
            failed_logon("08:10:00", user="jlopez", ip="10.10.1.22"),
            failed_logon("08:14:00", user="jlopez", ip="10.10.2.15"),
            failed_logon("09:10:00", user="aperez", ip="10.10.1.31"),
            successful_logon("08:12:00", user="jlopez", ip="10.10.1.22"),
            successful_logon("09:12:00", user="aperez", ip="10.10.1.31"),
            {
                "Timestamp": f"{DAY} 09:13:00",
                "Hostname": "WS-031",
                "Event_ID": 4672,
                "User": "CORP\\helpdesk",
                "Source_IP": "10.10.1.31",
                "Event_Description": "Special privileges assigned to new logon",
            },
            {
                "Timestamp": f"{DAY} 09:14:00",
                "Hostname": "APPSRV01",
                "Event_ID": 4672,
                "User": "CORP\\svc_backup",
                "Source_IP": "10.10.1.22",
                "Event_Description": "Special privileges assigned to new logon",
            },
            process("08:20:00", "explorer.exe"),
            process("08:21:00", "notepad.exe", user="aperez"),
            process("08:22:00", "svchost.exe", user="mruiz"),
            {
                "Timestamp": f"{DAY} 08:30:00",
                "Hostname": "FS-SRV01",
                "Event_ID": 4663,
                "User": "CORP\\backupsvc",
                "Event_Description": "An attempt was made to access an object",
            },
            {
                "Timestamp": f"{DAY} 08:35:00",
                "Hostname": "FS-SRV01",
                "Event_ID": 4663,
                "User": "CORP\\backupsvc",
                "Event_Description": "An attempt was made to access an object",
            },
            {
                "Timestamp": f"{DAY} 08:40:00",
                "Hostname": "FS-SRV01",
                "Event_ID": 4663,
                "User": "CORP\\backupsvc",
                "Event_Description": "An attempt was made to access an object",
            },
            {
                "Timestamp": f"{DAY} 09:00:00",
                "Hostname": "FS-SRV01",
                "Event_ID": 5140,
                "User": "CORP\\jlopez",
                "Event_Description": "A network share object was accessed",
            },
            {
                "Timestamp": f"{DAY} 09:30:00",
                "Hostname": "FS-SRV01",
                "Event_ID": 5140,
                "User": "CORP\\aperez",
                "Event_Description": "A network share object was accessed",
            },
            {
                "Timestamp": f"{DAY} 09:05:00",
                "Event_ID": 7036,
                "Log_Source": "System",
                "User": "CORP\\jlopez",
                "Event_Description": "Service entered running state",
            },
            {
                "Timestamp": f"{DAY} 09:15:00",
                "Event_ID": 7036,
                "Log_Source": "System",
                "User": "CORP\\aperez",
                "Event_Description": "Service entered running state",
            },
            {
                "Timestamp": f"{DAY} 09:20:00",
                "Event_ID": 5156,
                "User": "CORP\\jlopez",
                "Event_Description": "Windows Filtering Platform permitted a connection",
            },
            {
                "Timestamp": f"{DAY} 09:25:00",
                "Event_ID": 5156,
                "User": "CORP\\aperez",
                "Event_Description": "Windows Filtering Platform permitted a connection",
            },
            {
                "Timestamp": f"{DAY} 09:40:00",
                "Event_ID": 4634,
                "User": "CORP\\jlopez",
                "Event_Description": "An account was logged off",
            },
            {
                "Timestamp": f"{DAY} 09:45:00",
                "Event_ID": 4634,
                "User": "CORP\\aperez",
                "Event_Description": "An account was logged off",
            },
        ]
    )


@pytest.mark.parametrize("detector", ALL_DETECTORS, ids=lambda detector: detector.__name__)
def test_no_detector_fires_on_the_measured_baseline(detector) -> None:
    """FSD §6: the baseline is the behaviour the thresholds must not flag."""
    assert detector(measured_baseline()) == []


# --- D1a: directed brute force ------------------------------------------------


def test_d1a_fires_on_three_failures_for_one_account_in_ten_minutes() -> None:
    events = frame(
        [
            failed_logon("09:00:00"),
            failed_logon("09:05:00"),
            failed_logon("09:10:00"),
        ]
    )

    findings = d1a_directed_brute_force(events)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.code == "D1a"
    assert finding.category == "brute-force"
    assert finding.event_count == 3
    assert finding.evidence == ("EVT-00001", "EVT-00002", "EVT-00003")
    assert finding.entities.users == ("jlopez",)
    assert finding.severity_hint in {"high", "critical"}
    assert "jlopez" in finding.rationale
    assert "3" in finding.rationale


def test_d1a_ignores_two_failures_for_the_same_account() -> None:
    events = frame([failed_logon("09:00:00"), failed_logon("09:05:00")])

    assert d1a_directed_brute_force(events) == []


def test_d1a_ignores_failures_spread_beyond_the_ten_minute_window() -> None:
    events = frame(
        [
            failed_logon("09:00:00"),
            failed_logon("09:05:30"),
            failed_logon("09:11:00"),
        ]
    )

    assert d1a_directed_brute_force(events) == []


def test_d1a_counts_failures_per_account_not_across_accounts() -> None:
    events = frame(
        [
            failed_logon("09:00:00", user="jlopez"),
            failed_logon("09:01:00", user="aperez"),
            failed_logon("09:02:00", user="mruiz"),
        ]
    )

    assert d1a_directed_brute_force(events) == []


# --- D1b: password spray ------------------------------------------------------


def test_d1b_fires_on_five_failures_from_one_external_ip_against_three_accounts() -> None:
    events = frame(
        [
            failed_logon("09:00:00", user="jlopez", ip=EXTERNAL_IP),
            failed_logon("09:01:00", user="aperez", ip=EXTERNAL_IP),
            failed_logon("09:02:00", user="mruiz", ip=EXTERNAL_IP),
            failed_logon("09:03:00", user="jlopez", ip=EXTERNAL_IP),
            failed_logon("09:04:00", user="aperez", ip=EXTERNAL_IP),
        ]
    )

    findings = d1b_password_spray(events)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.code == "D1b"
    assert finding.category == "brute-force"
    assert finding.event_count == 5
    assert set(finding.entities.users) == {"jlopez", "aperez", "mruiz"}
    assert finding.entities.source_ips == (EXTERNAL_IP,)


def test_d1b_ignores_five_failures_against_only_two_accounts() -> None:
    events = frame(
        [
            failed_logon(
                f"09:0{minute}:00",
                user="jlopez" if minute % 2 else "aperez",
                ip=EXTERNAL_IP,
            )
            for minute in range(5)
        ]
    )

    assert d1b_password_spray(events) == []


def test_d1b_ignores_four_failures_against_three_accounts() -> None:
    events = frame(
        [
            failed_logon("09:00:00", user="jlopez", ip=EXTERNAL_IP),
            failed_logon("09:01:00", user="aperez", ip=EXTERNAL_IP),
            failed_logon("09:02:00", user="mruiz", ip=EXTERNAL_IP),
            failed_logon("09:03:00", user="jlopez", ip=EXTERNAL_IP),
        ]
    )

    assert d1b_password_spray(events) == []


def test_d1b_ignores_five_failures_that_never_fit_in_fifteen_minutes() -> None:
    """Five failures chained 14 minutes apart span 56 minutes: no 15-minute block."""
    events = frame(
        [
            failed_logon("09:00:00", user="jlopez", ip=EXTERNAL_IP),
            failed_logon("09:14:00", user="aperez", ip=EXTERNAL_IP),
            failed_logon("09:28:00", user="mruiz", ip=EXTERNAL_IP),
            failed_logon("09:42:00", user="jlopez", ip=EXTERNAL_IP),
            failed_logon("09:56:00", user="aperez", ip=EXTERNAL_IP),
        ]
    )

    assert d1b_password_spray(events) == []


def test_d1b_ignores_the_same_pattern_from_an_internal_ip() -> None:
    events = frame(
        [
            failed_logon("09:00:00", user="jlopez", ip=INTERNAL_IP),
            failed_logon("09:01:00", user="aperez", ip=INTERNAL_IP),
            failed_logon("09:02:00", user="mruiz", ip=INTERNAL_IP),
            failed_logon("09:03:00", user="jlopez", ip=INTERNAL_IP),
            failed_logon("09:04:00", user="aperez", ip=INTERNAL_IP),
        ]
    )

    assert d1b_password_spray(events) == []


# --- D1c: external exposure ---------------------------------------------------


def test_d1c_fires_on_a_single_failure_from_an_external_ip() -> None:
    events = frame([failed_logon("09:00:00", user="admin", ip=EXTERNAL_IP_2, logon_type=10)])

    findings = d1c_external_exposure(events)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.code == "D1c"
    assert finding.event_count == 1
    assert finding.entities.source_ips == (EXTERNAL_IP_2,)
    assert finding.severity_hint in {"high", "critical"}


def test_d1c_ignores_a_single_failure_from_an_internal_ip() -> None:
    events = frame([failed_logon("09:00:00", user="admin", ip=INTERNAL_IP)])

    assert d1c_external_exposure(events) == []


# --- D1d: successful logon after a brute-force block --------------------------


def test_d1d_escalates_to_critical_when_a_logon_succeeds_after_the_failures() -> None:
    events = frame(
        [
            failed_logon("09:00:00", user="admin", ip=EXTERNAL_IP_2),
            failed_logon("09:01:00", user="admin", ip=EXTERNAL_IP_2),
            failed_logon("09:02:00", user="admin", ip=EXTERNAL_IP_2),
            successful_logon("09:10:00", user="admin", ip=EXTERNAL_IP_2),
        ]
    )

    findings = d1d_post_compromise_logon(events)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.code == "D1d"
    assert finding.severity_hint == "critical"
    assert finding.entities.users == ("admin",)
    assert "EVT-00004" in finding.evidence


def test_d1d_does_not_fire_without_a_success() -> None:
    events = frame(
        [
            failed_logon("09:00:00", user="admin", ip=EXTERNAL_IP_2),
            failed_logon("09:01:00", user="admin", ip=EXTERNAL_IP_2),
            failed_logon("09:02:00", user="admin", ip=EXTERNAL_IP_2),
        ]
    )

    assert d1d_post_compromise_logon(events) == []


def test_d1d_does_not_fire_when_the_success_is_beyond_fifteen_minutes() -> None:
    events = frame(
        [
            failed_logon("09:00:00", user="admin", ip=EXTERNAL_IP_2),
            failed_logon("09:01:00", user="admin", ip=EXTERNAL_IP_2),
            failed_logon("09:02:00", user="admin", ip=EXTERNAL_IP_2),
            successful_logon("09:20:00", user="admin", ip=EXTERNAL_IP_2),
        ]
    )

    assert d1d_post_compromise_logon(events) == []


# --- D2: suspicious logons ----------------------------------------------------


def test_d2_fires_on_a_logon_from_an_external_ip() -> None:
    events = frame([successful_logon("09:00:00", user="mgarcia", ip=EXTERNAL_IP)])

    findings = d2_suspicious_logons(events)

    assert len(findings) == 1
    assert findings[0].code == "D2"
    assert findings[0].category == "suspicious-logon"
    assert findings[0].severity_hint == "high"


def test_d2_fires_on_a_privileged_account_logon() -> None:
    events = frame([successful_logon("09:00:00", user="admin", ip=INTERNAL_IP)])

    findings = d2_suspicious_logons(events)

    assert len(findings) == 1
    assert findings[0].entities.users == ("admin",)


def test_d2_stays_silent_on_a_normal_internal_logon_and_does_not_guess_hours() -> None:
    """FSD §7.4: there is no business-hour baseline in the export, so a 03:00
    logon of a regular account is not evidence of anything on its own."""
    events = frame(
        [
            successful_logon("09:00:00", user="jlopez", ip=INTERNAL_IP),
            {
                **successful_logon("03:00:00", user="jlopez", ip=INTERNAL_IP),
                "Log_ID": "EVT-00002",
            },
        ]
    )

    assert d2_suspicious_logons(events) == []


# --- D3: privilege escalation -------------------------------------------------


def privilege(
    time: str,
    *,
    user: str = "mruiz",
    ip: str = INTERNAL_IP,
    host: str = "FS-SRV01",
) -> dict:
    return {
        "Timestamp": f"{DAY} {time}",
        "Hostname": host,
        "Event_ID": 4672,
        "User": f"CORP\\{user}",
        "Source_IP": ip,
        "Event_Description": "Special privileges assigned to new logon",
    }


def test_d3_fires_when_special_privileges_come_from_an_external_ip() -> None:
    events = frame([privilege("09:07:00", user="admin", ip=EXTERNAL_IP_2, host="APPSRV01")])

    findings = d3_privilege_escalation(events)

    assert len(findings) == 1
    assert findings[0].code == "D3"
    assert findings[0].category == "privilege-escalation"


def test_d3_ignores_a_single_internal_failure_before_success_and_privileges() -> None:
    """FSD §6: ≤2 failures per account per 10 min is the measured baseline, so one
    mistyped password followed by a normal logon is not an escalation."""
    events = frame(
        [
            failed_logon("09:09:09", user="mruiz", ip=INTERNAL_IP),
            successful_logon("09:10:49", user="mruiz", ip=INTERNAL_IP),
            privilege("09:13:56", user="mruiz", ip=INTERNAL_IP),
        ]
    )

    assert d3_privilege_escalation(events) == []


def test_d3_ignores_two_internal_failures_before_success_and_privileges() -> None:
    """One step below the D1a burst threshold is still baseline behaviour."""
    events = frame(
        [
            failed_logon("09:04:00", user="mruiz", ip=INTERNAL_IP),
            failed_logon("09:07:00", user="mruiz", ip=INTERNAL_IP),
            successful_logon("09:10:49", user="mruiz", ip=INTERNAL_IP),
            privilege("09:13:56", user="mruiz", ip=INTERNAL_IP),
        ]
    )

    assert d3_privilege_escalation(events) == []


def test_d3_fires_on_three_internal_failures_then_success_then_privileges() -> None:
    """A real burst (≥3 failures in 10 min, the D1a threshold) escalates."""
    events = frame(
        [
            failed_logon("09:00:00", user="mruiz", ip=INTERNAL_IP),
            failed_logon("09:03:00", user="mruiz", ip=INTERNAL_IP),
            failed_logon("09:06:00", user="mruiz", ip=INTERNAL_IP),
            successful_logon("09:10:49", user="mruiz", ip=INTERNAL_IP),
            privilege("09:13:56", user="mruiz", ip=INTERNAL_IP),
        ]
    )

    findings = d3_privilege_escalation(events)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.code == "D3"
    assert finding.category == "privilege-escalation"
    assert finding.evidence == (
        "EVT-00001",
        "EVT-00002",
        "EVT-00003",
        "EVT-00004",
        "EVT-00005",
    )


def test_d3_ignores_internal_failures_spread_beyond_ten_minutes() -> None:
    """Three failures that never fit one 10-minute window are not a burst."""
    events = frame(
        [
            failed_logon("09:00:00", user="mruiz", ip=INTERNAL_IP),
            failed_logon("09:05:30", user="mruiz", ip=INTERNAL_IP),
            failed_logon("09:11:00", user="mruiz", ip=INTERNAL_IP),
            successful_logon("09:12:30", user="mruiz", ip=INTERNAL_IP),
            privilege("09:13:56", user="mruiz", ip=INTERNAL_IP),
        ]
    )

    assert d3_privilege_escalation(events) == []


def test_d3_still_fires_from_an_external_ip_when_no_internal_burst_exists() -> None:
    """Regression: the external-origin branch does not require any prior failure."""
    events = frame(
        [
            privilege("09:07:00", user="mruiz", ip=INTERNAL_IP),
            privilege("09:08:00", user="admin", ip=EXTERNAL_IP_2, host="APPSRV01"),
        ]
    )

    findings = d3_privilege_escalation(events)

    assert len(findings) == 1
    assert findings[0].code == "D3"
    assert findings[0].entities.source_ips == (EXTERNAL_IP_2,)
    assert findings[0].evidence == ("EVT-00002",)


def test_d3_ignores_a_lone_internal_privilege_event() -> None:
    """FSD §6: 7 of the 8 `4672` in the export are legitimate internal noise."""
    events = frame([privilege("09:22:27", user="svc_backup", ip="10.10.1.31")])

    assert d3_privilege_escalation(events) == []


def test_d3_ignores_privileges_that_only_follow_a_successful_logon() -> None:
    events = frame(
        [
            successful_logon("09:10:49", user="mruiz", ip=INTERNAL_IP),
            privilege("09:13:56", user="mruiz", ip=INTERNAL_IP),
        ]
    )

    assert d3_privilege_escalation(events) == []


# --- D4: commands and processes ----------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "powershell.exe -NoProfile -EncodedCommand <base64_redacted>",
        "powershell.exe -enc SQBFAFgA",
        "vssadmin.exe delete shadows /all /quiet",
        "net.exe view \\\\FS-SRV01",
        "cmd.exe /c whoami",
        "7z.exe a C:\\Users\\Public\\archive.7z C:\\Legal\\*.docx",
        "tar.exe -a -c -f C:\\Temp\\finance.zip C:\\Temp\\reports",
        "C:\\ProgramData\\wuhelper.exe",
    ],
)
def test_d4_fires_on_each_known_bad_command_line(command: str) -> None:
    findings = d4_command_execution(frame([process("09:09:00", command)]))

    assert len(findings) == 1
    assert findings[0].code == "D4"
    assert findings[0].category == "command-execution"
    assert findings[0].evidence == ("EVT-00001",)


def test_d4_fires_on_a_process_created_by_the_web_server_pool() -> None:
    events = frame(
        [
            {
                "Timestamp": f"{DAY} 12:15:00",
                "Hostname": "WEB-01",
                "Event_ID": 4688,
                "User": "IIS APPPOOL\\DefaultAppPool",
                "Source_IP": "192.0.2.91",
                "Event_Description": "A new process has been created",
                "Process_CommandLine": "cmd.exe /c dir",
            }
        ]
    )

    findings = d4_command_execution(events)

    assert len(findings) == 1
    assert "IIS" in findings[0].rationale


def test_d4_ignores_benign_processes() -> None:
    events = frame(
        [
            process("09:00:00", "explorer.exe"),
            process("09:01:00", "notepad.exe"),
            process("09:02:00", "svchost.exe"),
            process("09:03:00", "taskhostw.exe"),
        ]
    )

    assert d4_command_execution(events) == []


def test_d4_never_claims_what_a_redacted_payload_did() -> None:
    events = frame(
        [process("09:09:00", "powershell.exe -NoProfile -EncodedCommand <base64_redacted>")]
    )

    finding = d4_command_execution(events)[0]

    assert "no es posible determinar" in finding.rationale
    assert "<base64_redacted>" not in finding.rationale


# --- D5: lateral movement -----------------------------------------------------


def test_d5_fires_when_a_remote_logon_is_followed_by_share_access_on_the_target() -> None:
    events = frame(
        [
            successful_logon(
                "09:16:00",
                user="admin",
                ip="10.10.2.15",
                host="FS-SRV01",
                logon_type=3,
                source_host="APP-SRV01",
            ),
            {
                "Timestamp": f"{DAY} 09:17:00",
                "Hostname": "FS-SRV01",
                "Event_ID": 5140,
                "User": "CORP\\admin",
                "Source_IP": "10.10.2.15",
                "Event_Description": "Network share accessed: \\\\FS-SRV01\\Finance",
            },
        ]
    )

    findings = d5_lateral_movement(events)

    assert len(findings) == 1
    assert findings[0].code == "D5"
    assert findings[0].category == "lateral-movement"
    assert findings[0].evidence == ("EVT-00001", "EVT-00002")
    assert "FSSRV01" in findings[0].entities.hosts


def test_d5_ignores_a_remote_logon_without_follow_up_on_the_target() -> None:
    events = frame(
        [
            successful_logon(
                "09:16:00",
                user="admin",
                ip="10.10.2.15",
                host="FS-SRV01",
                logon_type=3,
                source_host="APP-SRV01",
            ),
            {
                "Timestamp": f"{DAY} 09:17:00",
                "Hostname": "WEB-01",
                "Event_ID": 5140,
                "User": "CORP\\admin",
                "Source_IP": "10.10.2.15",
                "Event_Description": "A network share object was accessed",
            },
        ]
    )

    assert d5_lateral_movement(events) == []


def test_d5_ignores_a_follow_up_outside_the_ten_minute_window() -> None:
    events = frame(
        [
            successful_logon(
                "09:16:00",
                user="admin",
                ip="10.10.2.15",
                host="FS-SRV01",
                logon_type=3,
                source_host="APP-SRV01",
            ),
            {
                "Timestamp": f"{DAY} 09:27:00",
                "Hostname": "FS-SRV01",
                "Event_ID": 5145,
                "User": "CORP\\admin",
                "Source_IP": "10.10.2.15",
                "Event_Description": "Detailed file share access: Finance\\Budget2027.xlsx",
            },
        ]
    )

    assert d5_lateral_movement(events) == []


def test_d5_ignores_a_logon_whose_source_is_the_target_itself() -> None:
    events = frame(
        [
            successful_logon(
                "09:16:00",
                user="admin",
                ip="10.10.2.15",
                host="FS-SRV01",
                logon_type=3,
                source_host="FS-SRV01",
            ),
            {
                "Timestamp": f"{DAY} 09:17:00",
                "Hostname": "FS-SRV01",
                "Event_ID": 5140,
                "User": "CORP\\admin",
                "Event_Description": "A network share object was accessed",
            },
        ]
    )

    assert d5_lateral_movement(events) == []


# --- D6: other anomalies ------------------------------------------------------


def object_access(time: str, index: int, *, user: str = "backupsvc") -> dict:
    return {
        "Timestamp": f"{DAY} {time}",
        "Hostname": "FS-SRV01",
        "Event_ID": 4663,
        "User": f"CORP\\{user}",
        "Event_Description": "An attempt was made to access an object",
        "Process_CommandLine": f"File access: Finance\\FY2026\\document_{index:03d}.xlsx",
    }


def test_d6_flags_a_description_that_occurs_exactly_once() -> None:
    events = frame(
        [
            {
                **successful_logon("09:00:00"),
                "Event_Description": "An account was successfully logged on",
            },
            {
                **successful_logon("09:01:00"),
                "Event_Description": "An account was successfully logged on",
            },
            {
                "Timestamp": f"{DAY} 09:21:00",
                "Hostname": "APPSRV01",
                "Event_ID": 5156,
                "User": "CORP\\admin",
                "Event_Description": (
                    "Allowed outbound connection to 203.0.113.88:443 (process=powershell.exe)"
                ),
            },
        ]
    )

    findings = d6_anomalies(events)

    assert len(findings) == 1
    assert findings[0].code == "D6"
    assert findings[0].evidence == ("EVT-00003",)
    assert findings[0].category == "other-anomaly"


def test_d6_bulk_object_read_fires_and_requires_validation() -> None:
    events = frame([object_access(f"09:37:{index * 5:02d}", index) for index in range(11)])

    findings = d6_anomalies(events)

    assert len(findings) == 1
    assert findings[0].requires_validation is True
    assert findings[0].event_count == 11


def test_d6_bulk_object_read_ignores_ten_objects() -> None:
    events = frame([object_access(f"09:37:{index * 5:02d}", index) for index in range(10)])

    assert d6_anomalies(events) == []


def test_d6_bulk_object_read_ignores_reads_spread_beyond_five_minutes() -> None:
    base = pd.Timestamp(f"{DAY} 09:37:00")
    times = [(base + pd.Timedelta(seconds=40 * index)).strftime("%H:%M:%S") for index in range(11)]

    events = frame([object_access(time, index) for index, time in enumerate(times)])

    assert d6_anomalies(events) == []


def test_d6_flags_persistence_created_outside_the_maintenance_window() -> None:
    events = frame(
        [
            {
                "Timestamp": f"{DAY} 11:37:00",
                "Hostname": "APPSRV01",
                "Event_ID": 4698,
                "User": "CORP\\helpdesk",
                "Event_Description": "A scheduled task was created",
                "Process_CommandLine": (
                    "TaskName=\\Microsoft\\Windows\\UpdateCheck; "
                    "Action=powershell.exe -File C:\\ProgramData\\updatecheck.ps1"
                ),
            },
            {
                "Timestamp": f"{DAY} 11:38:00",
                "Hostname": "APPSRV01",
                "Event_ID": 7045,
                "Log_Source": "System",
                "User": "CORP\\helpdesk",
                "Event_Description": "A service was installed in the system",
                "Process_CommandLine": (
                    "ServiceName=WinUpdateHelper; ImagePath=C:\\ProgramData\\wuhelper.exe"
                ),
            },
        ]
    )

    findings = d6_anomalies(events)

    assert len(findings) == 2
    assert {finding.code for finding in findings} == {"D6"}
    assert all(finding.category == "other-anomaly" for finding in findings)


def test_d6_ignores_persistence_created_inside_the_maintenance_window() -> None:
    events = frame(
        [
            {
                "Timestamp": f"{DAY} 03:00:00",
                "Hostname": "APPSRV01",
                "Event_ID": 4698,
                "User": "CORP\\helpdesk",
                "Event_Description": "A scheduled task was created",
            },
            {
                "Timestamp": f"{DAY} 03:10:00",
                "Hostname": "APPSRV01",
                "Event_ID": 7045,
                "Log_Source": "System",
                "User": "CORP\\helpdesk",
                "Event_Description": "A service was installed in the system",
            },
        ]
    )

    assert d6_anomalies(events) == []


# --- D7: exfiltration ---------------------------------------------------------

MEGABYTE = 1_000_000


def test_d7_fires_on_fifty_megabytes_towards_one_external_destination() -> None:
    events = frame(
        [
            proxy("10:43:00", bytes_out=25 * MEGABYTE),
            proxy("10:44:00", bytes_out=25 * MEGABYTE, uri="/upload/session/2"),
        ]
    )

    findings = d7_exfiltration(events)

    assert len(findings) == 1
    assert findings[0].code == "D7"
    assert findings[0].category == "other-anomaly"
    assert findings[0].event_count == 2
    assert "198.51.100.88" in findings[0].rationale


def test_d7_ignores_just_below_fifty_megabytes_and_few_posts() -> None:
    events = frame(
        [
            proxy("10:43:00", bytes_out=24 * MEGABYTE),
            proxy("10:44:00", bytes_out=24 * MEGABYTE, uri="/upload/session/2"),
        ]
    )

    assert d7_exfiltration(events) == []


def test_d7_fires_on_ten_posts_to_the_same_destination() -> None:
    events = frame(
        [
            proxy(f"10:4{index}:00", bytes_out=1024, uri=f"/upload/session/{index}")
            for index in range(10)
        ]
    )

    findings = d7_exfiltration(events)

    assert len(findings) == 1
    assert findings[0].event_count == 10


def test_d7_ignores_nine_posts_summing_below_the_byte_threshold() -> None:
    events = frame(
        [
            proxy(f"10:4{index}:00", bytes_out=1024, uri=f"/upload/session/{index}")
            for index in range(9)
        ]
    )

    assert d7_exfiltration(events) == []


def test_d7_ignores_upload_volume_towards_an_internal_destination() -> None:
    events = frame(
        [
            proxy(
                f"10:4{index}:00",
                bytes_out=10 * MEGABYTE,
                uri=f"/upload/{index}",
                destination="10.10.1.20:443",
            )
            for index in range(9)
        ]
    )

    assert d7_exfiltration(events) == []
