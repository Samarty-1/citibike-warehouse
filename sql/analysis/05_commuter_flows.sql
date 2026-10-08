-- The morning rebalancing problem. On weekday mornings (07:00-09:59, 2023-24)
-- which stations drain (more departures than arrivals) and which fill?
-- Net flow is per average weekday; a station draining 30 bikes every morning
-- needs a truck or it is empty by 9.
with am as (
    select date_key, start_station_key, end_station_key
    from fct_trips
    where not (is_dockless or is_unresolved_station or is_bad_duration)
      and year(started_at) in (2023, 2024)
      and isodow(started_at) <= 5
      and hour(started_at) between 7 and 9
),
days as (select count(distinct date_key) as n from am),
flows as (
    select station_key, sum(arrivals) as arrivals, sum(departures) as departures
    from (
        select start_station_key as station_key, 0 as arrivals, count(*) as departures
        from am group by 1
        union all
        select end_station_key, count(*), 0
        from am group by 1
    )
    group by station_key
),
named as (
    select station_key, station_name, area
    from dim_station
    where is_latest_version and is_public
)
select
    n.station_name,
    n.area,
    round(f.departures / d.n, 1)                        as departures_per_weekday,
    round(f.arrivals / d.n, 1)                          as arrivals_per_weekday,
    round((f.arrivals - f.departures) / d.n, 1)         as net_per_weekday,
    case when f.arrivals > f.departures then 'fills' else 'drains' end as morning_pattern
from flows f
cross join days d
join named n using (station_key)
where n.area in ('Jersey City', 'Hoboken')
qualify row_number() over (partition by morning_pattern order by abs(f.arrivals - f.departures) desc) <= 6
order by net_per_weekday;
