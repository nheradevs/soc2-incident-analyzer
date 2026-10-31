"""JSON-safe conversion of pandas values for the API payloads.

One implementation for every endpoint: the table view and the analysis payload
must serialize a cell the same way, so a `NaN` in the export always reaches the
browser as `null` and never as the literal string `"nan"`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd


def json_value(value: Any) -> Any:
    """Convert one pandas scalar into a JSON-safe value (`NaN`/`NaT` -> null)."""
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if pd.isna(value):
        return None
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Every row of a frame as a JSON-safe dict, column order preserved."""
    return [
        {column: json_value(value) for column, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]
