"""Upload and table-view endpoints (RF1).

Every user-facing message here is Spanish, because it is rendered verbatim in
the UI. Identifiers, comments and tests stay English.
"""

from __future__ import annotations

import io
import math
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any
from zipfile import BadZipFile

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from openpyxl.utils.exceptions import InvalidFileException

from app.api.session import session_store
from app.config import Settings, get_settings
from app.ingest.loader import SchemaError, load_export
from app.ingest.quality import quality_report

router = APIRouter()

# Table-view protocol bounds. These are part of the UI contract, not deployment
# configuration, so they live next to the endpoint instead of in `Settings`;
# `Settings` still owns every deployable number (upload size).
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

XLSX_SUFFIX = ".xlsx"
ORDER_ASC = "asc"
ORDER_DESC = "desc"

NO_SESSION_MESSAGE = (
    "Todavía no se ha cargado ningún archivo. Suba un export .xlsx y vuelva a intentarlo."
)

# Unreadable-workbook failures: a bad zip, a non-Excel zip, a broken sheet.
_READ_ERRORS = (BadZipFile, InvalidFileException, KeyError, ValueError, OSError)


def _time_range(frame: pd.DataFrame) -> dict[str, str | None]:
    """Earliest and latest parsed timestamp; `None` when nothing parsed."""
    if "timestamp" not in frame:
        return {"start": None, "end": None}
    stamps = frame["timestamp"].dropna()
    if stamps.empty:
        return {"start": None, "end": None}
    return {"start": stamps.min().isoformat(), "end": stamps.max().isoformat()}


def _json_value(value: Any) -> Any:
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


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {column: _json_value(value) for column, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _search_mask(frame: pd.DataFrame, term: str) -> pd.Series:
    """Case-insensitive literal substring match across every column."""
    haystack = frame.astype("string")
    matches = haystack.apply(
        lambda column: column.str.contains(term, case=False, regex=False, na=False)
    )
    return matches.any(axis=1)


def _sort_frame(frame: pd.DataFrame, column: str, ascending: bool) -> pd.DataFrame:
    """Order by one column without raising on mixed-type source columns."""
    key = frame[column]
    if key.dtype == object:
        # `Event_ID` mixes ints and names; text order is deterministic and safe.
        key = key.astype("string")
    ordered = key.sort_values(ascending=ascending, kind="stable", na_position="last")
    return frame.loc[ordered.index]


def _too_large(settings: Settings) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "El archivo supera el tamaño máximo permitido de "
            f"{settings.max_upload_mb} MB."
        ),
    )


@router.post("/upload", tags=["ingest"])
async def upload_export(
    file: Annotated[UploadFile, File(description="Export del SIEM en formato .xlsx.")],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Validate an `.xlsx` upload, load it into the session and report its quality."""
    file_name = file.filename or ""
    if Path(file_name).suffix.lower() != XLSX_SUFFIX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato no admitido: solo se aceptan archivos .xlsx.",
        )

    # Reject on the size Starlette already knows, before materializing the body:
    # reading first would let one huge upload exhaust memory (RF8).
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if file.size is not None and file.size > max_bytes:
        raise _too_large(settings)

    payload = await file.read(max_bytes + 1)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo está vacío. Seleccione un export .xlsx válido.",
        )
    if len(payload) > max_bytes:
        raise _too_large(settings)

    try:
        frame = load_export(io.BytesIO(payload))
    except SchemaError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
        ) from error
    except _READ_ERRORS as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No se pudo leer el archivo como un libro .xlsx válido. "
                "Verifique que no esté dañado y vuelva a exportarlo."
            ),
        ) from error

    session_store.store(frame)
    report = quality_report(frame)
    return {
        "file_name": file_name,
        "detected_columns": report["detected_columns"],
        "row_count": report["row_count"],
        "time_range": _time_range(frame),
        "quality": report,
    }


@router.get("/events", tags=["ingest"])
def list_events(
    page: Annotated[
        int, Query(description="Página solicitada (1-based); se ajusta a 1 si es menor.")
    ] = 1,
    page_size: Annotated[
        int,
        Query(description=f"Filas por página; se ajusta al rango 1..{MAX_PAGE_SIZE}."),
    ] = DEFAULT_PAGE_SIZE,
    search: Annotated[
        str | None,
        Query(
            description="Texto a buscar en todas las columnas, sin distinguir mayúsculas."
        ),
    ] = None,
    sort: Annotated[str | None, Query(description="Columna de ordenamiento.")] = None,
    order: Annotated[str, Query(description="'asc' o 'desc'.")] = ORDER_ASC,
) -> dict[str, Any]:
    """Return one page of normalized events: original columns plus derived ones."""
    frame = session_store.frame()
    if frame is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=NO_SESSION_MESSAGE
        )

    normalized_order = order.lower()
    if normalized_order not in {ORDER_ASC, ORDER_DESC}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Orden no válido: use 'asc' o 'desc'.",
        )
    if sort is not None and sort not in frame.columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Columna de ordenamiento no válida: {sort}.",
        )

    working = frame.reset_index(drop=True)
    if search:
        working = working[_search_mask(working, search)]
    if sort is not None:
        working = _sort_frame(working, sort, normalized_order == ORDER_ASC)

    total = int(len(working))
    size = max(1, min(page_size, MAX_PAGE_SIZE))
    current = max(1, page)
    total_pages = math.ceil(total / size) if total else 0
    start = (current - 1) * size
    window = working.iloc[start : start + size]

    return {
        "items": _records(window),
        "total": total,
        "page": current,
        "page_size": size,
        "total_pages": total_pages,
        "columns": list(working.columns),
    }
