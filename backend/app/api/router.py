"""Upload, table-view and analysis endpoints (RF1, RF2, RF3, RF4).

Every user-facing message here is Spanish, because it is rendered verbatim in
the UI. Identifiers, comments and tests stay English.
"""

from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Annotated, Any
from zipfile import BadZipFile

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from openpyxl.utils.exceptions import InvalidFileException

from app.api.analysis import Analysis, analyze
from app.api.ratelimit import ANALYZE_BUCKET, UPLOAD_BUCKET, rate_limited
from app.api.serialization import records
from app.api.session import session_store
from app.api.upload_guard import ContentError, validate_workbook_payload
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
    "Todavía no se ha cargado ningún archivo. Sube un export .xlsx y vuelve a intentarlo."
)

UNKNOWN_INCIDENT_MESSAGE = "No existe un incidente con el identificador «{incident_id}»."

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


@router.post(
    "/upload",
    tags=["ingest"],
    dependencies=[Depends(rate_limited(UPLOAD_BUCKET, "rate_limit_upload"))],
)
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
            detail="El archivo está vacío. Selecciona un export .xlsx válido.",
        )
    if len(payload) > max_bytes:
        raise _too_large(settings)

    # The extension and the declared media type only state what the client says
    # this file is; a renamed `.exe`, an HTML page or a binary `.xls` all use the
    # `.xlsx` suffix. Validate the bytes before handing them to openpyxl (RF8).
    try:
        validate_workbook_payload(payload)
    except ContentError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
        ) from error

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
                "Verifica que no esté dañado y vuelve a exportarlo."
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
        "items": records(window),
        "total": total,
        "page": current,
        "page_size": size,
        "total_pages": total_pages,
        "columns": list(working.columns),
    }


def current_analysis() -> Analysis:
    """The session's analysis, computed on first use and cached for the session.

    Detection is deterministic and pure over the frame, so caching cannot change
    a result: it only avoids repeating the same work on every dashboard reload.
    """
    frame = session_store.frame()
    if frame is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=NO_SESSION_MESSAGE
        )

    cached = session_store.analysis(frame)
    if cached is None:
        cached = analyze(frame)
        session_store.store_analysis(frame, cached)
    return cached


@router.post(
    "/analyze",
    tags=["analysis"],
    dependencies=[Depends(rate_limited(ANALYZE_BUCKET, "rate_limit_analyze"))],
)
def analyze_export() -> dict[str, Any]:
    """Detect and classify the loaded export; return the dashboard payload (RF4)."""
    return current_analysis().dashboard


@router.get("/incidents/{incident_id}", tags=["analysis"])
def get_incident(incident_id: str) -> dict[str, Any]:
    """Risk block, findings and joined evidence rows of one incident (RF4)."""
    incident = current_analysis().incidents.get(incident_id)
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=UNKNOWN_INCIDENT_MESSAGE.format(incident_id=incident_id),
        )
    return incident
