"""Build the Citi Bike warehouse and run every analysis.

    python scripts/ingest.py    # once: trips (2019-2024) + weather
    python run.py               # build data/citibike.duckdb, write results/*.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent
LAYERS = ["staging", "core", "marts"]
RAW = ROOT / "data" / "raw"


def build(con: duckdb.DuckDBPyConnection, raw: str | Path = RAW) -> None:
    """Run every model, layer by layer, against the raw files under `raw`."""
    for layer in LAYERS:
        for path in sorted((ROOT / "sql" / layer).glob("*.sql")):
            con.execute(path.read_text().replace("{raw}", Path(raw).as_posix()))


def analysis(con: duckdb.DuckDBPyConnection, name: str):
    return con.sql((ROOT / "sql" / "analysis" / f"{name}.sql").read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(ROOT / "data" / "citibike.duckdb"))
    args = parser.parse_args()
    # DuckDB draws tables with box characters a Windows console can't encode
    sys.stdout.reconfigure(encoding="utf-8")

    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    with duckdb.connect(args.db) as con:
        build(con)
        for path in sorted((ROOT / "sql" / "analysis").glob("*.sql")):
            rel = analysis(con, path.stem)
            rel.write_csv(str(out / f"{path.stem}.csv"))
            print(f"\n== {path.stem}")
            rel.limit(15).show(max_width=200)


if __name__ == "__main__":
    main()
