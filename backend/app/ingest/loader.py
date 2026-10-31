"""Load a SIEM Excel export and apply the normalization + parsing layers."""

from __future__ import annotations

from pathlib import Path
from typing import IO

import pandas as pd

from app.ingest.normalize import normalize
from app.ingest.parse import parse

REQUIRED_COLUMNS = (
    "Log_ID",
    "Timestamp",
    "Hostname",
    "Event_ID",
    "User",
    "Source_IP",
    "Destination",
    "Log_Source",
    "Event_Description",
    "Process_CommandLine",
    "Result",
    "Severity",
)


class SchemaError(ValueError):
    """The uploaded workbook does not look like a SIEM export."""


def load_export(source: str | Path | IO[bytes]) -> pd.DataFrame:
    """Read the first sheet of an export and return it normalized.

    The original columns are kept verbatim so findings can cite `Log_ID` rows.
    """
    frame = pd.read_excel(source, sheet_name=0)

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise SchemaError(
            "El archivo no tiene el esquema esperado. Faltan columnas: "
            + ", ".join(missing)
        )

    return parse(normalize(frame))
