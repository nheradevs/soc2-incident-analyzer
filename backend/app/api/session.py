"""In-memory session state for the loaded export (RF1, RF4).

Single process, single frame, no persistence: the demo runs one analyst and a
restart is cheap. The store is a module singleton behind a lock because FastAPI
runs synchronous endpoints in a thread pool, and tests reset it between cases.

The upload summary (`file_name`, row count, columns, time range and quality
report) is kept next to the frame, so a browser that reloads the page can
rebuild the load panel without uploading again. The analysis result and the
composed report are cached next to the frame they were computed from. Every
cache is keyed by frame identity, so a new upload invalidates them by
construction: a stale incident list or a stale report can never be served for
a different export.
"""

from __future__ import annotations

import threading
from typing import Any

import pandas as pd

from app.api.analysis import Analysis


class SessionStore:
    """Hold at most one loaded frame with its summary, analysis and report.

    A new upload replaces all four: the frame identity keys the caches and the
    summary is stored by the same call, so a stale result or a stale summary can
    never be served for a different export.
    """

    def __init__(self) -> None:
        self._frame: pd.DataFrame | None = None
        self._summary: dict[str, Any] | None = None
        self._analysis: Analysis | None = None
        self._report: dict[str, Any] | None = None
        self._lock = threading.Lock()

    def store(self, frame: pd.DataFrame, summary: dict[str, Any]) -> None:
        """Load `frame` and the upload summary that describes it."""
        with self._lock:
            self._frame = frame
            self._summary = summary
            self._analysis = None
            self._report = None

    def frame(self) -> pd.DataFrame | None:
        """Return the loaded frame, or `None` when nothing has been uploaded."""
        with self._lock:
            return self._frame

    def summary(self) -> dict[str, Any] | None:
        """Upload summary of the loaded frame, or `None` when nothing is loaded."""
        with self._lock:
            return self._summary

    def analysis(self, frame: pd.DataFrame) -> Analysis | None:
        """Cached analysis of `frame`, or `None` when this frame was not analysed yet."""
        with self._lock:
            return self._analysis if self._frame is frame else None

    def store_analysis(self, frame: pd.DataFrame, analysis: Analysis) -> None:
        """Cache `analysis`, but never against a frame that has been replaced."""
        with self._lock:
            if self._frame is frame:
                self._analysis = analysis

    def report(self, frame: pd.DataFrame) -> dict[str, Any] | None:
        """Composed report of `frame`, or `None` when it was not composed yet."""
        with self._lock:
            return self._report if self._frame is frame else None

    def store_report(self, frame: pd.DataFrame, report: dict[str, Any]) -> None:
        """Cache `report`, but never against a frame that has been replaced."""
        with self._lock:
            if self._frame is frame:
                self._report = report

    def clear(self) -> None:
        with self._lock:
            self._frame = None
            self._summary = None
            self._analysis = None
            self._report = None


session_store = SessionStore()
