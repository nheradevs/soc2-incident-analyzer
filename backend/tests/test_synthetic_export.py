"""Volume fixture generator (FSD §7): a large synthetic export derived from the real one.

The deliverable analysis only ever runs on the client export; this fixture exists
so the performance claim of FSD §7 ("≥50k rows, analysis < 30 s") is measurable.
The generator must not invent data: every generated row is a verbatim copy of an
observed row, and the file declares itself synthetic.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

from app.detection import detect
from app.ingest.loader import load_export

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "make_synthetic_export.py"
REAL_EXPORT = REPO_ROOT / "SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx"


def _load_generator():
    spec = importlib.util.spec_from_file_location("make_synthetic_export", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generator():
    return _load_generator()


def test_the_generator_writes_the_requested_number_of_rows(generator, tmp_path) -> None:
    output = generator.build_synthetic_export(tmp_path / "fixture.xlsx", rows=1600, seed=7)

    assert len(pd.read_excel(output, sheet_name=0)) == 1600


def test_the_generated_export_keeps_the_twelve_column_schema(generator, tmp_path) -> None:
    output = generator.build_synthetic_export(tmp_path / "fixture.xlsx", rows=800, seed=7)

    generated = pd.read_excel(output, sheet_name=0)
    real = pd.read_excel(REAL_EXPORT, sheet_name=0)

    assert tuple(generated.columns) == tuple(real.columns) == generator.COLUMNS
    assert len(generator.COLUMNS) == 12
    timestamps = pd.to_datetime(generated["Timestamp"])
    assert list(timestamps) == sorted(timestamps)


def test_the_same_seed_produces_the_same_content(generator, tmp_path) -> None:
    first = generator.build_synthetic_export(tmp_path / "first.xlsx", rows=1600, seed=11)
    second = generator.build_synthetic_export(tmp_path / "second.xlsx", rows=1600, seed=11)

    pd.testing.assert_frame_equal(
        pd.read_excel(first, sheet_name=0), pd.read_excel(second, sheet_name=0)
    )


def test_the_generated_export_declares_itself_synthetic(generator, tmp_path) -> None:
    assert "SYNTHETIC" in generator.default_output_path(1600).name.upper()

    output = generator.build_synthetic_export(tmp_path / "fixture.xlsx", rows=800, seed=7)
    book = load_workbook(output, read_only=True)
    assert "SYNTHETIC" in " ".join(book.sheetnames).upper()
    assert "SYNTHETIC" in (book.properties.title or "").upper()
    assert "SYNTHETIC" in (book.properties.description or "").upper()


def test_the_default_row_count_covers_the_documented_volume(generator) -> None:
    assert generator.DEFAULT_ROWS >= 50_000
    assert "out" in generator.default_output_path(generator.DEFAULT_ROWS).parts


def test_every_generated_value_comes_from_the_real_export(generator, tmp_path) -> None:
    """No invented incident: the generator may only reuse values the export shows."""
    output = generator.build_synthetic_export(tmp_path / "fixture.xlsx", rows=1600, seed=7)

    generated = pd.read_excel(output, sheet_name=0, dtype=str)
    real = pd.read_excel(REAL_EXPORT, sheet_name=0, dtype=str)

    for column in ("Hostname", "Event_ID", "Log_Source", "Result", "Severity", "User"):
        assert set(generated[column].dropna()) <= set(real[column].dropna()), column
    assert generated["Log_ID"].is_unique


def test_the_generated_export_loads_and_analyses(generator, tmp_path) -> None:
    output = generator.build_synthetic_export(tmp_path / "fixture.xlsx", rows=1600, seed=7)

    incidents = detect(load_export(output))

    assert len(incidents) >= 2 * 6
