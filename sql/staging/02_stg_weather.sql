-- stg_weather: one row per day, Jersey City (Open-Meteo ERA5 archive).
create or replace table stg_weather as
select
    "time"::date                    as weather_date,
    temperature_2m_max::double      as temp_max_c,
    temperature_2m_min::double      as temp_min_c,
    precipitation_sum::double       as precip_mm,
    snowfall_sum::double            as snowfall_cm,
    wind_speed_10m_max::double      as wind_max_kmh
from read_csv('{raw}/weather.csv', header = true, all_varchar = true);
