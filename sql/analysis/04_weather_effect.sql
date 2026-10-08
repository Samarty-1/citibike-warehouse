-- What does rain cost in rides? Wet days (>= 5 mm) against dry days
-- (< 0.5 mm) *within the same year, month and weekday/weekend class*, so
-- seasonality, network growth and the 2020 shock compare like with like.
-- Each cell gives one wet-vs-dry difference in log daily trips; cells are
-- averaged weighted by their smaller side. Temperature gets the same
-- treatment: dry days only, each day's trips relative to its cell's mean
-- (days below 0 C are pooled into one bin; there are only 42 of them).
with daily as (
    select
        d.date_key, d.year, d.month, d.is_weekend, d.precip_class, d.temp_max_c,
        count(f.trip_id)                    as trips
    from dim_date d
    left join fct_trips f
      on  f.date_key = d.date_key
      and not (f.is_dockless or f.is_unresolved_station or f.is_bad_duration)
    group by all
    having count(f.trip_id) > 0
),
cells as (
    select
        year, month, is_weekend,
        avg(ln(trips)) filter (where precip_class = 'wet')  as wet_log,
        avg(ln(trips)) filter (where precip_class = 'dry')  as dry_log,
        count(*) filter (where precip_class = 'wet')        as n_wet,
        count(*) filter (where precip_class = 'dry')        as n_dry
    from daily
    group by year, month, is_weekend
    having n_wet > 0 and n_dry > 0
),
rain as (
    select
        'wet day (>= 5 mm) vs dry day'                                  as comparison,
        sum(least(n_wet, n_dry) * (wet_log - dry_log)) / sum(least(n_wet, n_dry))
                                                                        as log_effect,
        count(*)                                                        as cells,
        sum(n_wet)                                                      as wet_days
    from cells
),
temp as (
    select
        d.temp_max_c,
        ln(d.trips) - avg(ln(d.trips)) over (partition by d.year, d.month, d.is_weekend)
                                                                        as rel_log
    from daily d
    where d.precip_class = 'dry'
)
select comparison, pct_change_in_trips, cells, days
from (
    select
        -100                                                    as sort_key,
        comparison,
        round(100 * (exp(log_effect) - 1), 1)                   as pct_change_in_trips,
        cells,
        wet_days                                                as days
    from rain
    union all
    select
        bin,
        'dry day, max temp '
            || case when bin < 0 then 'below 0' else bin::int || ' to ' || (bin + 5)::int end
            || ' C, vs its month',
        round(100 * (exp(avg(rel_log)) - 1), 1),
        null,
        count(*)
    from (select greatest(floor(temp_max_c / 5) * 5, -5) as bin, rel_log from temp)
    group by bin
)
order by sort_key;
