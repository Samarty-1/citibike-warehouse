-- fct_trips: one row per trip, keyed to the station *version* live at the
-- moment of the trip (a point-in-time join on the SCD2 validity window).
create or replace table fct_trips as
select
    t.trip_id,
    t.system,
    t.started_at::date                              as date_key,
    t.started_at,
    t.ended_at,
    round(t.duration_min, 2)                        as duration_min,
    t.rider_type,
    t.bike_type,
    ss.station_sk                                   as start_station_sk,
    ss.station_key                                  as start_station_key,
    es.station_sk                                   as end_station_sk,
    es.station_key                                  as end_station_key,
    ss.area                                         as start_area,
    es.area                                         as end_area,
    ss.station_key = es.station_key                 as is_round_trip,
    -- straight-line distance between docks; a floor on distance ridden
    round(6371 * 2 * asin(sqrt(
        pow(sin(radians(es.lat - ss.lat) / 2), 2)
        + cos(radians(ss.lat)) * cos(radians(es.lat))
          * pow(sin(radians(es.lng - ss.lng) / 2), 2))), 3)
                                                    as dock_distance_km,
    -- data-quality flags
    t.start_station_source_id is null
        or t.end_station_source_id is null          as is_dockless,
    -- has a station ID, but one too rare to place (< 10 sightings)
    (t.start_station_source_id is not null and ss.station_sk is null)
        or (t.end_station_source_id is not null and es.station_sk is null)
                                                    as is_unresolved_station,
    t.duration_min < 1 or t.duration_min > 24 * 60  as is_bad_duration,
    t.started_at::date not between date '2019-01-01' and date '2024-12-31'
                                                    as is_out_of_window
from stg_trips t
left join dim_station ss
    on  ss.source_id = t.start_station_source_id
    and t.started_at >= ss.valid_from and t.started_at < ss.valid_to
left join dim_station es
    on  es.source_id = t.end_station_source_id
    and t.started_at >= es.valid_from and t.started_at < es.valid_to;
