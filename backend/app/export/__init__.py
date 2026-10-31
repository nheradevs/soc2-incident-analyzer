"""PDF export of the composed report (FSD RF6 / S6).

`render_pdf` turns the payload of `POST /api/report` into a PDF with ReportLab
on the server; `pdf_filename` is the attachment name the API uses.
"""

from __future__ import annotations

from app.export.content import pdf_filename
from app.export.pdf import render_pdf

__all__ = ["pdf_filename", "render_pdf"]
