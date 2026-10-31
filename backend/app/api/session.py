"""In-memory session state for the loaded export (RF1).

Single process, single frame, no persistence: the demo runs one analyst and a
restart is cheap. The store is a module singleton behind a lock because FastAPI
runs synchronous endpoints in a thread pool, and tests reset it between cases.
"""

from __future__ import annotations

import threading

import pandas as pd


class SessionStore:
    """Hold at most one loaded frame: a new upload replaces the previous one."""

    def __init__(self) -> None:
        self._frame: pd.DataFrame | None = None
        self._lock = threading.Lock()

    def store(self, frame: pd.DataFrame) -> None:
        with self._lock:
            self._frame = frame

    def frame(self) -> pd.DataFrame | None:
        """Return the loaded frame, or `None` when nothing has been uploaded."""
        with self._lock:
            return self._frame

    def clear(self) -> None:
        with self._lock:
            self._frame = None


session_store = SessionStore()
