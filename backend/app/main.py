"""FastAPI entrypoint for the SOC L2 incident analyzer."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router as ingest_router
from app.config import get_settings

API_PREFIX = "/api"


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="SOC L2 Incident Analyzer",
        version="0.1.0",
        description=(
            "Deterministic detection over a SIEM Excel export, with AI-assisted "
            "report writing. Findings are decided by rules, never by the model."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get(f"{API_PREFIX}/health", tags=["meta"])
    def health() -> dict[str, str]:
        """Liveness probe used by the frontend and the demo script."""
        return {"status": "ok"}

    app.include_router(ingest_router, prefix=API_PREFIX)

    return app


app = create_app()
