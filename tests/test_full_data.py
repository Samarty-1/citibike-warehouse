"""Invariants on the real 2019-2024 data. Skipped unless scripts/ingest.py has run."""
from run import analysis


def one(con, sql):
    return con.sql(sql).fetchone()[0]


def test_every_staged_trip_lands_once(full):
    # 4,322,979 raw rows less 24 rides published in two monthly files
    assert one(full, "select count(*) from stg_trips") == 4_322_955
    assert one(full, "select count(*) from fct_trips") == 4_322_955
    assert one(full, "select count(*) - count(distinct trip_id) from fct_trips") == 0


def test_station_versions_never_overlap(full):
    assert one(full, """
        select count(*) from dim_station a join dim_station b
          on a.station_key = b.station_key and a.station_sk < b.station_sk
         and a.valid_from < b.valid_to and b.valid_from < a.valid_to""") == 0


def test_point_in_time_join_is_unambiguous(full):
    # each trip with a placeable start station gets exactly one version
    assert one(full, """select count(*) from fct_trips
                        where start_station_sk is null and not is_dockless
                          and not is_unresolved_station""") == 0


def test_known_station_histories(full):
    def chain(name):
        return [r[0] for r in full.sql(f"""
            select source_id from dim_station
            where station_key = (select station_key from dim_station
                                 where station_name = '{name}' and is_latest_version)
            order by version_no""").fetchall()]
    assert chain("Grove St PATH") == ["3186", "JC005", "JC115"]
    assert chain("JC Medical Center") == ["3205", "JC011", "JC110"]


def test_linked_legacy_stations_mostly_keep_their_name(full):
    # names are never used for linking, so agreement is an independent check
    linked, same_name = full.sql("""
        select count(*), count(*) filter (where p.station_name = s.station_name)
        from dim_station s
        join dim_station p on p.station_key = s.station_key and p.version_no = s.version_no - 1
        where p.system = 'legacy' and s.system = 'current'""").fetchone()
    assert linked >= 45 and same_name / linked >= 0.9


def test_like_for_like_growth_is_far_below_naive(full):
    last = analysis(full, "03_like_for_like_growth").fetchall()[-1]
    year, *_, all_idx, jc_idx, same_idx = last
    # growth since 2019: naive count vs the same stations
    assert year == 2024 and (all_idx - 100) > 3 * (same_idx - 100) and same_idx < jc_idx


def test_rain_costs_rides(full):
    effect = dict((c, p) for c, p, *_ in analysis(full, "04_weather_effect").fetchall())
    assert -45 < effect["wet day (>= 5 mm) vs dry day"] < -20
