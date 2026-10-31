"""Server-side PDF rendering of the composed report (FSD RF6 / S6).

ReportLab's platypus builds the document from the same payload `POST /api/report`
returns: no HTML, no headless browser, no screenshot, and no system library
beyond the pure-Python ReportLab wheel. The text is set in Helvetica, a standard
PDF font with WinAnsi encoding, so Spanish accents and arrows are real glyphs
and survive extraction from the generated file.

Document structure:

* cover — title, client, analysed window, generation date, overall
  classification, the counts of the analysis, the criticality distribution and
  one neutral line about the narrative state;
* contents — the two versions with the nine section titles of each;
* the executive version, then the technical one, each starting on a new page
  with its own banner, and each with its nine sections. The tabular sections of
  the payload are drawn as tables; everything else as paragraphs.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import HRFlowable

from app.export.content import (
    BLOCK_BULLET,
    BLOCK_PARAGRAPH,
    BLOCK_TABLE,
    CONTENTS_NOTE_ES,
    FOOTER_LEFT_ES,
    HEADER_LEFT_ES,
    LEVEL_TABLE_HEADER,
    LEVEL_TABLE_WIDTHS,
    Block,
    Cover,
    TableBlock,
    audience_note,
    build_cover,
    sections_for,
    versions_for,
)

INK = colors.HexColor("#1b2431")
MUTED = colors.HexColor("#5b6879")
RULE = colors.HexColor("#c7d0db")
ACCENT = colors.HexColor("#123a63")
BAND = colors.HexColor("#eef3f9")
STRIPE = colors.HexColor("#f6f9fc")
LEVEL_COLOR = {
    "crítico": colors.HexColor("#a91910"),
    "alto": colors.HexColor("#b35200"),
    "medio": colors.HexColor("#7d6200"),
    "bajo": colors.HexColor("#2c6e49"),
}

PAGE = A4
MARGIN_X = 1.8 * cm
MARGIN_TOP = 2.3 * cm
MARGIN_BOTTOM = 2.1 * cm
TEXT_WIDTH = PAGE[0] - 2 * MARGIN_X
HEADER_Y = PAGE[1] - 1.45 * cm
FOOTER_Y = 1.15 * cm
RULE_OFFSET = 0.26 * cm

DOCUMENT_CREATOR = "SOC2 Analyzer"
PAGE_LABEL_ES = "Página {page} de {total}"
DOCUMENT_LABEL_ES = "Documento {document_id}"

STYLES = {
    "title": ParagraphStyle(
        "cover_title",
        fontName="Helvetica-Bold",
        fontSize=23,
        leading=28,
        textColor=ACCENT,
        spaceAfter=6,
    ),
    "subtitle": ParagraphStyle(
        "cover_subtitle",
        fontName="Helvetica",
        fontSize=12,
        leading=16,
        textColor=MUTED,
    ),
    "cover_label": ParagraphStyle(
        "cover_label",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=12,
        textColor=MUTED,
    ),
    "cover_value": ParagraphStyle(
        "cover_value",
        fontName="Helvetica",
        fontSize=9.5,
        leading=12.5,
        textColor=INK,
    ),
    "banner": ParagraphStyle(
        "version_banner",
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=colors.white,
    ),
    "note": ParagraphStyle(
        "note",
        fontName="Helvetica-Oblique",
        fontSize=8.8,
        leading=12,
        textColor=MUTED,
        spaceAfter=6,
    ),
    "contents_title": ParagraphStyle(
        "contents_title",
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=ACCENT,
        spaceAfter=10,
    ),
    "contents_version": ParagraphStyle(
        "contents_version",
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=INK,
        spaceBefore=8,
        spaceAfter=3,
    ),
    "contents_item": ParagraphStyle(
        "contents_item",
        fontName="Helvetica",
        fontSize=9,
        leading=12.5,
        leftIndent=12,
        textColor=INK,
    ),
    "section": ParagraphStyle(
        "section_title",
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16.5,
        textColor=ACCENT,
        spaceBefore=13,
        spaceAfter=5,
        keepWithNext=1,
    ),
    "body": ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=9.6,
        leading=13.6,
        textColor=INK,
        alignment=TA_JUSTIFY,
        spaceAfter=4.5,
    ),
    "bullet": ParagraphStyle(
        "bullet",
        fontName="Helvetica",
        fontSize=9.6,
        leading=13.6,
        textColor=INK,
        leftIndent=13,
        bulletIndent=2,
        spaceAfter=3.5,
    ),
    "cell": ParagraphStyle(
        "cell",
        fontName="Helvetica",
        fontSize=8.4,
        leading=11,
        textColor=INK,
    ),
    "cell_head": ParagraphStyle(
        "cell_head",
        fontName="Helvetica-Bold",
        fontSize=8.4,
        leading=11,
        textColor=colors.white,
    ),
}


class _NumberedCanvas(pdf_canvas.Canvas):
    """Canvas that can print `Página N de M` with a known page total.

    The page states are kept until `save`; every page is replayed with its
    number before the file is closed. Pages are otherwise drawn exactly once.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._page_states: list[dict[str, Any]] = []

    def showPage(self) -> None:  # noqa: N802 - ReportLab API
        self._page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._page_states)
        for state in self._page_states:
            self.__dict__.update(state)
            self._draw_page_number(total)
            super().showPage()
        super().save()

    def _draw_page_number(self, total: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 7.5)
        self.setFillColor(MUTED)
        self.drawRightString(
            PAGE[0] - MARGIN_X,
            FOOTER_Y,
            PAGE_LABEL_ES.format(page=self._pageNumber, total=total),
        )
        self.restoreState()


def _xml(text: str) -> str:
    """Escape a payload string so it is literal text, never markup (RF8)."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _page_decorator(document_id: str) -> Any:
    """Header with the document identifier, footer with the client, per page."""

    def decorate(canvas_obj: pdf_canvas.Canvas, doc: Any) -> None:
        canvas_obj.saveState()
        canvas_obj.setStrokeColor(RULE)
        canvas_obj.setLineWidth(0.6)
        canvas_obj.setFont("Helvetica", 7.5)
        canvas_obj.setFillColor(MUTED)
        canvas_obj.drawString(MARGIN_X, HEADER_Y, HEADER_LEFT_ES)
        canvas_obj.drawRightString(
            PAGE[0] - MARGIN_X,
            HEADER_Y,
            DOCUMENT_LABEL_ES.format(document_id=document_id),
        )
        canvas_obj.line(
            MARGIN_X, HEADER_Y - RULE_OFFSET, PAGE[0] - MARGIN_X, HEADER_Y - RULE_OFFSET
        )
        canvas_obj.drawString(MARGIN_X, FOOTER_Y, FOOTER_LEFT_ES)
        canvas_obj.line(
            MARGIN_X, FOOTER_Y + RULE_OFFSET, PAGE[0] - MARGIN_X, FOOTER_Y + RULE_OFFSET
        )
        canvas_obj.restoreState()

    return decorate


def _data_table(block: TableBlock) -> Table:
    """Draw a payload table with wrapped cells and severity-coloured levels."""
    header = [Paragraph(_xml(label), STYLES["cell_head"]) for label in block.header]
    rows = [
        [Paragraph(_xml(value), STYLES["cell"]) for value in row] for row in block.rows
    ]
    table = Table(
        [header, *rows],
        colWidths=[width * cm for width in block.widths_cm],
        repeatRows=1,
        hAlign="LEFT",
    )
    commands: list[tuple[Any, ...]] = [
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for index in range(1, len(rows) + 1):
        if index % 2 == 0:
            commands.append(("BACKGROUND", (0, index), (-1, index), STRIPE))
    if block.header == LEVEL_TABLE_HEADER:
        for index, row in enumerate(block.rows, start=1):
            commands.append(
                ("TEXTCOLOR", (0, index), (0, index), LEVEL_COLOR.get(row[0], INK))
            )
    table.setStyle(TableStyle(commands))
    return table


def _block_flowables(block: Block) -> list[Any]:
    if block.kind == BLOCK_TABLE and block.table is not None:
        return [Spacer(1, 2), _data_table(block.table), Spacer(1, 6)]
    if block.kind == BLOCK_BULLET:
        return [Paragraph(_xml(block.text), STYLES["bullet"], bulletText="•")]
    if block.kind == BLOCK_PARAGRAPH:
        return [Paragraph(_xml(block.text), STYLES["body"])]
    return []


def _cover_flowables(cover: Cover) -> list[Any]:
    fields = [
        [
            Paragraph(_xml(label), STYLES["cover_label"]),
            Paragraph(_xml(value), STYLES["cover_value"]),
        ]
        for label, value in cover.fields
    ]
    field_table = Table(fields, colWidths=[6.4 * cm, 11.0 * cm], hAlign="LEFT")
    field_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -2), 0.3, RULE),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    levels = TableBlock(
        header=LEVEL_TABLE_HEADER, rows=cover.levels, widths_cm=LEVEL_TABLE_WIDTHS
    )
    note = Table(
        [[Paragraph(_xml(cover.narrative_note), STYLES["note"])]],
        colWidths=[TEXT_WIDTH],
        hAlign="LEFT",
    )
    note.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BAND),
                ("BOX", (0, 0), (-1, -1), 0.4, RULE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )

    return [
        Spacer(1, 1.0 * cm),
        Paragraph(_xml(cover.title), STYLES["title"]),
        Paragraph(_xml(cover.subtitle), STYLES["subtitle"]),
        Spacer(1, 0.35 * cm),
        HRFlowable(width="100%", thickness=1.1, color=ACCENT, spaceAfter=14),
        field_table,
        Spacer(1, 0.7 * cm),
        Paragraph("Distribución por criticidad", STYLES["cover_label"]),
        Spacer(1, 0.2 * cm),
        _data_table(levels),
        Spacer(1, 0.8 * cm),
        note,
    ]


def _contents_flowables(cover: Cover) -> list[Any]:
    flowables: list[Any] = [
        PageBreak(),
        Paragraph("Contenido del documento", STYLES["contents_title"]),
        Paragraph(_xml(CONTENTS_NOTE_ES), STYLES["note"]),
    ]
    for label, titles in cover.contents:
        flowables.append(Paragraph(_xml(label), STYLES["contents_version"]))
        flowables.extend(Paragraph(_xml(title), STYLES["contents_item"]) for title in titles)
    return flowables


def _version_flowables(report: dict[str, Any], version: str) -> list[Any]:
    label = str(report["versions"][version]["label"])
    banner = Table(
        [[Paragraph(_xml(label), STYLES["banner"])],
         [Paragraph(_xml(audience_note(version)), STYLES["note"])]],
        colWidths=[TEXT_WIDTH],
        hAlign="LEFT",
    )
    banner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("BACKGROUND", (0, 1), (-1, 1), BAND),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    flowables: list[Any] = [PageBreak(), banner, Spacer(1, 0.4 * cm)]
    for section in sections_for(report, version):
        flowables.append(Paragraph(_xml(section.title), STYLES["section"]))
        for block in section.blocks:
            flowables.extend(_block_flowables(block))
    return flowables


def render_pdf(report: dict[str, Any], *, generated_at: datetime | None = None) -> bytes:
    """Render the composed report as PDF bytes, deterministically for a payload."""
    stamp = (generated_at or datetime.now()).strftime("%d/%m/%Y %H:%M")
    cover = build_cover(report, generated_at=stamp)
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=PAGE,
        leftMargin=MARGIN_X,
        rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        title=cover.title,
        author=cover.fields[0][1],
        subject=cover.subtitle,
        creator=DOCUMENT_CREATOR,
    )
    story: list[Any] = list(_cover_flowables(cover))
    story.extend(_contents_flowables(cover))
    for version in versions_for(report):
        story.extend(_version_flowables(report, version))
    decorate = _page_decorator(cover.document_id)
    document.build(
        story,
        onFirstPage=decorate,
        onLaterPages=decorate,
        canvasmaker=_NumberedCanvas,
    )
    return buffer.getvalue()
