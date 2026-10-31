"""In-memory session state for the loaded export (RF1, RF4).

Single process, single frame, no persistence: the demo runs one analyst and a
restart is cheap. The store is a module singleton behind a lock because FastAPI
runs synchronous endpoints in a thread pool, and tests reset it between cases.

The analysis result is cached next to the frame it was computed from. The cache
is keyed by frame identity, so a new upload invalidates it by construction: a
stale incident list can never be served for a different export.
"""

from __future__ import annotations

import threading

import pandas as pd

from app.api.analysis import Analysis


class SessionStore:
    """Hold at most one loaded frame and its analysis: a new upload replaces both."""

    def __init__(self) -> None:
        self._frame: pd.DataFrame | None = None
        self._analysis: Analysis | None = None
        self._lock = threading.Lock()

    def store(self, frame: pd.DataFrame) -> None:
        with self._lock:
            self._frame = frame
            self._analysis = None

    def frame(self) -> pd.DataFrame | None:
        """Return the loaded frame, or `None` when nothing has been uploaded."""
        with self._lock:
            return self._frame

    def analysis(self, frame: pd.DataFrame) -> Analysis | None:
        """Cached analysis of `frame`, or `None` when this frame was not analysed yet."""
        with self._lock:
            return self._analysis if self._frame is frame else None

    def store_analysis(self, frame: pd.DataFrame, analysis: Analysis) -> None:
        """Cache `analysis`, but never against a frame that has been replaced."""
        with self._lock:
            if self._frame is frame:
                self._analysis = analysis

    def clear(self) -> None:
        with self._lock:
            self._frame = None
            self._analysis = None


session_store = SessionStore()
