"""Application settings, loaded from the environment.

Secrets never live in the repository: `.env` is gitignored and `.env.example`
documents every supported variable.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM provider (nan.builders, OpenAI-compatible). The key stays server-side.
    nan_api_key: str = ""
    nan_base_url: str = "https://api.nan.builders/v1"
    nan_model: str = "deepseek-v4-flash"
    nan_reasoning_effort: str = "low"

    # Upload guard (RF1 / RF8).
    max_upload_mb: int = 50

    # Rate limiting (RF8): in-process fixed window, per client and per endpoint.
    # The counter lives in the API process (see `app/api/ratelimit.py`); the
    # defaults leave a normal analyst session far below the limit, and they are
    # generous enough that a dashboard refresh loop never blocks a PDF download
    # because every endpoint has its own bucket.
    rate_limit_enabled: bool = True
    rate_limit_window_seconds: int = 60
    rate_limit_upload: int = 20
    rate_limit_analyze: int = 120
    rate_limit_report: int = 60
    rate_limit_pdf: int = 30

    # Only the local frontend may call the API (RF8).
    cors_origins: list[str] = ["http://localhost:4200"]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
