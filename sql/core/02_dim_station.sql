-- dim_station: a Type 2 slowly changing dimension over physical stations.
--
--   station_key  durable key: one per physical station, stable across ID
--                changes, renames and small relocations
--   station_sk   surrogate key: one per *version* (one per source ID)
--   valid_from / valid_to   when that version was the live one
--
-- Source IDs are not stable. The 2021 system migration renumbered every
-- station (3186 -> JC005), and later relocations issued new IDs again
-- (Grove St PATH: JC005 -> JC115, moved ~20 m). Names don't help either: a
-- closed station can share a name with an unrelated later one.
--
-- So versions are linked by behaviour, never by name. B succeeds A when:
--   * B first appears after A was last seen, within 60 days
--   * their docks are within 150 m
--   * the match is one-to-one (each A's nearest qualifying B, and vice versa)
-- Chains of successions are then walked with a recursive CTE.
create or replace table dim_station as
with recursive src as (
    select * from station_sources
    -- a handful of NYC "stations" appear once via drifting e-bike GPS
    where endpoint_events >= 10 and lat is not null
),

candidates as (
    select
        a.source_id                                     as pred_id,
        b.source_id                                     as succ_id,
        6371000 * 2 * asin(sqrt(
            pow(sin(radians(b.lat - a.lat) / 2), 2)
            + cos(radians(a.lat)) * cos(radians(b.lat))
              * pow(sin(radians(b.lng - a.lng) / 2), 2)))
                                                        as distance_m,
        date_diff('day', a.last_seen, b.first_seen)     as gap_days
    from src a
    join src b
      on  b.first_seen > a.last_seen
      and b.first_seen <= a.last_seen + interval 60 day
      and abs(b.lat - a.lat) < 0.002        -- cheap prefilter (~220 m)
      and abs(b.lng - a.lng) < 0.003
),

links as (
    select pred_id, succ_id, distance_m, gap_days
    from candidates
    where distance_m <= 150
    -- one-to-one: keep a pair only if each side is the other's best match
    qualify row_number() over (partition by pred_id order by distance_m, gap_days) = 1
        and row_number() over (partition by succ_id order by distance_m, gap_days) = 1
),

chains as (
    -- roots: versions nobody succeeds
    select source_id as root_id, source_id, 1 as version_no
    from src
    where source_id not in (select succ_id from links)
    union all
    select c.root_id, l.succ_id, c.version_no + 1
    from chains c
    join links l on l.pred_id = c.source_id
),

versions as (
    select
        c.root_id,
        c.version_no,
        s.*,
        l.distance_m                                    as moved_m_from_previous
    from chains c
    join src s using (source_id)
    left join links l on l.succ_id = s.source_id
)

select
    row_number() over (order by root_id, version_no)        as station_sk,
    dense_rank() over (order by root_id)                    as station_key,
    version_no,
    source_id,
    system,
    station_name,
    area,
    is_public,
    round(lat, 6)                                           as lat,
    round(lng, 6)                                           as lng,
    round(moved_m_from_previous, 0)                         as moved_m_from_previous,
    first_seen,
    last_seen,
    endpoint_events,
    -- a version is live from its first sighting until the next version's
    case when version_no = 1 then timestamp '1900-01-01' else first_seen end
                                                            as valid_from,
    coalesce(lead(first_seen) over (partition by root_id order by version_no),
             timestamp '9999-12-31')                        as valid_to,
    lead(first_seen) over (partition by root_id order by version_no) is null
                                                            as is_latest_version
from versions;
