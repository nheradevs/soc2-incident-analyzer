"""Risk matrix (FSD RF3): impact potential × evidence confidence.

The level of a finding is produced in three auditable steps and combined in one
explicit table, so the classification never hides inside a chain of `if`s.

**Impact potential** answers what the observed behaviour can *do* if it is real.
It is keyed on the detector's own rule identity — the rule code, plus the rule
variant the detector publishes for `D4` (command pattern) and `D6` (anomaly
kind) — because two `D4` findings can be wildly different: `whoami` is merely a
reconnaissance step, an encoded PowerShell payload is code execution, and a
process spawned by the IIS application pool is a web shell.

**Evidence confidence** answers how strongly the cited rows support that reading,
using only facts the finding already carries:

- depth: how many independent `Log_ID` rows support it (1 row proves an event
  happened, not that it is part of an intrusion);
- breadth: how many distinct entities (accounts, hosts, source IPs, shares) the
  evidence covers;
- origin: an external source IP is the strongest discriminator of this export,
  because the measured baseline (FSD §6) has no external failures at all;
- `requires_validation`: the detector itself says the pattern is also compatible
  with legitimate administration or backup, which lowers the score.

The final level is `MATRIX[impact][confidence]`, then two hard caps:

- a finding with one evidence row can never be `crítico`;
- a finding marked `requires_validation` can never be presented above `alto`.

The SIEM `Severity` column and the detector's `severity_hint` are deliberately
**not** inputs: the first is documented as inconsistent (FSD §4.10) and the
second would make the matrix circular, since both express the detector's own
opinion rather than what the evidence measures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.detection.models import Finding
from app.ingest.normalize import ip_class

# Most severe first: the report and the dashboard order by this.
LEVELS = ("crítico", "alto", "medio", "bajo")
LEVEL_RANK = {"bajo": 0, "medio": 1, "alto": 2, "crítico": 3}
LEVEL_KEY = {"crítico": "critical", "alto": "high", "medio": "medium", "bajo": "low"}

IMPACT_LEVELS = ("bajo", "medio", "alto", "crítico")
CONFIDENCE_LEVELS = ("baja", "media", "alta")

# impact × confidence → level. The terraces are intentional: confidence can
# lower an impact reading by one step, never two, and it can never raise it.
MATRIX: dict[str, dict[str, str]] = {
    "crítico": {"alta": "crítico", "media": "alto", "baja": "medio"},
    "alto": {"alta": "alto", "media": "alto", "baja": "medio"},
    "medio": {"alta": "medio", "media": "medio", "baja": "bajo"},
    "bajo": {"alta": "bajo", "media": "bajo", "baja": "bajo"},
}

# Impact potential per (rule code, rule variant). A rule without a variant uses
# its own code as the variant (`variant_of`).
IMPACT_BY_RULE: dict[tuple[str, str], str] = {
    # Failed credential guessing only: the log shows attempts, not a compromise.
    ("D1a", "D1a"): "medio",
    ("D1b", "D1b"): "alto",
    ("D1c", "D1c"): "medio",
    # Failure → success: credentials are confirmed compromised.
    ("D1d", "D1d"): "crítico",
    ("D2", "D2"): "alto",
    ("D3", "D3"): "crítico",
    # D4 is split by command pattern: recon, execution and web shell differ.
    ("D4", "iis-apppool"): "crítico",
    ("D4", "powershell-codificado"): "alto",
    ("D4", "vssadmin-delete-shadows"): "alto",
    ("D4", "archivo-comprimido"): "alto",
    ("D4", "net-view"): "medio",
    ("D4", "programdata"): "medio",
    ("D4", "whoami"): "bajo",
    ("D5", "D5"): "alto",
    # D6 is split by anomaly kind: rarity says nothing, bulk reads and persistence do.
    ("D6", "rareza"): "bajo",
    ("D6", "lectura-masiva"): "alto",
    ("D6", "persistencia"): "alto",
    ("D7", "D7"): "alto",
}
DEFAULT_IMPACT = "medio"

# A logon on an administrative account from the internal network is ordinary
# operation; only the external origin makes D2 anything more than context.
INTERNAL_LOGON_IMPACT = "medio"

# The export names machines by role (`FS-SRV01`, `APP-SRV01`, `WEB-01`). A lateral
# hop whose target carries the file-server prefix concentrates the data, so the
# same behaviour has a larger blast radius.
FILE_SERVER_HOST_PREFIXES = ("FS", "FILE")
FILE_SERVER_IMPACT = "crítico"

# D7 impact is scaled by the volume the detector measured, in decimal megabytes
# (the same unit the detector's own rationale uses).
EXFIL_CRITICAL_MEGABYTES = 200.0
EXFIL_FALLBACK_IMPACT = "alto"

# Confidence scoring: (threshold, points). Depth is the first matching row.
DEPTH_POINTS: tuple[tuple[int, int], ...] = ((5, 3), (2, 2))
SINGLE_EVENT_POINTS = 1
BREADTH_MIN_ENTITIES = 3
BREADTH_POINTS = 1
EXTERNAL_ORIGIN_POINTS = 1
VALIDATION_PENALTY = 1
# (minimum points, confidence) — first matching row wins.
CONFIDENCE_BY_POINTS: tuple[tuple[int, str], ...] = ((4, "alta"), (2, "media"), (0, "baja"))

# Caps applied after the matrix.
SINGLE_ROW_CAP = "alto"
VALIDATION_CAP = "alto"

# `D6` persistence events: `4698` creates a scheduled task, `7045` installs a service.
D6_PERSISTENCE_VARIANTS = frozenset({"4698", "7045"})
_VARIANT_ALIASES = {"iis-apppool-defaultapppool": "iis-apppool"}

_MEASURED_MEGABYTES = re.compile(r"(\d[\d.]*,\d)\s*MB")


@dataclass(frozen=True, slots=True)
class RiskScore:
    """Matrix factors of one finding, before any wording is written."""

    level: str
    impact: str
    confidence: str
    event_count: int
    single_row: bool
    requires_validation: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "level_key": LEVEL_KEY[self.level],
            "impact": self.impact,
            "confidence": self.confidence,
            "event_count": self.event_count,
            "requires_validation": self.requires_validation,
        }


def _id_segment(finding: Finding) -> str:
    """Rule variant key the detector publishes inside `finding.id`.

    `detection.context.build_finding` composes ids as `code:variant@entity@time`,
    so the segment between the first colon and the first `@` is the rule's own
    variant — the command pattern for `D4`, the event id or the account for `D6`.
    An unexpected id shape falls back to the code instead of failing.
    """
    _, _, remainder = finding.id.partition(":")
    return remainder.split("@", 1)[0]


def variant_of(finding: Finding) -> str:
    if finding.code == "D4":
        return _VARIANT_ALIASES.get(_id_segment(finding), _id_segment(finding))
    if finding.code == "D6":
        segment = _id_segment(finding)
        if segment in D6_PERSISTENCE_VARIANTS:
            return "persistencia"
        return "lectura-masiva" if finding.requires_validation else "rareza"
    return finding.code


def measured_megabytes(finding: Finding) -> float | None:
    """Volume the D7 detector measured, read from its own rationale text.

    The detector publishes the byte count only in the rationale (and in no
    structured field), so the risk layer reads the number it already stated
    instead of recomputing the proxy rows itself.
    """
    if finding.code != "D7":
        return None
    match = _MEASURED_MEGABYTES.search(finding.rationale)
    if match is None:
        return None
    return float(match.group(1).replace(".", "").replace(",", "."))


def external_origin(finding: Finding) -> bool:
    return any(ip_class(source_ip) == "external" for source_ip in finding.entities.source_ips)


def targets_file_server(finding: Finding) -> bool:
    return any(
        host.upper().startswith(prefix)
        for host in finding.entities.hosts
        for prefix in FILE_SERVER_HOST_PREFIXES
    )


def entity_count(finding: Finding) -> int:
    entities = finding.entities
    return (
        len(entities.users) + len(entities.hosts) + len(entities.source_ips) + len(entities.shares)
    )


def impact_of(finding: Finding) -> str:
    """Impact potential of what the finding shows, with measurable amplifiers."""
    base = IMPACT_BY_RULE.get((finding.code, variant_of(finding)), DEFAULT_IMPACT)

    if finding.code == "D2" and not external_origin(finding):
        return INTERNAL_LOGON_IMPACT
    if finding.code == "D5" and targets_file_server(finding):
        return FILE_SERVER_IMPACT
    if finding.code == "D7":
        megabytes = measured_megabytes(finding)
        if megabytes is not None and megabytes >= EXFIL_CRITICAL_MEGABYTES:
            return "crítico"
        return EXFIL_FALLBACK_IMPACT
    return base


def confidence_of(finding: Finding) -> str:
    """Evidence confidence: depth, breadth, origin and declared ambiguity."""
    points = SINGLE_EVENT_POINTS
    for minimum, awarded in DEPTH_POINTS:
        if finding.event_count >= minimum:
            points = awarded
            break
    if entity_count(finding) >= BREADTH_MIN_ENTITIES:
        points += BREADTH_POINTS
    if external_origin(finding):
        points += EXTERNAL_ORIGIN_POINTS
    if finding.requires_validation:
        points -= VALIDATION_PENALTY
    for minimum, confidence in CONFIDENCE_BY_POINTS:
        if points >= minimum:
            return confidence
    return CONFIDENCE_LEVELS[0]


def cap_level(level: str, maximum: str) -> str:
    return level if LEVEL_RANK[level] <= LEVEL_RANK[maximum] else maximum


def level_of(impact: str, confidence: str, single_row: bool, requires_validation: bool) -> str:
    level = MATRIX[impact][confidence]
    if single_row:
        level = cap_level(level, SINGLE_ROW_CAP)
    if requires_validation:
        level = cap_level(level, VALIDATION_CAP)
    return level


def score(finding: Finding) -> RiskScore:
    impact = impact_of(finding)
    confidence = confidence_of(finding)
    single_row = finding.event_count <= 1 or len(finding.evidence) <= 1
    return RiskScore(
        level=level_of(impact, confidence, single_row, finding.requires_validation),
        impact=impact,
        confidence=confidence,
        event_count=finding.event_count,
        single_row=single_row,
        requires_validation=finding.requires_validation,
    )
