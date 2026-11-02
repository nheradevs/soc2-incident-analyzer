"""Session snapshot endpoint (RF1).

`GET /api/session` answers the question the browser cannot answer on its own
after a reload: does this process already hold an export? The summary it
returns is the same body `/api/upload` returns, so the UI rebuilds the load
panel from one shape whichever way the file arrived.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.api.session import session_store
from app.ingest.loader import REQUIRED_COLUMNS
from app.main import app

EXPORT = Path(__file__).resolve().parents[2] / "SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

SESSION_EMPTY_MESSAGE = (
    "Todavía no has cargado ningún archivo. Sube un export .xlsx para empezar."
)


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """Isolated process state: no leftover frame and no leftover summary."""
    session_store.clear()
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    session_store.clear()


def upload(client: TestClient, path: Path | None = None) -> Any:
    target = path or EXPORT
    return client.post(
        "/api/upload",
        files={"file": (target.name, target.read_bytes(), XLSX_MIME)},
    )


def write_export(path: Path, rows: int = 2) -> Path:
    """Write a minimal but schema-complete export, one row per requested index."""
    columns: dict[str, list[Any]] = {
        column: [f"{column}-{index}" for index in range(rows)]
        for column in REQUIRED_COLUMNS
    }
    columns["Timestamp"] = [f"2026-10-24 09:0{index}:00" for index in range(rows)]
    columns["Event_ID"] = [4625] * rows
    pd.DataFrame(columns).to_excel(path, index=False)
    return path


def test_session_before_any_upload_is_a_clean_conflict(client: TestClient) -> None:
    response = client.get("/api/session")

    assert response.status_code == 409
    assert response.json()["detail"] == SESSION_EMPTY_MESSAGE


def test_session_summary_matches_the_upload_response(client: TestClient) -> None:
    uploaded = upload(client).json()

    response = client.get("/api/session")

    assert response.status_code == 200
    assert response.json() == uploaded


def test_session_summary_includes_the_quality_report(client: TestClient) -> None:
    upload(client)

    quality = client.get("/api/session").json()["quality"]

    assert quality["row_count"] == 715
    assert quality["column_count"] == 12
    assert quality["duplicate_hosts"][0]["host_norm"] == "DC01"
    assert quality["event_id_types"]["named_ids"] == {
        "HTTP_ACCESS": 21,
        "PROXY_ACCESS": 22,
    }
    assert quality["timestamp_parse_failures"]["count"] == 0


def test_a_second_upload_replaces_the_session_summary(
    client: TestClient, tmp_path: Path
) -> None:
    upload(client)
    small = write_export(tmp_path / "pequeno.xlsx")

    second = upload(client, path=small).json()
    summary = client.get("/api/session").json()

    assert summary == second
    assert summary["file_name"] == "pequeno.xlsx"
    assert summary["row_count"] == 2
    assert summary["time_range"] == {
        "start": "2026-10-24T09:00:00",
        "end": "2026-10-24T09:01:00",
    }


def test_session_is_empty_again_after_the_session_is_cleared(client: TestClient) -> None:
    upload(client)
    session_store.clear()

    response = client.get("/api/session")

    assert response.status_code == 409
    assert response.json()["detail"] == SESSION_EMPTY_MESSAGE
