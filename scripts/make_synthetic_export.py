"""Generate a large synthetic SIEM export from the real one (FSD §7 volume fixture).

The deliverable report only ever runs on the client export
(`SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx`, 715 rows). FSD §7 retires the
unverifiable "100k rows" claim and replaces it with a declared synthetic fixture
of at least 50,000 rows. This script builds that fixture.

What it does, and deliberately does not do:

* Every generated row is a **verbatim copy of a row observed in the real export**
  (same columns, same values, same nulls), so no new event, host, account, value
  or incident type is invented. The incidents documented in FSD §8 simply recur.
* Each repetition of the 715-row block lands **one day later**, jittered by less
  than an hour by the seed. The cadence inside a block (19 s spray, 16 s reads,
  22 POSTs) is preserved, so the detectors behave exactly as they do on the real
  export, while blocks never overlap in time.
* `Log_ID` is renumbered sequentially (`EVT-00001` …) because evidence keys must
  stay unique. The prefix is kept: the report guard recognises `EVT-` ids.
* The output declares itself synthetic in the directory and file name, in the
  first sheet name, and in the workbook properties.

Output goes to `backend/out/synthetic/`, which is already covered by the
`backend/out/` line in `.gitignore`. The file is never read by the report.

Usage (from `backend/`, so the project's virtualenv provides pandas/openpyxl):

    uv run python ../scripts/make_synthetic_export.py
    uv run python ../scripts/make_synthetic_export.py --rows 50000 --seed 7
"""

from __future__ import annotations

import argparse
import random
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import Workbook

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_EXPORT = REPO_ROOT / "SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx"
OUTPUT_DIRECTORY = REPO_ROOT / "backend" / "out" / "synthetic"

# The 12 columns of the real export, in their real order (FSD §3).
COLUMNS: tuple[str, ...] = (
    "Log_ID",
    "Timestamp",
    "Hostname",
    "Event_ID",
    "User",
    "Source_IP",
    "Destination",
    "Log_Source",
    "Event_Description",
    "Process_CommandLine",
    "Result",
    "Severity",
)

DEFAULT_ROWS = 50_050  # 70 complete repetitions of the 715-row export
DEFAULT_SEED = 20261023

SYNTHETIC_TAG = "SYNTHETIC"
DATA_SHEET = "SYNTHETIC SIEM Export"
NOTICE_SHEET = "SYNTHETIC notice"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

# Fixed document metadata: a generator that stamped the wall clock would produce
# different bytes on every run (the repo's other outputs are reproducible too).
DOCUMENT_TIMESTAMP = datetime(2026, 10, 23, 13, 44, 6)

# One repeated block per day; the jitter stays far below the 17-hour gap between
# blocks, so rows keep ascending time order and blocks never interleave.
MAX_BLOCK_JITTER_SECONDS = 3600

NOTICE_LINES: tuple[str, ...] = (
    f"{SYNTHETIC_TAG} FIXTURE, NOT THE CLIENT EXPORT",
    "",
    "Rows are verbatim copies of rows observed in",
    f"{REAL_EXPORT.name}",
    "repeated one day apart, with Log_ID renumbered to keep evidence keys unique.",
    "",
    "No new event, host, account, value or incident type was invented.",
    "This file exists only to measure the performance claim of FSD §7.",
    "It is never used by the deliverable report.",
)


def default_output_path(rows: int = DEFAULT_ROWS) -> Path:
    """Where the fixture is written: a synthetic-named file under `backend/out/`."""
    return OUTPUT_DIRECTORY / f"SOC_L2_Logs_{SYNTHETIC_TAG}_{rows}.xlsx"


def _cell(value: Any) -> Any:
    """A cell value the workbook can store, with nulls kept as nulls (FSD §3)."""
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "item"):  # numpy scalar -> plain Python value
        return value.item()
    return value


def _real_rows() -> tuple[pd.DataFrame, list[datetime]]:
    """The real export's 12 columns plus its parsed timestamps (read-only)."""
    frame = pd.read_excel(REAL_EXPORT, sheet_name=0)
    missing = [column for column in COLUMNS if column not in frame.columns]
    if missing:
        raise SystemExit(
            f"{REAL_EXPORT.name} does not have the documented schema; missing: "
            + ", ".join(missing)
        )
    frame = frame[list(COLUMNS)]
    timestamps = [pd.Timestamp(value).to_pydatetime() for value in frame["Timestamp"]]
    return frame, timestamps


def build_rows(rows: int, seed: int) -> Iterator[list[Any]]:
    """Yield `rows` copies of the real rows, renumbered and shifted in time."""
    if rows <= 0:
        raise ValueError("rows must be a positive integer")

    frame, timestamps = _real_rows()
    block = len(frame)
    rng = random.Random(seed)

    cycle = -1
    shift = timedelta(0)
    for index in range(rows):
        position = index % block
        if position == 0:
            cycle += 1
            shift = timedelta(
                days=cycle, seconds=rng.randrange(MAX_BLOCK_JITTER_SECONDS)
            )
        source = frame.iloc[position]
        values = [_cell(source[column]) for column in COLUMNS]
        values[0] = f"EVT-{index + 1:05d}"
        values[1] = (timestamps[position] + shift).strftime(TIMESTAMP_FORMAT)
        yield values


def build_synthetic_export(
    output: str | Path,
    rows: int = DEFAULT_ROWS,
    seed: int = DEFAULT_SEED,
) -> Path:
    """Write the synthetic export and return its path (deterministic per seed)."""
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)

    book = Workbook(write_only=True)
    data = book.create_sheet(title=DATA_SHEET)
    data.append(list(COLUMNS))
    for values in build_rows(rows, seed):
        data.append(values)

    notice = book.create_sheet(title=NOTICE_SHEET)
    for line in NOTICE_LINES:
        notice.append([line])
    notice.append([f"rows: {rows}"])
    notice.append([f"seed: {seed}"])

    book.properties.title = f"{SYNTHETIC_TAG} SIEM export fixture ({rows} rows)"
    book.properties.description = (
        f"{SYNTHETIC_TAG} fixture derived from {REAL_EXPORT.name}. "
        "Never used by the deliverable report."
    )
    book.properties.creator = "scripts/make_synthetic_export.py"
    book.properties.created = DOCUMENT_TIMESTAMP
    book.properties.modified = DOCUMENT_TIMESTAMP

    book.save(destination)
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--rows", type=int, default=DEFAULT_ROWS, help="rows to generate (>= 50000 for FSD §7)"
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="seed of the timeline")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="output path (default: backend/out/synthetic/SOC_L2_Logs_SYNTHETIC_<rows>.xlsx)",
    )
    arguments = parser.parse_args(argv)

    destination = arguments.output or default_output_path(arguments.rows)
    written = build_synthetic_export(destination, rows=arguments.rows, seed=arguments.seed)
    print(f"{written} ({arguments.rows} rows, seed {arguments.seed})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
