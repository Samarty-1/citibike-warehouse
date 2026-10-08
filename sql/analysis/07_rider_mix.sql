-- Who rides, on what, and for how long, by year. Pre-2021 every bike was
-- a classic; e-bikes arrive with the system migration.
--
-- Do not read a trend into pct_electric across 2023 -> 2024. The monthly
-- share slides from 22% to 5% through 2023, then jumps to 61% on 1 January
-- 2024. A step that size, exactly at a year boundary, is a change in how the
-- feed labels bikes, not a fleet that tripled overnight.
select
    year(started_at)                                                    as year,
    count(*)                                                            as trips,
    round(100.0 * count(*) filter (where rider_type = 'casual') / count(*), 1)
                                                                        as pct_casual,
    round(100.0 * count(*) filter (where bike_type = 'electric') / count(*), 1)
                                                                        as pct_electric,
    round(median(duration_min) filter (where bike_type = 'classic'), 1) as median_min_classic,
    round(median(duration_min) filter (where bike_type = 'electric'), 1) as median_min_electric,
    round(median(dock_distance_km) filter (where bike_type = 'classic' and not is_round_trip), 2)
                                                                        as median_km_classic,
    round(median(dock_distance_km) filter (where bike_type = 'electric' and not is_round_trip), 2)
                                                                        as median_km_electric
from fct_trips
where not (is_dockless or is_unresolved_station or is_bad_duration)
group by year(started_at)
order by year;
