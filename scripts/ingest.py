"""Land Citi Bike Jersey City trip files and daily weather.

    python scripts/ingest.py                 # 2019-2024
    python scripts/ingest.py 2023 2024       # chosen years

Trips: the public bucket's file names are inconsistent (a "citbike" typo in
2022-07, ".zip" vs ".csv.zip"), so files are found from the bucket listing,
never by constructing a name. Each file is routed by its *header*, not its
date: the legacy schema (tripduration, starttime, ... usertype, birth year,
gender) goes to data/raw/trips/legacy/, the 2021+ schema (ride_id,
rideable_type, ... member_casual) to data/raw/trips/current/.

Weather: daily observations for Jersey City from the Open-Meteo archive API
(ERA5 reanalysis; no key needed), written to data/raw/weather.csv.
"""
from __future__ import annotations

import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

BUCKET = "https://s3.amazonaws.com/tripdata"
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
WEATHER_URL = (
    "https://archive-api.open-meteo.com/v1/archive?latitude=40.7178&longitude=-74.0431"
    "&start_date={start}&end_date={end}&timezone=America%2FNew_York"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,snowfall_sum,wind_speed_10m_max"
)


def list_trip_files(years: list[str]) -> list[str]:
    listing = urllib.request.urlopen(f"{BUCKET}?list-type=2&prefix=JC-").read().decode()
    keys = re.findall(r"<Key>([^<]+)</Key>", listing)
    return sorted(k for k in keys if k[3:7] in years and k.endswith(".zip"))


def schema_of(header: bytes) -> str:
    cols = header.decode().strip().replace('"', "").split(",")
    if "tripduration" in cols:
        return "legacy"
    if "ride_id" in cols:
        return "current"
    raise ValueError(f"unknown schema: {cols}")


def land_trips(years: list[str]) -> None:
    trips = RAW / "trips"
    for key in list_trip_files(years):
        month = key[3:9]
        if list(trips.glob(f"*/JC-{month}.csv")):
            continue
        payload = urllib.request.urlopen(f"{BUCKET}/{urllib.request.quote(key)}").read()
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            csvs = [n for n in zf.namelist() if n.endswith(".csv") and not n.startswith("__MACOSX")]
            assert len(csvs) == 1, (key, csvs)
            data = zf.read(csvs[0])
        dest = trips / schema_of(data.splitlines()[0]) / f"JC-{month}.csv"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        print(f"{key} -> {dest.parent.name}/{dest.name}")


def land_weather(years: list[str]) -> None:
    url = WEATHER_URL.format(start=f"{min(years)}-01-01", end=f"{max(years)}-12-31")
    daily = json.load(urllib.request.urlopen(url))["daily"]
    cols = list(daily)
    lines = [",".join(cols)] + [
        ",".join("" if daily[c][i] is None else str(daily[c][i]) for c in cols)
        for i in range(len(daily["time"]))
    ]
    (RAW / "weather.csv").write_text("\n".join(lines) + "\n")
    print(f"weather: {len(lines) - 1} days")


if __name__ == "__main__":
    years = sys.argv[1:] or [str(y) for y in range(2019, 2025)]
    land_trips(years)
    land_weather(years)
