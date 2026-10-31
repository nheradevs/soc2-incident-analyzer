"""Risk classification (FSD RF3): impact potential × evidence confidence.

One public entry point — `classify(incidents)` — returns plain, JSON-serialisable
dicts with a `risk` block on the incident and on each finding, so the report,
the PDF and the dashboard read the same classification (single source of
truth). The matrix itself lives in `matrix.py` and the Spanish wording in
`justification.py`.
"""

from app.risk.classifier import Assessment, assess_finding, assess_incident, classify
from app.risk.matrix import LEVELS

__all__ = ["LEVELS", "Assessment", "assess_finding", "assess_incident", "classify"]
