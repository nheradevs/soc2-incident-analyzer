"""`GET /api/report/pdf` (FSD RF6 / S6): the report as a server-rendered PDF.

The document is generated with ReportLab from the composed report payload, so it
contains real text: both Spanish versions, the same counts the dashboard shows
and the `Log_ID`s of the technical evidence. These tests read the bytes back
with `pypdf` and pin what the export promises — a valid PDF, both versions with
their nine sections, accents that survive extraction, a safe dated attachment
filename, a 409 before any upload and no provider secret anywhere in the file.

The provider is never called: every case overrides the narrative client.
"""

from __future__ import annotations

import io
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.api.report import get_narrative_client
from app.api.session import session_store
from app.config import Settings, get_settings
from app.main import app
from app.reporting.narrative import NarrativeClient

EXPORT = Path(__file__).resolve().parents[2] / "SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
NO_SESSION_MESSAGE = (
    "Todavía no se ha cargado ningún archivo. Sube un export .xlsx y vuelve a intentarlo."
)

API_KEY = "sk-test-do-not-leak-0b2f"
ACCEPTED_TEXT = (
    "El incidente INC-20261023-0820, de criticidad crítico, sigue siendo el riesgo "
    "principal del análisis. Se recomienda validar la evidencia y contener el acceso."
)
API_URL = "https://api.nan.builders/v1/chat/completions"
PDF_MEDIA_TYPE = "application/pdf"
MIN_PAGES = 5
MAX_DEMO_BYTES = 1_000_000
ATTACHMENT_RE = re.compile(r'^attachment; filename="(?P<name>[^"]+)"$')


@pytest.fixture()
def client() -> Iterator[TestClient]:
    session_store.clear()
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    session_store.clear()


def configure(*, key: str = "", transport: httpx.BaseTransport | None = None) -> None:
    """Point the endpoints at a settings object and an optional fake provider."""
    settings = Settings(nan_api_key=key)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_narrative_client] = lambda: NarrativeClient(
        settings, transport=transport
    )


def stream_of(text: str) -> bytes:
    chunk = json.dumps({"choices": [{"delta": {"content": text}}]}, ensure_ascii=False)
    return f"data: {chunk}\n\ndata: [DONE]\n\n".encode()


def sse_transport(text: str) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL(API_URL)
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=stream_of(text)
        )

    return httpx.MockTransport(handler)


def upload(client: TestClient) -> None:
    response = client.post(
        "/api/upload", files={"file": (EXPORT.name, EXPORT.read_bytes(), XLSX_MIME)}
    )
    assert response.status_code == 200, response.text


def report_payload(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/report")
    assert response.status_code == 200, response.text
    return response.json()


def download(client: TestClient) -> bytes:
    response = client.get("/api/report/pdf")
    assert response.status_code == 200, response.text
    return response.content


def pdf_text(payload: bytes) -> str:
    """All extracted text of the document, page by page."""
    reader = PdfReader(io.BytesIO(payload))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def cover_text(payload: bytes) -> str:
    return PdfReader(io.BytesIO(payload)).pages[0].extract_text() or ""


def _pages(payload: bytes) -> list[str]:
    return [page.extract_text() or "" for page in PdfReader(io.BytesIO(payload)).pages]


def test_pdf_before_upload_is_a_conflict_in_spanish(client: TestClient) -> None:
    configure()

    response = client.get("/api/report/pdf")

    assert response.status_code == 409
    assert response.json()["detail"] == NO_SESSION_MESSAGE


def test_the_response_is_an_ascii_pdf_attachment_with_a_dated_filename(
    client: TestClient,
) -> None:
    configure()
    upload(client)

    response = client.get("/api/report/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == PDF_MEDIA_TYPE
    disposition = response.headers["content-disposition"]
    match = ATTACHMENT_RE.match(disposition)
    assert match, disposition
    name = match.group("name")
    assert name.isascii()
    assert " " not in name
    assert name.endswith(".pdf")
    assert re.search(r"\d{8}", name), name


def test_the_document_starts_and_ends_like_a_pdf(client: TestClient) -> None:
    configure()
    upload(client)

    payload = download(client)

    assert payload.startswith(b"%PDF")
    assert payload.rstrip().endswith(b"%%EOF")


def test_the_document_has_more_than_five_pages(client: TestClient) -> None:
    configure()
    upload(client)

    reader = PdfReader(io.BytesIO(download(client)))

    assert len(reader.pages) > MIN_PAGES


def test_both_version_headings_are_present_executive_first(client: TestClient) -> None:
    configure()
    upload(client)

    text = pdf_text(download(client))

    assert "Versión ejecutiva" in text
    assert "Versión técnica" in text
    assert text.index("Versión ejecutiva") < text.index("Versión técnica")


def test_spanish_accents_survive_text_extraction(client: TestClient) -> None:
    configure()
    upload(client)

    text = pdf_text(download(client))

    for expected in ("crítico", "Hallazgos identificados", "Plan de acción", "Limitaciones"):
        assert expected in text, expected


def test_the_cover_reports_the_classification_and_the_counts(client: TestClient) -> None:
    configure()
    upload(client)
    body = report_payload(client)

    text = cover_text(download(client))

    assert "Consultora de ciberseguridad — Estocolmo" in text
    assert "Clasificación general del análisis" in text
    assert "crítico" in text
    assert str(body["scope"]["events_analysed"]) in text
    assert "Ventana analizada" in text
    assert "Fecha de generación" in text
    assert "SOC2-" in text


def test_the_cover_marks_assisted_writing_as_not_configured(client: TestClient) -> None:
    configure()
    upload(client)

    text = cover_text(download(client))

    assert "Redacción asistida: no configurada" in text
    assert "incompleto" not in text


def test_the_technical_evidence_table_cites_a_real_log_id(client: TestClient) -> None:
    configure()
    upload(client)
    body = report_payload(client)

    evidence_section = "\n".join(body["versions"]["tecnica"]["sections"][3]["body"])
    log_id = re.search(r"EVT-\d+", evidence_section)
    assert log_id, evidence_section

    text = pdf_text(download(client))

    assert log_id.group(0) in text


def test_no_provider_key_reaches_the_file(client: TestClient) -> None:
    configure(key=API_KEY, transport=sse_transport(ACCEPTED_TEXT))
    upload(client)
    body = report_payload(client)
    assert body["narrative"]["estado"] == "aplicada"

    payload = download(client)
    text = pdf_text(payload)

    assert API_KEY not in text
    assert "sk-" not in text
    assert "Bearer" not in text
    assert API_KEY.encode() not in payload


def test_the_report_is_composed_once_per_upload_not_once_per_download(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []

    from app.api import report as report_module

    compose = report_module.compose_report

    def counting_compose(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append(1)
        return compose(*args, **kwargs)

    monkeypatch.setattr(report_module, "compose_report", counting_compose)
    configure()
    upload(client)

    first = download(client)
    second = download(client)

    assert calls == [1]
    assert len(_pages(first)) == len(_pages(second))


def test_the_tabular_sections_are_rendered_as_tables(client: TestClient) -> None:
    configure()
    upload(client)

    text = pdf_text(download(client))

    assert "Nivel\nIncidentes\nHallazgos" in text  # criticality distribution on the cover
    assert "Incidente\nCriticidad\nVentana" in text  # incidents of both versions
    assert "Incidente\nLog_ID (evidencia)" in text  # technical evidence table


def test_the_pdf_stays_small_enough_for_a_demo(client: TestClient) -> None:
    configure()
    upload(client)

    payload = download(client)

    assert len(payload) < MAX_DEMO_BYTES


def test_the_report_endpoint_still_works_after_a_download(client: TestClient) -> None:
    configure()
    upload(client)

    download(client)
    body = report_payload(client)

    assert set(body["versions"]) == {"ejecutiva", "tecnica"}
    assert body["scope"]["events_analysed"] == 715
    assert client.get("/api/events").json()["total"] == 715
