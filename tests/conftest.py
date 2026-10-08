import sys
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import run  # noqa: E402

LEGACY_HEADER = ('"tripduration","starttime","stoptime","start station id","start station name",'
                 '"start station latitude","start station longitude","end station id",'
                 '"end station name","end station latitude","end station longitude","bikeid",'
                 '"usertype","birth year","gender"')
CURRENT_HEADER = ("ride_id,rideable_type,started_at,ended_at,start_station_name,start_station_id,"
                  "end_station_name,end_station_id,start_lat,start_lng,end_lat,end_lng,member_casual")

# Four physical places in Jersey City.
#   A  "Alpha"   legacy 1001 -> renumbered JC001 in 2021 -> moved 30 m as JC101 in 2022
#   B  "Bravo"   legacy 1002, closed 2019-03; an unrelated "Bravo" (JC002) opens 900 m
#                away in 2021: same name, different station, must NOT be linked
#   C  "Charlie" JC003, always there; used as the far end of trips
A = (40.7200, -74.0430)
A_MOVED = (40.72027, -74.0430)          # ~30 m north
B = (40.7300, -74.0500)
B_NEW = (40.7381, -74.0500)             # ~900 m north
C = (40.7150, -74.0600)


def legacy_trip(start, start_id, start_name, end, end_id, end_name, when, user="Subscriber"):
    return (f'300,"{when}","{when}",{start_id},"{start_name}",{start[0]},{start[1]},'
            f'{end_id},"{end_name}",{end[0]},{end[1]},1,"{user}",1990,1')


def current_trip(ride, start, start_id, start_name, end, end_id, end_name, when, bike="classic_bike"):
    end_time = when[:-2] + "59"
    return (f"{ride},{bike},{when},{end_time},{start_name},{start_id},{end_name},{end_id},"
            f"{start[0]},{start[1]},{end[0]},{end[1]},member")


def write_fixture(raw: Path) -> None:
    legacy, current = [], []
    # 12 trips a month in each direction keeps every station above the
    # 10-sighting floor for placement
    for day in range(1, 13):
        legacy.append(legacy_trip(A, 1001, "Alpha", C, 1003, "Charlie Old", f"2019-01-{day:02d} 08:00:00"))
        legacy.append(legacy_trip(B, 1002, "Bravo", C, 1003, "Charlie Old", f"2019-02-{day:02d} 08:00:00"))
        legacy.append(legacy_trip(C, 1003, "Charlie Old", A, 1001, "Alpha", f"2021-01-{day:02d} 08:00:00"))
        current.append(current_trip(f"a{day}", A, "JC001", "Alpha", C, "JC003", "Charlie",
                                    f"2021-02-{day:02d} 08:00:00"))
        current.append(current_trip(f"b{day}", B_NEW, "JC002", "Bravo", C, "JC003", "Charlie",
                                    f"2021-03-{day:02d} 08:00:00"))
        current.append(current_trip(f"m{day}", A_MOVED, "JC101", "Alpha", C, "JC003", "Charlie",
                                    f"2022-03-{day:02d} 08:00:00"))
    # a month-end ride published again in the next month's file
    current.append(current_trip("dup", A, "JC001", "Alpha", C, "JC003", "Charlie", "2021-02-12 23:59:00"))
    # an e-bike trip with GPS drift and a dockless finish
    current.append("e1,electric_bike,2022-03-20 09:00:00,2022-03-20 09:20:00,Alpha,JC101,,,"
                   f"{A_MOVED[0] + 0.001},{A_MOVED[1]},40.7,-74.05,casual")
    # JC001's last day is 2021-02-12; JC101 first appears 2022-03-01 (> 60 days).
    # Bridge them with a late JC001 sighting so the gap is 45 days.
    current.append(current_trip("a99", A, "JC001", "Alpha", C, "JC003", "Charlie", "2022-01-15 08:00:00"))

    # ... and its second copy in the next month's file, with millisecond timestamps
    next_month = ["dup,classic_bike,2021-02-12 23:59:00.123,2021-02-12 23:59:59.456,Alpha,JC001,"
                  f"Charlie,JC003,{A[0]},{A[1]},{C[0]},{C[1]},member"]

    for sub, header, rows, name in [("legacy", LEGACY_HEADER, legacy, "JC-201901.csv"),
                                    ("current", CURRENT_HEADER, current, "JC-202102.csv"),
                                    ("current", CURRENT_HEADER, next_month, "JC-202103.csv")]:
        (raw / "trips" / sub).mkdir(parents=True, exist_ok=True)
        (raw / "trips" / sub / name).write_text(header + "\n" + "\n".join(rows) + "\n")
    days = [f"2019-01-{d:02d}" for d in range(1, 32)]
    (raw / "weather.csv").write_text(
        "time,temperature_2m_max,temperature_2m_min,precipitation_sum,snowfall_sum,wind_speed_10m_max\n"
        + "\n".join(f"{d},5.0,0.0,{'10.0' if i % 7 == 0 else '0.0'},0.0,10.0" for i, d in enumerate(days)) + "\n")


@pytest.fixture(scope="session")
def fx(tmp_path_factory):
    raw = tmp_path_factory.mktemp("raw")
    write_fixture(raw)
    con = duckdb.connect()
    con.execute("set enable_progress_bar = false")
    run.build(con, raw)
    yield con
    con.close()


@pytest.fixture(scope="session")
def full():
    if not (run.RAW / "trips" / "current").exists():
        pytest.skip("full dataset not landed; run scripts/ingest.py")
    con = duckdb.connect()
    con.execute("set enable_progress_bar = false")
    run.build(con)
    yield con
    con.close()
