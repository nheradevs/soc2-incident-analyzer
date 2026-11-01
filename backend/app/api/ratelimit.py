"""In-process rate limiting for the expensive endpoints (RF8 / FSD §5).

No dependency, no shared store: the demo runs a single uvicorn process, so a
fixed-window counter in memory is the whole mechanism. The counter is keyed by
`(client identity, bucket)` and every knob lives in `Settings` so the limits are
deployment configuration rather than code.

Client identity is the peer address of the TCP connection
(`request.client.host`). Forwarding headers (`X-Forwarded-For`, `X-Real-IP`,
`Forwarded`) are deliberately never read: the app is served directly, with no
trusted reverse proxy in front, so those headers are attacker-controlled input.
Reading them would let one client mint an unlimited number of fresh budgets by
sending a different address on every request.

Expensive means: uploading a workbook, running detection, composing the report
and rendering the PDF. Each of them has its own bucket, so a burst of dashboard
refreshes cannot consume the PDF download budget.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.config import Settings, get_settings

RATE_LIMIT_MESSAGE = (
    "Demasiadas solicitudes en poco tiempo. Espera unos segundos y vuelve a intentarlo."
)

UPLOAD_BUCKET = "upload"
ANALYZE_BUCKET = "analyze"
REPORT_BUCKET = "report"
PDF_BUCKET = "pdf"

# Bucket used when the transport exposes no peer address (an ASGI server that
# omits `client`). Such requests share one budget instead of escaping the limit.
UNKNOWN_CLIENT = "desconocido"

# Above this many tracked clients, expired windows are evicted on the next hit.
# Bounds memory without a background task.
MAX_TRACKED_KEYS = 1024


class RateLimiter:
    """Fixed-window request counter: at most `limit` hits per key and window."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._windows: dict[tuple[str, str], tuple[float, int]] = {}
        self._lock = threading.Lock()

    def hit(
        self, key: tuple[str, str], *, limit: int, window_seconds: int
    ) -> float | None:
        """Count one request; return `None` when allowed, else the wait in seconds.

        A new window starts on the first hit and is not extended by later hits,
        so a client that keeps sending requests cannot postpone its own reset.
        """
        span = float(max(1, window_seconds))
        budget = max(1, limit)
        now = self._clock()
        with self._lock:
            self._evict_expired(now, span)
            window = self._windows.get(key)
            if window is None or now - window[0] >= span:
                self._windows[key] = (now, 1)
                return None
            start, count = window
            if count >= budget:
                return span - (now - start)
            self._windows[key] = (start, count + 1)
            return None

    def reset(self) -> None:
        """Forget every window. Used by the school demo restart and by tests."""
        with self._lock:
            self._windows.clear()

    def _evict_expired(self, now: float, span: float) -> None:
        if len(self._windows) < MAX_TRACKED_KEYS:
            return
        expired = [key for key, (start, _) in self._windows.items() if now - start >= span]
        for key in expired:
            del self._windows[key]


limiter = RateLimiter()


def client_identity(request: Request) -> str:
    """Identify the caller by its peer address, never by a forwarded header."""
    client = request.client
    return client.host if client is not None and client.host else UNKNOWN_CLIENT


def rate_limited(bucket: str, limit_field: str) -> Callable[..., None]:
    """Build the dependency enforcing `bucket`'s per-client budget.

    `limit_field` names the `Settings` field holding the budget, so the limit is
    resolved per request and a settings override is honoured immediately.
    """

    def enforce(
        request: Request,
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> None:
        if not settings.rate_limit_enabled:
            return
        retry_after = limiter.hit(
            (client_identity(request), bucket),
            limit=int(getattr(settings, limit_field)),
            window_seconds=settings.rate_limit_window_seconds,
        )
        if retry_after is None:
            return
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=RATE_LIMIT_MESSAGE,
            headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
        )

    return enforce
