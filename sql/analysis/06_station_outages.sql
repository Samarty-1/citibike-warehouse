-- Gaps and islands: stretches of 14+ days in which a station that was in
-- service before and after recorded no departures at all. Measured on the
-- durable station_key, so a renumbering or relocation is not mistaken for an
-- outage. The network-wide quiet of 2020 shows up as a cluster.
with active_days as (
    select distinct start_station_key as station_key, date_key
    from fct_trips
    where not (is_dockless or is_unresolved_station or is_bad_duration)
      and start_area in ('Jersey City', 'Hoboken')
),
gaps as (
    select
        station_key,
        lag(date_key) over (partition by station_key order by date_key) as last_active,
        date_key                                                        as back_in_service
    from active_days
),
named as (
    select station_key, station_name from dim_station where is_latest_version and is_public
)
select
    n.station_name,
    g.last_active + 1                               as dark_from,
    g.back_in_service - 1                           as dark_to,
    date_diff('day', g.last_active, g.back_in_service) - 1 as days_dark
from gaps g
join named n using (station_key)
where date_diff('day', g.last_active, g.back_in_service) - 1 >= 14
order by days_dark desc;
