"""Report endpoints: both Spanish versions and the PDF export (RF5, RF6, RF7).

`POST /api/report` reads the session's cached analysis, turns it into the closed
brief and composes the report. `GET /api/report/pdf` renders that same payload
as a PDF on the server, whole or as the single version the `version` query
parameter asks for. Both are synchronous because the provider client is
synchronous; FastAPI runs them in the thread pool. Every user-facing string is
Spanish; identifiers stay English.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.analysis import Analysis
from app.api.ratelimit import PDF_BUCKET, REPORT_BUCKET, rate_limited
from app.api.router import current_analysis
from app.api.session import session_store
from app.config import Settings, get_settings
from app.export import pdf_filename, render_pdf
from app.reporting.brief import build_brief
from app.reporting.compose import compose_report
from app.reporting.narrative import NarrativeClient
from app.reporting.templates import VERSIONS

router = APIRouter()

PDF_MEDIA_TYPE = "application/pdf"
UNKNOWN_VERSION_MESSAGE = "Versión de informe no válida: usa «ejecutiva» o «tecnica»."


def requested_version(version: str | None) -> str | None:
    """The version asked for, or a 400 naming the two accepted values."""
    if version is None or version in VERSIONS:
        return version
    raise HTTPException(status_code=400, detail=UNKNOWN_VERSION_MESSAGE)


def get_narrative_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> NarrativeClient:
    """Provider client for one request; overridable in tests."""
    return NarrativeClient(settings)


def composed_report(analysis: Analysis, client: NarrativeClient) -> dict[str, Any]:
    """The report payload of this export, composed once per upload.

    The PDF renders exactly this payload, so a download never disagrees with the
    report the UI already showed, and a configured provider is not called again
    just because the file is generated. A new upload invalidates the cache.
    """
    frame = session_store.frame()
    cached = session_store.report(frame) if frame is not None else None
    if cached is not None:
        return cached

    report = compose_report(build_brief(analysis), client=client)
    if frame is not None:
        session_store.store_report(frame, report)
    return report


@router.post(
    "/report",
    tags=["report"],
    dependencies=[Depends(rate_limited(REPORT_BUCKET, "rate_limit_report"))],
)
def generate_report(
    client: Annotated[NarrativeClient, Depends(get_narrative_client)],
) -> dict[str, Any]:
    """Return both report versions, the narrative state and the guard outcome.

    Raises 409 with a Spanish message when nothing has been uploaded yet, using
    the same session guard as the dashboard endpoints.
    """
    return composed_report(current_analysis(), client)


@router.get(
    "/report/pdf",
    tags=["report"],
    dependencies=[Depends(rate_limited(PDF_BUCKET, "rate_limit_pdf"))],
)
def export_report_pdf(
    client: Annotated[NarrativeClient, Depends(get_narrative_client)],
    version: str | None = None,
) -> Response:
    """Download the report as a PDF generated on the server (RF6).

    With `?version=ejecutiva` or `?version=tecnica` the file carries only that
    version: cover, contents and its nine sections. Without the parameter it
    still carries both, so existing links keep working. An unknown value is a
    400 in Spanish rather than a validation error. The file is built from the
    composed report only: the cover carries the counts and the classification of
    the analysis. Raises the same 409 as `POST /api/report` before any upload,
    and never includes the provider key, the prompt or the completion.
    """
    selected = requested_version(version)
    report = composed_report(current_analysis(), client)
    return Response(
        content=render_pdf(report, version=selected),
        media_type=PDF_MEDIA_TYPE,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{pdf_filename(report, selected)}"'
            ),
        },
    )
