"""Content of the PDF export, read only from the composed report payload.

`POST /api/report` already returns everything the document needs: the scope
counts, the criticality distribution, the narrative state and the nine sections
of both versions. Nothing here computes a fact, a count or a finding — the only
licence this module takes is *presentation*: a deterministic bullet of the
report whose wording follows one of the known templates is turned into a table
row, and any bullet that does not match is rendered as a paragraph instead of
being guessed at.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

CLIENT_ES = "Consultora de ciberseguridad — Estocolmo"
DOCUMENT_TITLE_ES = "Informe de análisis de incidentes de seguridad"
DOCUMENT_SUBTITLE_ES = "SOC Nivel 2 — Análisis de export del SIEM"
DOCUMENT_PREFIX = "SOC2"
NO_INCIDENTS_ES = "sin incidentes"
HEADER_LEFT_ES = "Informe de análisis de incidentes de seguridad — SOC Nivel 2"
FOOTER_LEFT_ES = CLIENT_ES

LEVEL_TABLE_HEADER = ("Nivel", "Incidentes", "Hallazgos")
INCIDENT_TABLE_HEADER = ("Incidente", "Criticidad", "Ventana")
EVIDENCE_TABLE_HEADER = ("Incidente", "Log_ID (evidencia)")
EVIDENCE_WINDOW_HEADER = ("Incidente", "Ventana")

# Widths in centimetres; the horizontal margins of the page are 3.6 cm wide, so
# every table spans the 17.4 cm of the text column exactly.
LEVEL_TABLE_WIDTHS = (5.0, 3.0, 3.0)
INCIDENT_TABLE_WIDTHS = (8.6, 2.6, 6.2)
EVIDENCE_TABLE_WIDTHS = (4.4, 13.0)

VERSION_AUDIENCE_ES = {
    "ejecutiva": (
        "Documento dirigido a la dirección: impacto de negocio y plan de acción, sin "
        "identificadores técnicos."
    ),
    "tecnica": (
        "Documento dirigido al equipo técnico: detalle por hallazgo y evidencia con Log_ID."
    ),
}
CONTENTS_NOTE_ES = (
    "El documento reúne las dos versiones del mismo análisis, la ejecutiva primero y la "
    "técnica después. Cada versión contiene las nueve secciones obligatorias del informe."
)

# Neutral wording of the narrative state (FSD RF7). None of these lines presents
# the document as incomplete: the deterministic report is the product, and
# assisted writing is an optional extra.
NARRATIVE_NOTE_ES = {
    "aplicada": (
        "Redacción asistida: aplicada a las secciones de redacción. Las cifras, la "
        "clasificación y la evidencia provienen del motor de reglas."
    ),
    "parcial": (
        "Redacción asistida: aplicada parcialmente. Las demás secciones conservan la "
        "redacción determinística y el contenido está completo."
    ),
    "no_configurada": (
        "Redacción asistida: no configurada en esta instalación. El informe se genera "
        "íntegramente con el motor de reglas."
    ),
    "deshabilitada_por_error": (
        "Redacción asistida: no se aplicó en esta generación. El informe conserva la "
        "redacción determinística del motor de reglas."
    ),
}
NARRATIVE_NOTE_FALLBACK_ES = (
    "Redacción asistida: el informe se genera con el motor de reglas del análisis."
)

BLOCK_PARAGRAPH = "paragraph"
BLOCK_BULLET = "bullet"
BLOCK_TABLE = "table"

# One deterministic bullet of the report, recognised by its exact template. The
# export reads the fields back out of the wording the payload already contains;
# the patterns are anchored so a changed template degrades to a paragraph.
_TECH_INCIDENT_RE = re.compile(
    r"^• (?P<id>INC-\S+) · (?P<title>.+?) — criticidad (?P<level>\w+) "
    r"\(impacto [^)]+ × confianza [^)]+\), .+? eventos y .+? hallazgos\. "
    r"Ventana: (?P<start>\d{2}:\d{2}:\d{2}) → (?P<end>\d{2}:\d{2}:\d{2}) del "
    r"(?P<date>\d{2}/\d{2}/\d{4}) \(\d+ min\); .+\.$"
)
_EXEC_INCIDENT_RE = re.compile(
    r"^• (?P<title>.+?) — criticidad (?P<level>\w+)\. Agrupa .+? hallazgos sobre "
    r".+?, con .+? eventos registrados entre las (?P<start>\d{2}:\d{2}:\d{2}) y las "
    r"(?P<end>\d{2}:\d{2}:\d{2}) del (?P<date>\d{2}/\d{2}/\d{4})\.$"
)
_TECH_EVIDENCE_RE = re.compile(
    r"^(?P<id>INC-\S+) — .+? eventos de evidencia entre las "
    r"(?P<start>\d{2}:\d{2}:\d{2}) y las (?P<end>\d{2}:\d{2}:\d{2}) del "
    r"(?P<date>\d{2}/\d{2}/\d{4})\. Log_ID: (?P<logs>.+)\.$"
)
_EXEC_EVIDENCE_RE = re.compile(
    r"^• (?P<title>.+?): .+? eventos entre las (?P<start>\d{2}:\d{2}:\d{2}) y las "
    r"(?P<end>\d{2}:\d{2}:\d{2}) del (?P<date>\d{2}/\d{2}/\d{4})\.$"
)

_DATE_RE = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})")
_UNSAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class TableBlock:
    """A table of the document: header, rows and the column widths to use."""

    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    widths_cm: tuple[float, ...]


@dataclass(frozen=True)
class Block:
    """One unit of section content: a paragraph, a bullet or a table."""

    kind: str
    text: str = ""
    table: TableBlock | None = None


@dataclass(frozen=True)
class Section:
    """One of the nine sections of a version, ready to render."""

    key: str
    title: str
    blocks: tuple[Block, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Cover:
    """Everything the cover page states, taken from the report payload."""

    document_id: str
    title: str
    subtitle: str
    fields: tuple[tuple[str, str], ...]
    levels: tuple[tuple[str, ...], ...]
    narrative_note: str
    contents: tuple[tuple[str, tuple[str, ...]], ...]


def document_date(report: dict[str, Any]) -> str:
    """`20261023` from the analysis window start, or `''` when absent."""
    first_seen = str(report.get("scope", {}).get("first_seen") or "")
    match = _DATE_RE.match(first_seen)
    return match.group("year") + match.group("month") + match.group("day") if match else ""


def document_id(report: dict[str, Any]) -> str:
    """Stable identifier of the document, derived from the analysed date."""
    digits = document_date(report)
    return f"{DOCUMENT_PREFIX}-{digits}" if digits else DOCUMENT_PREFIX


def pdf_filename(report: dict[str, Any]) -> str:
    """Stable, ASCII, space-free attachment name with the analysed date."""
    digits = document_date(report)
    stem = f"informe-soc2-{digits}" if digits else "informe-soc2"
    return _UNSAFE_NAME_RE.sub("-", stem).strip("-") + ".pdf"


def duration_label(minutes: int) -> str:
    """`358` → `5 h 58 min`, the same wording the report uses."""
    hours, rest = divmod(int(minutes), 60)
    if hours and rest:
        return f"{hours} h {rest} min"
    if hours:
        return f"{hours} h"
    return f"{rest} min"


def window_label(scope: dict[str, Any]) -> str:
    """`23/10/2026, 07:46:07 a 13:44:06 (5 h 58 min)` from the report scope."""
    return (
        f"{scope.get('date', '')}, {scope.get('start', '')} a {scope.get('end', '')} "
        f"({duration_label(scope.get('duration_minutes', 0))})"
    )


def narrative_note(report: dict[str, Any]) -> str:
    """The neutral one-liner that states which narrative state applies."""
    state = str(report.get("narrative", {}).get("estado") or "")
    return NARRATIVE_NOTE_ES.get(state, NARRATIVE_NOTE_FALLBACK_ES)


def build_cover(report: dict[str, Any], *, generated_at: str) -> Cover:
    """Cover fields, criticality distribution and the table of contents."""
    scope = report["scope"]
    levels = tuple(
        (str(row["level"]), str(row["incidents"]), str(row["findings"]))
        for row in scope["levels"]
    )
    classification = next(
        (str(row["level"]) for row in scope["levels"] if row["incidents"]), NO_INCIDENTS_ES
    )
    fields = (
        ("Cliente", CLIENT_ES),
        ("Documento", document_id(report)),
        ("Ventana analizada", window_label(scope)),
        ("Fecha de generación", generated_at),
        ("Clasificación general del análisis", classification),
        ("Eventos analizados", str(scope["events_analysed"])),
        ("Incidentes", str(scope["incidents"])),
        ("Hallazgos", str(scope["findings"])),
        ("Cuentas afectadas", str(len(scope["users"]))),
        ("Equipos afectados", str(len(scope["hosts"]))),
        ("Orígenes externos identificados", str(len(scope["external_sources"]))),
    )
    contents = tuple(
        (
            str(version["label"]),
            tuple(str(section["title"]) for section in version["sections"]),
        )
        for version in report["versions"].values()
    )
    return Cover(
        document_id=document_id(report),
        title=DOCUMENT_TITLE_ES,
        subtitle=DOCUMENT_SUBTITLE_ES,
        fields=fields,
        levels=levels,
        narrative_note=narrative_note(report),
        contents=contents,
    )


def _table_from(lines: list[str], version: str) -> TableBlock | None:
    """Build the incidents table, or `None` when a line does not match."""
    pattern = _TECH_INCIDENT_RE if version == "tecnica" else _EXEC_INCIDENT_RE
    rows: list[tuple[str, ...]] = []
    for line in lines:
        match = pattern.match(line)
        if match is None:
            return None
        title = (
            f"{match['id']} · {match['title']}"
            if version == "tecnica"
            else match["title"]
        )
        rows.append(
            (title, match["level"], f"{match['start']} a {match['end']} del {match['date']}")
        )
    if not rows:
        return None
    return TableBlock(
        header=INCIDENT_TABLE_HEADER, rows=tuple(rows), widths_cm=INCIDENT_TABLE_WIDTHS
    )


def _evidence_table_from(lines: list[str], version: str) -> TableBlock | None:
    """Build the evidence table (`Log_ID` for the technical version)."""
    if version == "tecnica":
        rows = []
        for line in lines:
            match = _TECH_EVIDENCE_RE.match(line)
            if match is None:
                return None
            rows.append((match["id"], match["logs"]))
        if not rows:
            return None
        return TableBlock(
            header=EVIDENCE_TABLE_HEADER,
            rows=tuple(rows),
            widths_cm=EVIDENCE_TABLE_WIDTHS,
        )

    rows = []
    for line in lines:
        match = _EXEC_EVIDENCE_RE.match(line)
        if match is None:
            return None
        rows.append(
            (match["title"], f"{match['start']} a {match['end']} del {match['date']}")
        )
    if not rows:
        return None
    return TableBlock(
        header=EVIDENCE_WINDOW_HEADER,
        rows=tuple(rows),
        widths_cm=(11.0, 6.4),
    )


def _table_for(key: str, lines: list[str], version: str) -> TableBlock | None:
    if key == "hallazgos-identificados":
        return _table_from(lines, version)
    if key == "evidencias-logs":
        return _evidence_table_from(lines, version)
    return None


def _blocks_for(section: dict[str, Any], version: str) -> tuple[Block, ...]:
    """Paragraphs, bullets and the one table a section may carry."""
    body = [str(line) for line in section["body"]]
    blocks: list[Block] = []

    if len(body) > 1:
        table = _table_for(str(section["key"]), body[1:], version)
        if table is not None:
            blocks.append(Block(BLOCK_PARAGRAPH, body[0]))
            blocks.append(Block(BLOCK_TABLE, table=table))
            return tuple(blocks)

    for line in body:
        if line.startswith("• "):
            blocks.append(Block(BLOCK_BULLET, line[2:]))
        else:
            blocks.append(Block(BLOCK_PARAGRAPH, line))
    return tuple(blocks)


def sections_for(report: dict[str, Any], version: str) -> tuple[Section, ...]:
    """The nine sections of one version, ready to render."""
    return tuple(
        Section(
            key=str(section["key"]),
            title=str(section["title"]),
            blocks=_blocks_for(section, version),
        )
        for section in report["versions"][version]["sections"]
    )


def versions_for(report: dict[str, Any]) -> tuple[str, ...]:
    """Version keys in document order: executive first, then technical."""
    return tuple(report["versions"])


def audience_note(version: str) -> str:
    """One line telling the reader which audience document they are in."""
    return VERSION_AUDIENCE_ES[version]
