-- station_sources: one row per source-system station ID ever seen, as a trip
-- start or end, with when it was active and where its dock is.
create or replace table station_sources as
with endpoints as (
    select system, start_station_source_id as source_id, start_station_name as station_name,
           started_at as seen_at, start_lat as lat, start_lng as lng, coords_are_dock
    from stg_trips
    where start_station_source_id is not null
    union all
    select system, end_station_source_id, end_station_name,
           ended_at, end_lat, end_lng, coords_are_dock
    from stg_trips
    where end_station_source_id is not null
)
select
    *,
    case
        when source_id like 'HB%' then 'Hoboken'
        when source_id like 'JC%' then 'Jersey City'
        -- legacy IDs are plain integers on both sides of the river; the
        -- Hudson (about -74.025 here) decides
        when system = 'legacy' and lng < -74.025 then 'Jersey City'
        else 'New York'
    end                                                     as area,
    -- operations sites (the JCBS depot) appear as stations in the feed
    not regexp_matches(lower(station_name), 'depot|warehouse')  as is_public
from (
select
    source_id,
    any_value(system)                                       as system,
    -- the most recent name wins; renames within one ID are rare (2 cases,
    -- both whitespace / abbreviation variants of NYC stations)
    arg_max(station_name, seen_at)                          as station_name,
    min(seen_at)                                            as first_seen,
    max(seen_at)                                            as last_seen,
    count(*)                                                as endpoint_events,
    -- dock position: prefer coordinates that are the dock's own
    coalesce(median(lat) filter (where coords_are_dock), median(lat))  as lat,
    coalesce(median(lng) filter (where coords_are_dock), median(lng))  as lng
from endpoints
group by source_id
);
