"""Free-text extraction contract (FSD §4.7).

The export has no dedicated columns for logon type, lateral source, share,
task, service, byte counts or URI: all of it is embedded in
`Event_Description` and `Process_CommandLine`. These tests pin what we can
and cannot recover.
"""

import pandas as pd
import pytest

from app.ingest.parse import parse


def frame(**columns: list) -> pd.DataFrame:
    width = len(next(iter(columns.values())))
    base = {name: [None] * width for name in ("Log_ID", "Event_Description", "Process_CommandLine")}
    for index in range(width):
        base["Log_ID"][index] = f"EVT-{index:05d}"
    base.update(columns)
    return pd.DataFrame(base)


def test_logon_type_is_recovered_from_the_description() -> None:
    df = frame(
        Event_Description=[
            "An account failed to log on (LogonType=10; RDP)",
            "An account was successfully logged on (LogonType=3; source=APP-SRV01)",
            "An account failed to log on",
        ]
    )

    result = parse(df)

    assert result["logon_type"].tolist()[0] == 10
    assert result["logon_type"].tolist()[1] == 3
    assert pd.isna(result["logon_type"].tolist()[2])


def test_lateral_source_is_the_only_host_attribution_available() -> None:
    """FSD §4.8: the lateral hop is visible in the text, never in Source_IP."""
    df = frame(
        Event_Description=["An account was successfully logged on (LogonType=3; source=APP-SRV01)"]
    )

    result = parse(df)

    assert result["lateral_source"].iloc[0] == "APP-SRV01"


def test_proxy_metadata_is_split_into_bytes_and_uri() -> None:
    df = frame(
        Process_CommandLine=["bytes_out=6737085 uri=/upload/session/1"],
    )

    result = parse(df)

    assert result["bytes_out"].iloc[0] == 6737085
    assert result["uri"].iloc[0] == "/upload/session/1"


def test_scheduled_task_fields_are_extracted() -> None:
    df = frame(
        Process_CommandLine=[
            "TaskName=\\Microsoft\\Windows\\UpdateCheck; "
            "Action=powershell.exe -File C:\\ProgramData\\updatecheck.ps1"
        ],
        Event_Description=["A scheduled task was created"],
    )

    result = parse(df)

    assert result["task_name"].iloc[0] == "\\Microsoft\\Windows\\UpdateCheck"
    assert result["script_path"].iloc[0] == "C:\\ProgramData\\updatecheck.ps1"


def test_service_install_fields_are_extracted() -> None:
    df = frame(
        Process_CommandLine=[
            "ServiceName=WinUpdateHelper; ImagePath=C:\\ProgramData\\wuhelper.exe"
        ],
        Event_Description=["A service was installed in the system"],
    )

    result = parse(df)

    assert result["service_name"].iloc[0] == "WinUpdateHelper"
    assert result["image_path"].iloc[0] == "C:\\ProgramData\\wuhelper.exe"


def test_share_and_file_path_are_extracted() -> None:
    df = frame(
        Event_Description=["Detailed file share access: Finance\\Budget2027.xlsx"],
    )

    result = parse(df)

    assert result["file_path"].iloc[0] == "Finance\\Budget2027.xlsx"


def test_unc_share_target_is_extracted() -> None:
    df = frame(Destination=["\\\\FS-SRV01\\Finance"])

    result = parse(df)

    assert result["share"].iloc[0] == "\\\\FS-SRV01\\Finance"


def test_missing_text_yields_missing_values_not_zeroes() -> None:
    """Absence of data must stay absent: a fabricated 0 would read as evidence."""
    df = frame(Event_Description=["An account was logged off"], Process_CommandLine=[None])

    result = parse(df)

    assert pd.isna(result["logon_type"].iloc[0])
    assert pd.isna(result["bytes_out"].iloc[0])
    assert pd.isna(result["task_name"].iloc[0])


@pytest.mark.parametrize(
    "command",
    [
        "powershell.exe -NoProfile -EncodedCommand [REDACTED_SYNTHETIC]",
        "powershell.exe -NoProfile -EncodedCommand <base64_redacted>",
    ],
)
def test_redacted_payloads_are_kept_verbatim_and_marked(command: str) -> None:
    """FSD §7.4: the payload is redacted at the source, we must not guess it."""
    result = parse(frame(Process_CommandLine=[command]))

    assert result["command_norm"].iloc[0] == command
    assert result["payload_redacted"].iloc[0]
