-- New Jersey stations whose identity changed: every version of each, in order.
-- One durable station_key spans the 2021 renumbering, relocations and renames.
select
    station_key,
    version_no,
    source_id,
    station_name,
    moved_m_from_previous,
    first_seen::date        as first_seen,
    last_seen::date         as last_seen,
    endpoint_events
from dim_station
where area in ('Jersey City', 'Hoboken')
  and station_key in (
      select station_key from dim_station
      group by station_key
      having count(*) > 2 or count(distinct station_name) > 1
  )
order by station_key, version_no;
