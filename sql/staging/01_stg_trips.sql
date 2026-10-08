-- stg_trips: both source schemas unified into one shape. Nothing is dropped.
--
-- legacy  (2019-01 .. 2021-01): tripduration, starttime, ..., usertype, birth year, gender
-- current (2021-02 ..        ): ride_id, rideable_type, ..., member_casual
-- Everything is read as text and cast explicitly, so a type surprise in one
-- month fails loudly instead of silently changing a column's type.
--
-- A ride that crosses midnight at a month end can be published in *both*
-- monthly files (24 rides on 2024-05-31 appear in May and June, the June
-- copy with millisecond timestamps, so the rows are not byte-identical).
-- ride_id is the key: keep the copy from the month the ride started in.
create or replace table stg_trips as
with legacy as (
    select
        'L-' || regexp_extract(filename, 'JC-([0-9]{6})', 1) || '-'
            || lpad(row_number() over (
                    partition by filename
                    order by starttime, bikeid, "start station id")::varchar, 6, '0')
                                                        as trip_id,
        'legacy'                                        as system,
        starttime::timestamp                            as started_at,
        stoptime::timestamp                             as ended_at,
        nullif("start station id", '')                  as start_station_source_id,
        nullif("start station name", '')                as start_station_name,
        "start station latitude"::double                as start_lat,
        "start station longitude"::double               as start_lng,
        nullif("end station id", '')                    as end_station_source_id,
        nullif("end station name", '')                  as end_station_name,
        "end station latitude"::double                  as end_lat,
        "end station longitude"::double                 as end_lng,
        case usertype when 'Subscriber' then 'member' when 'Customer' then 'casual' end
                                                        as rider_type,
        'classic'                                       as bike_type,
        -- legacy coordinates are the dock's, not the rider's
        true                                            as coords_are_dock
    from read_csv('{raw}/trips/legacy/*.csv', header = true, all_varchar = true, filename = true)
),
current_ as (
    select
        ride_id                                         as trip_id,
        'current'                                       as system,
        started_at::timestamp                           as started_at,
        ended_at::timestamp                             as ended_at,
        nullif(start_station_id, '')                    as start_station_source_id,
        nullif(start_station_name, '')                  as start_station_name,
        start_lat::double                               as start_lat,
        start_lng::double                               as start_lng,
        nullif(end_station_id, '')                      as end_station_source_id,
        nullif(end_station_name, '')                    as end_station_name,
        end_lat::double                                 as end_lat,
        end_lng::double                                 as end_lng,
        member_casual                                   as rider_type,
        -- "docked_bike" was the 2021-22 label for what is now "classic_bike"
        case rideable_type when 'electric_bike' then 'electric' else 'classic' end
                                                        as bike_type,
        -- e-bikes report GPS position, which drifts from the dock
        rideable_type <> 'electric_bike'                as coords_are_dock
    from read_csv('{raw}/trips/current/*.csv', header = true, all_varchar = true,
                  union_by_name = true, filename = true)
    qualify row_number() over (
        partition by ride_id
        order by (regexp_extract(filename, 'JC-([0-9]{6})', 1)
                  = strftime(started_at::timestamp, '%Y%m')) desc, filename
    ) = 1
)
select
    *,
    date_diff('second', started_at, ended_at) / 60.0    as duration_min
from (
    select * from legacy
    union all by name
    select * from current_
);
