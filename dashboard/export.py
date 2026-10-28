"""Export small, dashboard-ready CSVs from the warehouse.

    python dashboard/export.py      # needs data/citibike.duckdb (python run.py)

The warehouse is 1.7 GB; these files are a few hundred KB, so the Streamlit app
and Power BI / Tableau can run without it. Same validity filter as the
analyses: dockless, unresolved-station and bad-duration trips are excluded.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "data"

VALID = "not (f.is_dockless or f.is_unresolved_station or f.is_bad_duration)"

QUERIES = {
    # one row per month: the growth story plus the weather that explains the dips
    "monthly_trips": f"""
        select
            date_trunc('month', f.started_at)::date                         as month_start,
            count(*)                                                        as all_trips,
            count(*) filter (where f.start_area = 'Jersey City')            as jersey_city_trips,
            round(100.0 * count(*) filter (where f.rider_type = 'casual') / count(*), 1)
                                                                            as pct_casual,
            round(avg(d.temp_max_c), 1)                                     as avg_temp_max_c,
            round(avg(d.precip_mm), 2)                                      as avg_precip_mm
        from fct_trips f
        join dim_date d on d.date_key = f.date_key
        where {VALID}
        group by 1
        order by 1
    """,
    # when people ride: the commuter double peak on weekdays, a single midday hump at weekends
    "hourly_profile": f"""
        select
            year(f.started_at)                                              as year,
            case when d.is_weekend then 'Weekend' else 'Weekday' end        as day_type,
            hour(f.started_at)                                              as hour,
            count(*)                                                        as trips,
            round(count(*) * 1.0 / count(distinct f.date_key), 1)           as trips_per_day
        from fct_trips f
        join dim_date d on d.date_key = f.date_key
        where {VALID}
        group by 1, 2, 3
        order by 1, 2, 3
    """,
    # one row per physical station (latest version); trips follow the station through ID changes
    "stations": f"""
        with trips as (
            select start_station_key as station_key,
                   count(*) as trips_all_years,
                   count(*) filter (where year(started_at) = 2024) as trips_2024
            from fct_trips f
            where {VALID}
            group by 1
        )
        select s.station_key, s.station_name, s.area, s.lat, s.lng,
               s.first_seen, s.last_seen,
               coalesce(t.trips_all_years, 0) as trips_all_years,
               coalesce(t.trips_2024, 0)      as trips_2024
        from dim_station s
        left join trips t using (station_key)
        where s.is_latest_version and s.lat is not null
        order by trips_all_years desc
    """,
}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    con = duckdb.connect(str(ROOT / "data" / "citibike.duckdb"), read_only=True)
    for name, sql in QUERIES.items():
        frame = con.execute(sql).df()
        frame.to_csv(OUT / f"{name}.csv", index=False)
        print(f"{name}.csv  {len(frame):,} rows")
    # the analysis outputs the dashboard also reads
    for name in ("03_like_for_like_growth", "04_weather_effect", "05_commuter_flows", "07_rider_mix"):
        (OUT / f"{name}.csv").write_bytes((ROOT / "results" / f"{name}.csv").read_bytes())
        print(f"{name}.csv  copied")


if __name__ == "__main__":
    main()
