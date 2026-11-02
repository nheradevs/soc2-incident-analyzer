"""Anti-hallucination guard for assisted rewriting (FSD RF5 / S8).

The model is asked to rewrite a deterministic draft, never to analyse. Its text
is accepted only when all of the following hold:

* every `Log_ID` it cites belongs to the evidence allowed for that section (the
  executive version allows none, so it cannot leak technical identifiers);
* every `INC-` identifier it names exists in the analysis;
* every criticality it asserts is the one the classifier assigned, either to an
  incident named in the same sentence or, when the section covers a single
  level, to the section as a whole.

A rejected rewrite leaves the deterministic text untouched and records the
reasons, so a rejection can never remove content from the report.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass

from app.reporting.narrative import NARRATIVE_APPLIED, NARRATIVE_DISABLED_BY_ERROR

LOG_ID_PATTERN = re.compile(r"\bEVT-[0-9]+\b", re.IGNORECASE)
INCIDENT_PATTERN = re.compile(r"\bINC-[0-9]{4,}(?:-[0-9]{2,})?\b", re.IGNORECASE)
SENTENCE_BREAK = re.compile(r"(?<=[.!?;:])\s+|\n+")

LEVEL_ALIASES = {
    "critico": "crítico",
    "critica": "crítico",
    "criticos": "crítico",
    "criticas": "crítico",
    "alto": "alto",
    "alta": "alto",
    "altos": "alto",
    "altas": "alto",
    "medio": "medio",
    "media": "medio",
    "medios": "medio",
    "medias": "medio",
    "bajo": "bajo",
    "baja": "bajo",
    "bajos": "bajo",
    "bajas": "bajo",
}

_LEVEL_WORD = r"[a-záéíóúüñ]+"
CLAIM_PATTERNS = (
    re.compile(rf"criticidad\s*(?:de\s+|es\s+|:\s*)?«?({_LEVEL_WORD})»?", re.IGNORECASE),
    re.compile(
        rf"nivel\s+(?:de\s+criticidad\s+)?(?:es\s+|:\s*)?«?({_LEVEL_WORD})»?",
        re.IGNORECASE,
    ),
    re.compile(rf"severidad\s*(?:de\s+|es\s+|:\s*)?«?({_LEVEL_WORD})»?", re.IGNORECASE),
    re.compile(rf"clasificad[oa]\s+como\s+«?({_LEVEL_WORD})»?", re.IGNORECASE),
    re.compile(rf"riesgo\s+(?:de\s+|es\s+|:\s*)?«?({_LEVEL_WORD})»?", re.IGNORECASE),
)


@dataclass(frozen=True, slots=True)
class GuardContext:
    """What a section is allowed to say: its evidence and the real levels."""

    known_incident_levels: Mapping[str, str]
    allowed_log_ids: frozenset[str] = frozenset()
    single_incident: str | None = None
    version: str = "tecnica"
    section: str = ""


@dataclass(frozen=True, slots=True)
class GuardResult:
    """Verdict of the guard plus the citations it found in the text."""

    accepted: bool
    reasons: tuple[str, ...]
    log_ids: tuple[str, ...] = ()
    incidents: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SectionResolution:
    """Body finally used by the report and the state of its assisted writing."""

    body: list[str]
    narrative: str
    guard: GuardResult


def _plain(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.lower())
    stripped = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return stripped.strip("«»\"'.,;:() ")


def _claims(sentence: str) -> list[str]:
    found: list[str] = []
    for pattern in CLAIM_PATTERNS:
        for match in pattern.finditer(sentence):
            level = LEVEL_ALIASES.get(_plain(match.group(1)))
            if level is not None:
                found.append(level)
    return found


def _paragraphs(text: str) -> list[str]:
    """Plain-text paragraphs: markdown emphasis and bullets are normalised away."""
    paragraphs: list[str] = []
    for raw in text.splitlines():
        line = raw.strip().replace("**", "").replace("__", "")
        if not line:
            continue
        if line.startswith(("- ", "* ")):
            line = f"• {line[2:].strip()}"
        line = line.lstrip("#").strip()
        if line:
            paragraphs.append(line)
    return paragraphs or [text.strip()]


def _level_reason(claimed: str, expected: set[str]) -> str:
    label = " / ".join(sorted(expected)) if expected else "sin referencia"
    return (
        f"Afirma la criticidad «{claimed}» donde la clasificación del motor indica "
        f"«{label}»."
    )


def check(text: str, context: GuardContext) -> GuardResult:
    """Apply the rejection predicate to one rewritten section."""
    reasons: list[str] = []
    stripped = text.strip()
    if not stripped:
        return GuardResult(False, ("La redacción propuesta está vacía.",))

    log_ids = tuple(
        dict.fromkeys(match.group(0).upper() for match in LOG_ID_PATTERN.finditer(stripped))
    )
    incidents = tuple(
        dict.fromkeys(match.group(0).upper() for match in INCIDENT_PATTERN.finditer(stripped))
    )
    for log_id in log_ids:
        if log_id not in context.allowed_log_ids:
            reasons.append(
                "Cita un Log_ID que no pertenece a la evidencia de este apartado: "
                f"{log_id}."
            )
    for incident_id in incidents:
        if incident_id not in context.known_incident_levels:
            reasons.append(
                "Menciona un incidente que no existe en el análisis: "
                f"{incident_id}."
            )

    for sentence in SENTENCE_BREAK.split(stripped):
        named = [
            match.group(0).upper()
            for match in INCIDENT_PATTERN.finditer(sentence)
            if match.group(0).upper() in context.known_incident_levels
        ]
        claims = _claims(sentence)
        if not claims:
            continue
        if named:
            expected = {context.known_incident_levels[incident_id] for incident_id in named}
        elif context.single_incident is not None:
            expected = {context.known_incident_levels[context.single_incident]}
        else:
            expected = set(context.known_incident_levels.values())
        for claimed in claims:
            if len(expected) == 1 and claimed in expected:
                continue
            reasons.append(_level_reason(claimed, expected))

    return GuardResult(
        accepted=not reasons,
        reasons=tuple(reasons),
        log_ids=log_ids,
        incidents=incidents,
    )


def resolve(
    draft: str, *, fallback: list[str], context: GuardContext
) -> SectionResolution:
    """Use the rewrite only when the guard accepts it; otherwise keep the draft."""
    result = check(draft, context)
    if not result.accepted:
        return SectionResolution(
            body=list(fallback),
            narrative=NARRATIVE_DISABLED_BY_ERROR,
            guard=result,
        )
    return SectionResolution(
        body=_paragraphs(draft),
        narrative=NARRATIVE_APPLIED,
        guard=result,
    )
