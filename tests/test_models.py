"""Model tests on a hand-built fixture with known station histories."""
from datetime import datetime


def rows(con, sql):
    return con.sql(sql).fetchall()


def chain(con, source_id):
    """Every source ID sharing a durable key with `source_id`, in version order."""
    return [r[0] for r in rows(con, f"""
        select source_id from dim_station
        where station_key = (select station_key from dim_station where source_id = '{source_id}')
        order by version_no""")]


def test_both_schemas_unify_and_dedupe_on_ride_id(fx):
    got = dict(rows(fx, "select system, count(*) from stg_trips group by 1"))
    assert got == {"legacy": 36, "current": 39}     # 40 raw rows, "dup" counted once
    assert rows(fx, "select count(*) from stg_trips where trip_id = 'dup'") == [(1,)]


def test_renumbering_and_relocation_form_one_station(fx):
    # legacy 1001 -> JC001 (same dock, new ID) -> JC101 (moved ~30 m)
    assert chain(fx, "1001") == ["1001", "JC001", "JC101"]


def test_same_name_far_away_is_a_different_station(fx):
    # legacy "Bravo" closed in 2019; the 2021 "Bravo" is 900 m away, 2 years later
    assert chain(fx, "1002") == ["1002"]
    assert chain(fx, "JC002") == ["JC002"]


def test_versions_never_overlap(fx):
    bad = rows(fx, """
        select a.source_id, b.source_id
        from dim_station a join dim_station b
          on a.station_key = b.station_key and a.station_sk < b.station_sk
         and a.valid_from < b.valid_to and b.valid_from < a.valid_to""")
    assert bad == []


def test_relocation_distance_recorded(fx):
    moved = rows(fx, "select moved_m_from_previous from dim_station where source_id = 'JC101'")[0][0]
    assert 25 <= moved <= 35


def test_point_in_time_join_picks_live_version(fx):
    # a trip from Alpha in 2021 resolves to JC001's version, one in 2022-03 to JC101's
    got = dict(rows(fx, """
        select f.started_at, s.source_id
        from fct_trips f join dim_station s on s.station_sk = f.start_station_sk
        where f.trip_id in ('a1', 'm1')"""))
    assert got == {datetime(2021, 2, 1, 8): "JC001", datetime(2022, 3, 1, 8): "JC101"}


def test_ebike_gps_does_not_move_the_dock(fx):
    lat = rows(fx, "select lat from dim_station where source_id = 'JC101'")[0][0]
    assert abs(lat - 40.72027) < 1e-6


def test_dockless_trip_flagged(fx):
    assert rows(fx, "select is_dockless from fct_trips where trip_id = 'e1'") == [(True,)]


def test_weather_on_dim_date(fx):
    got = dict(rows(fx, """select precip_class, count(*) from dim_date
                           where date_key between '2019-01-01' and '2019-01-31' group by 1"""))
    assert got == {"wet": 5, "dry": 26}
