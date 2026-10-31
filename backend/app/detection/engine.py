"""Entry point of the detection engine (FSD RF2).

The detectors are independent pure functions over the normalized frame; only the
correlator combines them. `detect` is deterministic: the same frame always
produces the same findings, in the same order.
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from app.detection.anomalies import d6_anomalies
from app.detection.brute_force import (
    d1a_directed_brute_force,
    d1b_password_spray,
    d1c_external_exposure,
    d1d_post_compromise_logon,
)
from app.detection.commands import d4_command_execution
from app.detection.correlator import correlate
from app.detection.exfiltration import d7_exfiltration
from app.detection.lateral import d5_lateral_movement
from app.detection.logon import d2_suspicious_logons
from app.detection.models import Finding, Incident
from app.detection.privilege import d3_privilege_escalation

Detector = Callable[[pd.DataFrame | None], list[Finding]]

DETECTORS: tuple[Detector, ...] = (
    d1a_directed_brute_force,
    d1b_password_spray,
    d1c_external_exposure,
    d1d_post_compromise_logon,
    d2_suspicious_logons,
    d3_privilege_escalation,
    d4_command_execution,
    d5_lateral_movement,
    d6_anomalies,
    d7_exfiltration,
)


def findings(events: pd.DataFrame | None) -> list[Finding]:
    """Run every detector once and return the findings in a stable order."""
    collected = [finding for detector in DETECTORS for finding in detector(events)]
    return sorted(collected, key=lambda finding: (finding.first_seen, finding.id))


def detect(events: pd.DataFrame | None) -> list[Incident]:
    """Detect findings on a normalized export and correlate them into incidents."""
    return correlate(findings(events))
