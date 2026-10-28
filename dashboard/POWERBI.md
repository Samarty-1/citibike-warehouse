# Building this dashboard in Power BI (or Tableau)

`dashboard/app.py` is the Streamlit version. This is the same dashboard as a Power BI
report, using the CSVs in `dashboard/data/`. Power BI Desktop and Tableau Public are both
free.

## 1. Load the data

Get Data > Text/CSV, one query per file:

| File | Grain | Use |
|---|---|---|
| `monthly_trips.csv` | one row per month | trend, weather colouring |
| `hourly_profile.csv` | year x weekday/weekend x hour | when people ride |
| `stations.csv` | one row per physical station | map |
| `03_like_for_like_growth.csv` | one row per year | the headline chart |
| `04_weather_effect.csv` | one row per comparison | weather bars |
| `05_commuter_flows.csv` | one row per station | drain/fill table |
| `07_rider_mix.csv` | one row per year | rider mix table |

In Power Query, set `month_start` to Date, `year` to Whole Number, and `lat`/`lng` to
Decimal Number. Then set `lat`/`lng` Data Category to Latitude/Longitude in the Column
tools tab.

`03_like_for_like_growth` and `monthly_trips` have no key in common, so keep them as
separate pages' data sources rather than forcing a relationship. Add a `Date` table
(`Date = CALENDAR(DATE(2019,1,1), DATE(2024,12,31))`) and relate `Date[Date]` to
`monthly_trips[month_start]` if you want a shared year slicer.

## 2. Measures (DAX)

```dax
Trips = SUM ( monthly_trips[jersey_city_trips] )

Naive Growth =
VAR latest = MAX ( '03_like_for_like_growth'[year] )
RETURN
    DIVIDE (
        CALCULATE ( MAX ( '03_like_for_like_growth'[all_trips_index] ), '03_like_for_like_growth'[year] = latest ),
        100
    )

Like For Like Growth =
VAR latest = MAX ( '03_like_for_like_growth'[year] )
RETURN
    DIVIDE (
        CALCULATE ( MAX ( '03_like_for_like_growth'[same_stations_index] ), '03_like_for_like_growth'[year] = latest ),
        100
    ) - 1
```

`Naive Growth` should show 2.6 and `Like For Like Growth` should show 31%. If they do not,
a filter is leaking into the measure; check the page and slicer interactions.

## 3. Page layout

1. **Cards (top row):** `Naive Growth`, `Like For Like Growth`, station count
   (`DISTINCTCOUNT ( stations[station_key] )`).
2. **Line chart:** `03_like_for_like_growth`, x = `year`, values = the three index columns.
   Title it "Naive growth is 2.6x; like-for-like is +31%". The gap between the lines is
   the point of the whole project.
3. **Column chart:** `monthly_trips`, x = `month_start`, y = `jersey_city_trips`, colour
   saturation = `avg_temp_max_c`.
4. **Bar chart:** `04_weather_effect`, `comparison` on the axis, `pct_change_in_trips`
   as values.
5. **Line chart:** `hourly_profile`, x = `hour`, y = `trips_per_day`, legend = `day_type`,
   slicer on `year`. Weekdays show a commuter double peak; weekends a single midday hump.
6. **Map:** `stations`, latitude/longitude, size = `trips_2024`, legend = `area`.
7. **Table:** `05_commuter_flows`, sorted by `net_per_weekday`.

## 4. Do not chart this

`07_rider_mix[pct_electric]` jumps from 13% to 59% between 2023 and 2024. That is the feed
changing how it labels bikes on 1 January 2024, not the fleet changing. Show the table, or
chart `pct_casual`, and put a text box on the page saying so.

## 5. Tableau Public equivalent

Connect to the same text files and build the same seven sheets. The like-for-like chart is
a dual-line sheet with the three index fields on Measure Values; the map uses `lat`/`lng`
as Latitude/Longitude with `trips_2024` on Size.

## 6. Publish

Power BI: File > Export > PDF for the repo (`dashboard/powerbi_report.pdf`), and
screenshot the main page as `dashboard/screenshot.png`. Tableau Public: Publish to Tableau
Public and link it in the README.
