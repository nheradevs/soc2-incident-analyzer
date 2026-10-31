"""RF8 / FSD §5: upload content validation and basic rate limiting.

The extension and the client-declared media type describe what the client *says*
the upload is. These tests pin that the endpoint instead asks the bytes: an
`.xlsx` is a ZIP container with `[Content_Types].xml` and an `xl/` workbook part,
so a renamed executable, an old OLE2 `.xls` and a ZIP without a workbook are
rejected in Spanish, while a legitimate `curl -F file=@export.xlsx` (which sends
`application/octet-stream`) is still accepted.

The limiter half pins the deployment contract: a fixed window per client and per
endpoint, a Spanish 429 with `Retry-After`, no budget for a spoofed
`X-Forwarded-For`, no effect on `/api/health`, and a session that survives a
rejection.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api.ratelimit import UNKNOWN_CLIENT, RateLimiter, client_identity, limiter
from app.api.session import session_store
from app.config import Settings, get_settings
from app.main import app

EXPORT = Path(__file__).resolve().parents[2] / "SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ROW_COUNT = 715
WINDOW_SECONDS = 60

# The bytes Starlette hands us for an old-style Excel workbook (OLE2 compound file).
OLE2_XLS = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 512
TEXT_PAYLOAD = b"Log_ID,Timestamp\nEVT-00001,2026-10-23 07:46:07\n"

NOT_A_ZIP_MESSAGE = (
    "El contenido del archivo no es un libro .xlsx válido: no es un contenedor ZIP. "
    "Verifique que el archivo no se haya renombrado desde otro formato."
)
OLD_XLS_MESSAGE = (
    "El archivo es un libro .xls antiguo (formato binario OLE2). "
    "Ábralo en Excel y guárdelo como .xlsx antes de subirlo."
)
NO_WORKBOOK_MESSAGE = (
    "El archivo es un ZIP, pero no contiene un libro de Excel: "
    "falta [Content_Types].xml o la parte xl/ del libro."
)
RATE_LIMIT_MESSAGE = (
    "Demasiadas solicitudes en poco tiempo. Espere unos segundos y vuelva a intentarlo."
)

LIMIT_FIELDS = {
    "/api/upload": "rate_limit_upload",
    "/api/analyze": "rate_limit_analyze",
    "/api/report": "rate_limit_report",
    "/api/report/pdf": "rate_limit_pdf",
}


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """Isolated process state: no leftover frame and no leftover settings override."""
    session_store.clear()
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    session_store.clear()


def upload(
    client: TestClient,
    payload: bytes | None = None,
    *,
    name: str = EXPORT.name,
    content_type: str = XLSX_MIME,
) -> Any:
    body = payload if payload is not None else EXPORT.read_bytes()
    return client.post("/api/upload", files={"file": (name, body, content_type)})


def zip_payload(*names: str) -> bytes:
    """A real ZIP container holding exactly the given member names."""
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name in names:
            archive.writestr(name, b"placeholder")
    return buffer.getvalue()


def settings_with(limit_field: str, limit: int, **overrides: Any) -> Settings:
    """Settings where only `limit_field` is tight and every other bucket is wide."""
    values: dict[str, Any] = dict.fromkeys(LIMIT_FIELDS.values(), 1000)
    values[limit_field] = limit
    values.update(overrides)
    return Settings(rate_limit_window_seconds=WINDOW_SECONDS, **values)


def call_protected(client: TestClient, path: str) -> Any:
    """One request against a protected endpoint, with the session already loaded."""
    if path == "/api/upload":
        return upload(client)
    if path == "/api/report/pdf":
        return client.get(path)
    return client.post(path)


# --- content validation -----------------------------------------------------


def test_a_real_xlsx_export_is_accepted(client: TestClient) -> None:
    response = upload(client)

    assert response.status_code == 200
    assert response.json()["row_count"] == ROW_COUNT


def test_a_text_file_renamed_to_xlsx_is_rejected_in_spanish(
    client: TestClient,
) -> None:
    response = upload(client, TEXT_PAYLOAD)

    assert response.status_code == 400
    assert response.json()["detail"] == NOT_A_ZIP_MESSAGE
    assert client.get("/api/events").status_code == 409


def test_an_old_style_xls_is_rejected_with_its_own_message(
    client: TestClient,
) -> None:
    response = upload(client, OLE2_XLS, name="export.xlsx")

    assert response.status_code == 400
    assert response.json()["detail"] == OLD_XLS_MESSAGE
    assert client.get("/api/events").status_code == 409


def test_a_zip_without_a_workbook_part_is_rejected(client: TestClient) -> None:
    response = upload(client, zip_payload("readme.txt", "docs/notes.md"))

    assert response.status_code == 400
    assert response.json()["detail"] == NO_WORKBOOK_MESSAGE
    assert client.get("/api/events").status_code == 409


def test_a_zip_with_content_types_but_no_workbook_part_is_rejected(
    client: TestClient,
) -> None:
    response = upload(client, zip_payload("[Content_Types].xml", "readme.txt"))

    assert response.status_code == 400
    assert response.json()["detail"] == NO_WORKBOOK_MESSAGE


def test_a_zip_with_a_workbook_folder_but_no_content_types_is_rejected(
    client: TestClient,
) -> None:
    response = upload(client, zip_payload("xl/workbook.xml"))

    assert response.status_code == 400
    assert response.json()["detail"] == NO_WORKBOOK_MESSAGE


@pytest.mark.parametrize(
    "declared_type",
    ["application/octet-stream", "text/plain", "application/x-msexcel"],
)
def test_the_declared_content_type_is_not_the_gate(
    client: TestClient, declared_type: str
) -> None:
    response = upload(client, content_type=declared_type)

    assert response.status_code == 200
    assert response.json()["row_count"] == ROW_COUNT


def test_a_rejected_upload_leaves_the_previous_session_intact(
    client: TestClient,
) -> None:
    assert upload(client).status_code == 200

    rejected = upload(client, TEXT_PAYLOAD, name="broken.xlsx")

    assert rejected.status_code == 400
    events = client.get("/api/events")
    assert events.status_code == 200
    assert events.json()["total"] == ROW_COUNT
    assert client.post("/api/analyze").status_code == 200


# --- rate limiting ----------------------------------------------------------


@pytest.mark.parametrize("path", list(LIMIT_FIELDS))
def test_every_protected_endpoint_answers_429_with_retry_after(
    client: TestClient, path: str
) -> None:
    assert upload(client).status_code == 200
    # The setup upload above counted against the upload bucket; start the measured
    # window from a clean slate so the tight limit is the only thing in play.
    limiter.reset()
    app.dependency_overrides[get_settings] = lambda: settings_with(
        LIMIT_FIELDS[path], 2
    )

    allowed = [call_protected(client, path).status_code for _ in range(2)]
    blocked = call_protected(client, path)

    assert allowed == [200, 200]
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == RATE_LIMIT_MESSAGE
    retry_after = blocked.headers["retry-after"]
    assert retry_after.isdigit()
    assert 1 <= int(retry_after) <= WINDOW_SECONDS


def test_the_health_probe_is_never_rate_limited(client: TestClient) -> None:
    assert upload(client).status_code == 200
    app.dependency_overrides[get_settings] = lambda: settings_with(
        "rate_limit_analyze", 1
    )
    assert client.post("/api/analyze").status_code == 200
    assert client.post("/api/analyze").status_code == 429

    for _ in range(5):
        assert client.get("/api/health").status_code == 200


def test_the_limit_is_per_client() -> None:
    settings = settings_with("rate_limit_analyze", 1)
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with (
            TestClient(app, client=("10.10.7.1", 40000)) as first,
            TestClient(app, client=("10.10.7.2", 40000)) as second,
        ):
            assert upload(first).status_code == 200
            assert first.post("/api/analyze").status_code == 200
            assert first.post("/api/analyze").status_code == 429
            assert second.post("/api/analyze").status_code == 200
    finally:
        app.dependency_overrides.clear()
        session_store.clear()


def test_a_spoofed_forwarding_header_does_not_grant_a_fresh_budget(
    client: TestClient,
) -> None:
    assert upload(client).status_code == 200
    app.dependency_overrides[get_settings] = lambda: settings_with(
        "rate_limit_analyze", 1
    )
    assert client.post("/api/analyze").status_code == 200

    spoofed = client.post(
        "/api/analyze",
        headers={
            "X-Forwarded-For": "203.0.113.99",
            "X-Real-IP": "203.0.113.99",
            "Forwarded": "for=203.0.113.99",
        },
    )

    assert spoofed.status_code == 429
    assert spoofed.json()["detail"] == RATE_LIMIT_MESSAGE


def test_a_rate_limited_request_does_not_corrupt_the_session(
    client: TestClient,
) -> None:
    assert upload(client).status_code == 200
    app.dependency_overrides[get_settings] = lambda: settings_with(
        "rate_limit_analyze", 1
    )
    baseline = client.post("/api/analyze").json()

    assert client.post("/api/analyze").status_code == 429
    events = client.get("/api/events")
    assert events.status_code == 200
    assert events.json()["total"] == ROW_COUNT

    limiter.reset()
    assert client.post("/api/analyze").json() == baseline


def test_rate_limiting_can_be_switched_off_from_settings(client: TestClient) -> None:
    assert upload(client).status_code == 200
    app.dependency_overrides[get_settings] = lambda: settings_with(
        "rate_limit_analyze", 1, rate_limit_enabled=False
    )

    assert [client.post("/api/analyze").status_code for _ in range(3)] == [200] * 3


def test_the_budget_is_restored_when_the_window_expires() -> None:
    now = [1000.0]
    window_limiter = RateLimiter(clock=lambda: now[0])
    key = ("10.0.0.9", "analyze")

    assert window_limiter.hit(key, limit=1, window_seconds=WINDOW_SECONDS) is None
    retry_after = window_limiter.hit(key, limit=1, window_seconds=WINDOW_SECONDS)
    assert retry_after is not None
    assert 0 < retry_after <= WINDOW_SECONDS

    now[0] += WINDOW_SECONDS
    assert window_limiter.hit(key, limit=1, window_seconds=WINDOW_SECONDS) is None


def test_the_default_budget_comfortably_covers_a_demo_session() -> None:
    defaults = Settings()

    assert defaults.rate_limit_enabled is True
    assert defaults.rate_limit_window_seconds == WINDOW_SECONDS
    assert defaults.rate_limit_upload >= 10
    assert defaults.rate_limit_analyze >= 60
    assert defaults.rate_limit_report >= 30
    assert defaults.rate_limit_pdf >= 10


def test_a_request_without_a_peer_address_shares_one_bucket() -> None:
    """No peer address means one shared bucket, and the header is still ignored."""
    request = Request(
        {
            "type": "http",
            "client": None,
            "headers": [(b"x-forwarded-for", b"203.0.113.99")],
        }
    )

    assert client_identity(request) == UNKNOWN_CLIENT
