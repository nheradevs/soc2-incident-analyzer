"""RF8: only the local frontend may call the API from a browser.

`CORSMiddleware` does not block requests; it withholds the
`Access-Control-Allow-Origin` grant so the browser discards the response.
These tests pin that contract, plus the method allow-list.
"""

from fastapi.testclient import TestClient

from app.main import app

ALLOWED_ORIGIN = "http://localhost:4200"
UNTRUSTED_ORIGIN = "http://evil.example"

client = TestClient(app)


def test_allowed_origin_receives_cors_grant() -> None:
    response = client.get("/api/health", headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_untrusted_origin_receives_no_cors_grant() -> None:
    response = client.get("/api/health", headers={"Origin": UNTRUSTED_ORIGIN})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_untrusted_origin_preflight_is_rejected() -> None:
    response = client.options(
        "/api/health",
        headers={"Origin": UNTRUSTED_ORIGIN, "Access-Control-Request-Method": "POST"},
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_methods_outside_get_and_post_are_not_allowed() -> None:
    response = client.request("DELETE", "/api/health", headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 405
