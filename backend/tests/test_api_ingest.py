"""Upload and table-view API contract (RF1).

The upload endpoint is the only way a session gets data, so these tests pin both
halves: the accepted real export (715 rows, 12 columns, quality report) and the
rejected error paths, which must leave the session exactly as it was.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.api.session import session_store
from app.config import Settings, get_settings
from app.ingest.loader import REQUIRED_COLUMNS
from app.main import app

EXPORT = Path(__file__).resolve().parents[2] / "SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


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
    path: Path | None = None,
    payload: bytes | None = None,
    name: str | None = None,
    content_type: str = XLSX_MIME,
) -> Any:
    body = payload if payload is not None else (path or EXPORT).read_bytes()
    return client.post(
        "/api/upload",
        files={"file": (name or (path or EXPORT).name, body, content_type)},
    )


def write_export(path: Path, **overrides: list[Any]) -> Path:
    """Write a minimal but schema-complete export, one list per column."""
    rows = overrides.pop("rows", None)
    width = rows if rows is not None else 2
    columns: dict[str, list[Any]] = {
        column: [f"{column}-{index}" for index in range(width)]
        for column in REQUIRED_COLUMNS
    }
    columns["Timestamp"] = [
        f"2026-10-23 07:4{index}:00" for index in range(width)
    ]
    columns["Event_ID"] = [4624] * width
    columns["Source_IP"] = ["10.10.1.22"] * width
    columns["Destination"] = ["DC-01"] * width
    columns["Result"] = ["Success"] * width
    columns["Severity"] = ["Informational"] * width
    columns.update(overrides)
    pd.DataFrame(columns).to_excel(path, index=False)
    return path


def test_upload_of_the_real_export_returns_rows_columns_and_quality(
    client: TestClient,
) -> None:
    response = upload(client)

    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 715
    assert len(body["detected_columns"]) == 12
    assert body["detected_columns"][0] == "Log_ID"
    assert body["time_range"] == {
        "start": "2026-10-23T07:46:07",
        "end": "2026-10-23T13:44:06",
    }
    assert body["quality"]["duplicate_hosts"][0]["host_norm"] == "DC01"
    assert body["quality"]["event_id_types"]["named_ids"] == {
        "HTTP_ACCESS": 21,
        "PROXY_ACCESS": 22,
    }


def test_non_xlsx_upload_is_rejected_and_leaves_the_session_empty(
    client: TestClient,
) -> None:
    response = upload(
        client,
        payload=b"Log_ID,Timestamp\nEVT-00001,2026-10-23\n",
        name="logs.csv",
        content_type="text/csv",
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Formato no admitido: solo se aceptan archivos .xlsx."
    assert client.get("/api/events").status_code == 409


def test_oversized_upload_is_rejected_with_the_configured_limit(
    client: TestClient,
) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(max_upload_mb=0)

    response = upload(client)

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "El archivo supera el tamaño máximo permitido de 0 MB."
    )
    assert client.get("/api/events").status_code == 409


def test_empty_upload_is_rejected(client: TestClient) -> None:
    response = upload(client, payload=b"", name="empty.xlsx")

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "El archivo está vacío. Seleccione un export .xlsx válido."
    )
    assert client.get("/api/events").status_code == 409


def test_workbook_without_the_siem_schema_is_rejected(
    client: TestClient, tmp_path: Path
) -> None:
    path = tmp_path / "random.xlsx"
    pd.DataFrame({"foo": [1], "bar": [2]}).to_excel(path, index=False)

    response = upload(client, path=path)

    assert response.status_code == 400
    assert "Faltan columnas" in response.json()["detail"]
    assert client.get("/api/events").status_code == 409


def test_events_before_any_upload_is_a_clean_conflict(client: TestClient) -> None:
    response = client.get("/api/events")

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Todavía no se ha cargado ningún archivo. Suba un export .xlsx y vuelva a intentarlo."
    )


def test_events_page_two_does_not_repeat_page_one(client: TestClient) -> None:
    upload(client)

    first = client.get("/api/events", params={"page": 1, "page_size": 5}).json()
    second = client.get("/api/events", params={"page": 2, "page_size": 5}).json()

    assert first["total"] == 715
    assert first["total_pages"] == 143
    assert [row["Log_ID"] for row in first["items"]] == [
        "EVT-00001",
        "EVT-00002",
        "EVT-00003",
        "EVT-00004",
        "EVT-00005",
    ]
    assert second["items"][0]["Log_ID"] == "EVT-00006"
    assert not {row["Log_ID"] for row in first["items"]} & {
        row["Log_ID"] for row in second["items"]
    }


def test_page_size_above_the_maximum_is_clamped(client: TestClient) -> None:
    upload(client)

    body = client.get("/api/events", params={"page": 1, "page_size": 100_000}).json()

    assert body["page_size"] == 200
    assert len(body["items"]) == 200
    assert body["total_pages"] == 4


def test_page_below_one_is_clamped(client: TestClient) -> None:
    upload(client)

    body = client.get("/api/events", params={"page": 0, "page_size": 2}).json()

    assert body["page"] == 1
    assert body["items"][0]["Log_ID"] == "EVT-00001"


def test_event_rows_carry_the_original_and_derived_columns(client: TestClient) -> None:
    upload(client)

    row = client.get("/api/events", params={"page_size": 1}).json()["items"][0]

    assert row["Log_ID"] == "EVT-00001"
    assert row["Event_ID"] == 7036
    assert row["event_id_norm"] == "7036"
    assert row["host_norm"] == "WS018"
    assert row["timestamp"] == "2026-10-23T07:46:07"
    assert row["Destination"] == "DC-01"
    assert row["is_failure"] is False
    assert row["ip_class"] == "internal"


def test_null_cells_serialize_as_json_null(client: TestClient, tmp_path: Path) -> None:
    """NaN/NaT must become `null`, never the literal string "nan"."""
    path = write_export(
        tmp_path / "with_nulls.xlsx",
        Destination=[None, "WEB-01:443"],
        Process_CommandLine=[None, "whoami"],
    )

    response = upload(client, path=path)

    assert response.status_code == 200
    row = client.get("/api/events", params={"page_size": 1}).json()["items"][0]
    assert row["Destination"] is None
    assert row["dest_port"] is None
    assert row["Process_CommandLine"] is None


def test_search_filters_the_event_table(client: TestClient) -> None:
    upload(client)

    body = client.get(
        "/api/events", params={"search": "PROXY_ACCESS", "page_size": 200}
    ).json()

    assert body["total"] == 22
    assert {row["event_id_norm"] for row in body["items"]} == {"PROXY_ACCESS"}


def test_sort_order_is_applied_before_pagination(client: TestClient) -> None:
    upload(client)

    body = client.get(
        "/api/events", params={"sort": "Log_ID", "order": "desc", "page_size": 1}
    ).json()

    assert body["items"][0]["Log_ID"] == "EVT-00715"


def test_unknown_sort_column_is_rejected_in_spanish(client: TestClient) -> None:
    upload(client)

    response = client.get("/api/events", params={"sort": "no_existe"})

    assert response.status_code == 400
    assert "Columna de ordenamiento no válida" in response.json()["detail"]


def test_unknown_order_is_rejected_in_spanish(client: TestClient) -> None:
    upload(client)

    response = client.get("/api/events", params={"order": "sideways"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Orden no válido: use 'asc' o 'desc'."


def test_a_second_upload_replaces_the_session(client: TestClient, tmp_path: Path) -> None:
    upload(client)
    small = write_export(tmp_path / "small.xlsx")

    response = upload(client, path=small)

    assert response.status_code == 200
    assert response.json()["row_count"] == 2
    assert client.get("/api/events").json()["total"] == 2
