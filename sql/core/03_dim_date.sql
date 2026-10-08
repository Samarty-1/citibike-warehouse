-- dim_date: calendar with the day's weather as attributes. Weather is a
-- property of the date (one station network, one city), so it lives here
-- rather than in its own dimension.
create or replace table dim_date as
select
    d::date                                         as date_key,
    year(d)                                         as year,
    month(d)                                        as month,
    isodow(d)                                       as iso_dow,
    isodow(d) >= 6                                  as is_weekend,
    w.temp_max_c,
    w.temp_min_c,
    w.precip_mm,
    w.snowfall_cm,
    w.wind_max_kmh,
    case
        when w.precip_mm >= 5 then 'wet'
        when w.precip_mm < 0.5 then 'dry'
        else 'drizzle'
    end                                             as precip_class
from range(date '2019-01-01', date '2025-01-01', interval 1 day) t(d)
left join stg_weather w on w.weather_date = d::date;
