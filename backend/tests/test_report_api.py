"""`POST /api/report` (FSD RF5, RF7 / S5, S7).

The deterministic report is the product: it must be complete in every narrative
state. Assisted writing is optional, and its three states (`aplicada`,
`no_configurada`, `deshabilitada_por_error`) must be distinguishable in the
payload. This file also pins that the API key never reaches a response and that
the existing endpoints keep working.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.report import get_narrative_client
from app.api.session import session_store
from app.config import Settings, get_settings
from app.main import app
from app.reporting.narrative import NarrativeClient

EXPORT = Path(__file__).resolve().parents[2] / "SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
NO_SESSION_MESSAGE = (
    "Todavía no se ha cargado ningún archivo. Suba un export .xlsx y vuelva a intentarlo."
)

API_KEY = "test-key-do-not-leak-0b2f"
ACCEPTED_TEXT = (
    "El incidente INC-20261023-0820, de criticidad crítico, sigue siendo el riesgo "
    "principal del análisis. Se recomienda validar la evidencia y contener el acceso."
)
REJECTED_TEXT = (
    "El incidente INC-20261023-0820 acumula la evidencia EVT-99999 y mantiene "
    "criticidad crítico."
)
API_URL = "https://api.nan.builders/v1/chat/completions"
NINE_SECTIONS = 9


@pytest.fixture()
def client() -> Iterator[TestClient]:
    session_store.clear()
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    session_store.clear()


def configure(
    *, key: str, transport: httpx.BaseTransport | None = None
) -> Settings:
    """Point the endpoint at a settings object (and an optional fake provider)."""
    settings = Settings(nan_api_key=key)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_narrative_client] = lambda: NarrativeClient(
        settings, transport=transport
    )
    return settings


def stream_of(text: str) -> bytes:
    chunk = json.dumps({"choices": [{"delta": {"content": text}}]}, ensure_ascii=False)
    return f"data: {chunk}\n\ndata: [DONE]\n\n".encode()


def sse_transport(text: str, seen: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=stream_of(text)
        )

    return httpx.MockTransport(handler)


def failing_transport(seen: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        raise httpx.ConnectError("connection refused", request=request)

    return httpx.MockTransport(handler)


def broken_transport(seen: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        raise RuntimeError("unexpected transport failure")

    return httpx.MockTransport(handler)


def upload(client: TestClient) -> None:
    response = client.post(
        "/api/upload", files={"file": (EXPORT.name, EXPORT.read_bytes(), XLSX_MIME)}
    )
    assert response.status_code == 200, response.text


def report(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/report")
    assert response.status_code == 200, response.text
    return response.json()


def sections(version: dict[str, Any]) -> list[dict[str, Any]]:
    return version["sections"]


def test_report_before_upload_is_a_conflict_in_spanish(client: TestClient) -> None:
    response = client.post("/api/report")

    assert response.status_code == 409
    assert response.json()["detail"] == NO_SESSION_MESSAGE


def test_without_a_key_the_report_is_complete_and_marked_not_configured(
    client: TestClient,
) -> None:
    configure(key="")
    upload(client)

    body = report(client)

    assert body["narrative"]["estado"] == "no_configurada"
    assert body["narrative"]["solicitudes"] == 0
    assert set(body["versions"]) == {"ejecutiva", "tecnica"}
    for version in body["versions"].values():
        assert version["narrative_status"] == "no_configurada"
        assert len(sections(version)) == NINE_SECTIONS
        assert all(item["body"] for item in sections(version))
        assert all(
            item["narrative"] in {"no_configurada", "plantilla"}
            for item in sections(version)
        )
    assert "715" in "\n".join(sections(body["versions"]["tecnica"])[0]["body"])
    assert "sin narrativa IA" not in json.dumps(body, ensure_ascii=False)


def test_the_missing_key_is_mentioned_once_without_drama(client: TestClient) -> None:
    configure(key="")
    upload(client)

    body = report(client)

    for version in body["versions"].values():
        text = "\n".join(
            paragraph for item in sections(version) for paragraph in item["body"]
        )
        assert text.count("Nota: la redacción asistida") == 1
        assert "no está configurada" in text


def test_two_reports_without_assisted_writing_are_byte_stable(
    client: TestClient,
) -> None:
    configure(key="")
    upload(client)

    first = report(client)
    second = report(client)

    assert first == second


def test_assisted_writing_is_applied_when_a_provider_answers(
    client: TestClient,
) -> None:
    seen: list[httpx.Request] = []
    configure(key=API_KEY, transport=sse_transport(ACCEPTED_TEXT, seen))
    upload(client)

    body = report(client)

    assert body["narrative"]["estado"] == "aplicada"
    assert body["narrative"]["solicitudes"] == body["narrative"]["secciones_aplicadas"]
    assert body["narrative"]["solicitudes"] > 0
    assert body["guard"]["rechazadas"] == []
    assert len(body["guard"]["aceptadas"]) == body["narrative"]["secciones_aplicadas"]
    for version in body["versions"].values():
        assert version["narrative_status"] == "aplicada"
        applied = [item for item in sections(version) if item["narrative"] == "aplicada"]
        assert applied
        assert all(item["body"] == [ACCEPTED_TEXT] for item in applied)
    assert "sin narrativa IA" not in json.dumps(body, ensure_ascii=False)


def test_the_provider_request_is_streaming_and_uses_the_configured_model(
    client: TestClient,
) -> None:
    seen: list[httpx.Request] = []
    configure(key=API_KEY, transport=sse_transport(ACCEPTED_TEXT, seen))
    upload(client)

    report(client)

    assert seen
    request = seen[0]
    payload = json.loads(request.content)
    assert request.method == "POST"
    assert str(request.url) == API_URL
    assert request.headers["authorization"] == f"Bearer {API_KEY}"
    assert payload["stream"] is True
    assert payload["model"] == "deepseek-v4-flash"
    assert payload["reasoning_effort"] == "low"
    assert payload["messages"][0]["role"] == "system"
    assert "no analizas" in payload["messages"][0]["content"]


def test_a_guarded_rejection_falls_back_and_is_reported(client: TestClient) -> None:
    seen: list[httpx.Request] = []
    configure(key=API_KEY, transport=sse_transport(REJECTED_TEXT, seen))
    upload(client)

    body = report(client)

    assert body["narrative"]["estado"] == "deshabilitada_por_error"
    assert body["guard"]["aceptadas"] == []
    assert len(body["guard"]["rechazadas"]) == body["narrative"]["solicitudes"]
    assert all(
        entry["reasons"] for entry in body["guard"]["rechazadas"]
    )
    assert any(
        "EVT-99999" in reason
        for entry in body["guard"]["rechazadas"]
        for reason in entry["reasons"]
    )
    for version in body["versions"].values():
        assert version["narrative_status"] == "deshabilitada_por_error"
        assert len(sections(version)) == NINE_SECTIONS
        assert all(item["body"] for item in sections(version))
        assert all(
            item["narrative"] in {"deshabilitada_por_error", "plantilla"}
            for item in sections(version)
        )
        assert all(
            "EVT-99999" not in paragraph
            for item in sections(version)
            for paragraph in item["body"]
        )


def test_a_provider_error_degrades_to_the_deterministic_report(
    client: TestClient,
) -> None:
    seen: list[httpx.Request] = []
    configure(key=API_KEY, transport=failing_transport(seen))
    upload(client)

    body = report(client)

    assert seen
    assert body["narrative"]["estado"] == "deshabilitada_por_error"
    assert body["narrative"]["secciones_con_error"] == body["narrative"]["solicitudes"]
    assert all(
        "conectar" in item["narrative_reason"]
        for version in body["versions"].values()
        for item in sections(version)
        if item["narrative"] == "deshabilitada_por_error"
    )
    for version in body["versions"].values():
        assert len(sections(version)) == NINE_SECTIONS
        assert all(item["body"] for item in sections(version))


def test_an_unexpected_provider_failure_never_fails_the_request(
    client: TestClient,
) -> None:
    seen: list[httpx.Request] = []
    configure(key=API_KEY, transport=broken_transport(seen))
    upload(client)

    body = report(client)

    assert seen
    assert body["narrative"]["estado"] == "deshabilitada_por_error"
    assert all(
        "no procesable" in item["narrative_reason"]
        for version in body["versions"].values()
        for item in sections(version)
        if item["narrative"] == "deshabilitada_por_error"
    )
    for version in body["versions"].values():
        assert len(sections(version)) == NINE_SECTIONS
        assert all(item["body"] for item in sections(version))


def test_the_api_key_never_reaches_the_payload(client: TestClient) -> None:
    configure(key=API_KEY, transport=sse_transport(ACCEPTED_TEXT, []))
    upload(client)

    response = client.post("/api/report")

    assert response.status_code == 200
    assert API_KEY not in response.text
    assert API_KEY not in json.dumps(response.json(), ensure_ascii=False)


def test_the_payload_exposes_both_versions_with_the_nine_mandatory_sections(
    client: TestClient,
) -> None:
    configure(key="")
    upload(client)

    body = report(client)

    expected_titles = [
        "1. Resumen ejecutivo",
        "2. Hallazgos identificados",
        "3. Explicación técnica de cada hallazgo",
        "4. Evidencias encontradas en los logs",
        "5. Criticidad y justificación",
        "6. Posible impacto en la organización",
        "7. Plan de acción: investigar → contener → remediar",
        "8. Recomendaciones generales de seguridad",
        "9. Limitaciones del análisis",
    ]
    for version in body["versions"].values():
        assert [item["title"] for item in sections(version)] == expected_titles
        assert all(item["number"] == index for index, item in enumerate(sections(version), 1))


def test_the_technical_version_cites_log_ids_and_the_executive_does_not(
    client: TestClient,
) -> None:
    configure(key="")
    upload(client)

    body = report(client)
    technical = "\n".join(
        paragraph
        for item in sections(body["versions"]["tecnica"])
        for paragraph in item["body"]
    )
    executive = "\n".join(
        paragraph
        for item in sections(body["versions"]["ejecutiva"])
        for paragraph in item["body"]
    )

    assert "EVT-" in technical
    assert "EVT-" not in executive
    assert body["scope"]["events_analysed"] == 715
    assert body["scope"]["incidents"] == 6


def test_existing_endpoints_still_work_after_a_report(client: TestClient) -> None:
    configure(key="")
    upload(client)
    body = report(client)
    incident_id = body["guard"] and next(iter(body["scope"]["incident_ids"]))

    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/events").json()["total"] == 715
    dashboard = client.post("/api/analyze").json()
    assert dashboard["coverage"]["incidents"] == 6
    assert client.get(f"/api/incidents/{incident_id}").status_code == 200
