"""Classification entry point (FSD RF3).

`classify(incidents)` is the only public entry point: it returns plain,
JSON-serialisable dicts with the incident payload plus a `risk` block on the
incident and on every finding. The report, the PDF and the dashboard consume
that single shape, so no consumer can re-derive a level of its own.

An incident takes the level of its most severe finding. When one of the findings
that set that level is marked `requires_validation`, the incident is capped at
`alto` and its justification says that no compromise is confirmed: an ambiguous
pattern is never presented as a fact (FSD §8, INC-6).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.detection.models import Finding, Incident
from app.risk.justification import finding_justification, incident_justification
from app.risk.matrix import (
    LEVEL_KEY,
    LEVEL_RANK,
    LEVELS,
    RiskScore,
    cap_level,
    score,
)

VALIDATED_INCIDENT_CAP = "alto"


@dataclass(frozen=True, slots=True)
class Assessment:
    """Level, matrix factors and rule-written justification of one unit."""

    level: str
    score: RiskScore
    requires_validation: bool
    justification: str

    def to_dict(self) -> dict[str, Any]:
        payload = self.score.to_dict()
        payload["level"] = self.level
        payload["level_key"] = LEVEL_KEY[self.level]
        payload["requires_validation"] = self.requires_validation
        payload["justification"] = self.justification
        return payload


def assess_finding(finding: Finding) -> Assessment:
    finding_score = score(finding)
    return Assessment(
        level=finding_score.level,
        score=finding_score,
        requires_validation=finding.requires_validation,
        justification=finding_justification(finding, finding_score),
    )


def _level_from_rank(rank: int) -> str:
    return next(level for level in LEVELS if LEVEL_RANK[level] == rank)


def assess_incident(incident: Incident) -> Assessment:
    scored = [(finding, score(finding)) for finding in incident.findings]
    if not scored:
        fallback = RiskScore(
            level=LEVELS[-1],
            impact=LEVELS[-1],
            confidence="baja",
            event_count=incident.event_count,
            single_row=True,
            requires_validation=incident.requires_validation,
        )
        return Assessment(
            level=LEVELS[-1],
            score=fallback,
            requires_validation=incident.requires_validation,
            justification=(
                f"Criticidad {LEVELS[-1]}: el incidente no tiene hallazgos correlacionados. "
                f"No alcanza «{LEVELS[-2]}»: no hay evidencia que clasificar."
            ),
        )

    top_rank = max(LEVEL_RANK[finding_score.level] for _, finding_score in scored)
    top_level = _level_from_rank(top_rank)
    governing = [
        finding
        for finding, finding_score in scored
        if LEVEL_RANK[finding_score.level] == top_rank
    ]
    governing.sort(key=lambda finding: (finding.first_seen, finding.id))
    governing_score = next(
        finding_score for finding, finding_score in scored if finding is governing[0]
    )
    validated_governing = next(
        (finding for finding in governing if finding.requires_validation), None
    )

    level = top_level
    if validated_governing is not None:
        level = cap_level(level, VALIDATED_INCIDENT_CAP)

    return Assessment(
        level=level,
        score=RiskScore(
            level=level,
            impact=governing_score.impact,
            confidence=governing_score.confidence,
            event_count=incident.event_count,
            single_row=governing_score.single_row,
            requires_validation=incident.requires_validation,
        ),
        requires_validation=incident.requires_validation,
        justification=incident_justification(
            incident, governing[0], governing_score, level, validated_governing
        ),
    )


def _payload(incident: Incident) -> dict[str, Any]:
    payload = incident.to_dict()
    payload["findings"] = [
        {**finding.to_dict(), "risk": assess_finding(finding).to_dict()}
        for finding in incident.findings
    ]
    payload["risk"] = assess_incident(incident).to_dict()
    return payload


def classify(incidents: Sequence[Incident]) -> list[dict[str, Any]]:
    """Classify every incident and every finding inside it (FSD RF3).

    Deterministic: the incident order of the detection engine is preserved and
    every level and justification is a pure function of the given objects.
    """
    return [_payload(incident) for incident in incidents]
