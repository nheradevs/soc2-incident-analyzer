"""Report endpoint: both Spanish versions plus the narrative state (RF5, RF7).

`POST /api/report` reads the session's cached analysis, turns it into the closed
brief and composes the report. It is a synchronous endpoint because the provider
client is synchronous; FastAPI runs it in the thread pool. Every user-facing
string of the report is Spanish; identifiers stay English.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.router import current_analysis
from app.config import Settings, get_settings
from app.reporting.brief import build_brief
from app.reporting.compose import compose_report
from app.reporting.narrative import NarrativeClient

router = APIRouter()


def get_narrative_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> NarrativeClient:
    """Provider client for one request; overridable in tests."""
    return NarrativeClient(settings)


@router.post("/report", tags=["report"])
def generate_report(
    client: Annotated[NarrativeClient, Depends(get_narrative_client)],
) -> dict[str, Any]:
    """Return both report versions, the narrative state and the guard outcome.

    Raises 409 with a Spanish message when nothing has been uploaded yet, using
    the same session guard as the dashboard endpoints.
    """
    analysis = current_analysis()
    return compose_report(build_brief(analysis), client=client)
