"""Deterministic detection engine and correlator (FSD RF2, §6, §8).

Detectors are pure functions over the normalized frame produced by
`app.ingest.loader`; `detect` runs all of them and correlates the findings into
incidents. Nothing here writes state or calls an external service.
"""

from app.detection.correlator import correlate
from app.detection.engine import DETECTORS, detect, findings
from app.detection.models import (
    CATEGORIES,
    CATEGORY_LABEL_ES,
    SEVERITY_LEVELS,
    Entities,
    Finding,
    Incident,
)

__all__ = [
    "CATEGORIES",
    "CATEGORY_LABEL_ES",
    "DETECTORS",
    "SEVERITY_LEVELS",
    "Entities",
    "Finding",
    "Incident",
    "correlate",
    "detect",
    "findings",
]
