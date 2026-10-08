-- Ridership growth, three ways. From 2021 the files also carry Hoboken, a
-- separate city that joined the network, and Jersey City itself kept adding
-- stations. A naive year-on-year count compares different systems.
--   all trips              everything in the files
--   Jersey City            trips starting at a Jersey City station
--   same stations          trips starting at the 2019 Jersey City stations
--                          that were still running at the end of 2024: the
--                          bike-share version of like-for-like store sales,
--                          only possible because dim_station tracks a
--                          station through its ID changes
with valid as (
    select *
    from fct_trips
    where not (is_dockless or is_unresolved_station or is_bad_duration)
),
same_station_set as (
    select station_key
    from dim_station
    where area = 'Jersey City'
    group by station_key
    having min(first_seen) < date '2019-02-01' and max(last_seen) >= date '2024-12-01'
),
yearly as (
    select
        year(started_at)                                                    as year,
        count(*)                                                            as all_trips,
        count(*) filter (where start_area = 'Jersey City')                  as jersey_city,
        count(*) filter (where start_station_key in (select station_key from same_station_set))
                                                                            as same_stations
    from valid
    group by year(started_at)
)
select
    year,
    all_trips,
    jersey_city,
    same_stations,
    (select count(*) from same_station_set)                                 as n_same_stations,
    round(100.0 * all_trips / first(all_trips) over (order by year), 0)     as all_trips_index,
    round(100.0 * jersey_city / first(jersey_city) over (order by year), 0) as jersey_city_index,
    round(100.0 * same_stations / first(same_stations) over (order by year), 0)
                                                                            as same_stations_index
from yearly
order by year;
