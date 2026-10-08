# citibike-warehouse

A Kimball-style star schema over **4.3 million Citi Bike trips** in Jersey
City and Hoboken (2019–2024), joined to daily weather. It's built in plain
DuckDB SQL. The modelling problem it solves is **station identity**: the same
physical dock changes ID, name and position over six years, and the source
data never says so.

```
                          dim_date (+ weather)
                                 │
dim_station (SCD2) ──── fct_trips (4.32m rows) ──── dim_station (SCD2)
  start, as of trip time                              end, as of trip time
```

## The problem: station IDs aren't stable

In February 2021 the system migrated and **every station was renumbered**
(`3186` → `JC005`), with a new file schema arriving at the same time. Since
then, stations that moved a few metres were issued new IDs again, sometimes
under a new name. Names can't be used as keys either: a closed station can
share a name with an unrelated later one.

`dim_station` is a Type 2 slowly changing dimension:
- One **durable key** per physical station.
- One **version** per source ID, with `valid_from` and `valid_to`.

Versions are linked by behaviour, never by name. B succeeds A when it first
appears within 60 days of A's last sighting, within 150m, and the match is
one-to-one. A recursive CTE then walks the chains. Some of what comes out:

| Station | Versions |
|---|---|
| Grove St PATH | `3186` (to Jan 2021) → `JC005` → `JC115` (Dec 2022, moved 20m) |
| JC Medical Center | `3205` → `JC011` → `JC110` (Nov 2022, moved 128m) |
| Sip Ave | `3195` → `JC056` → `JC109` *Bergen Ave & Sip Ave* (moved 46m) |
| York St | `3481` → `JC096` (dark Apr 2021 – Sep 2022) → `JC097` *York St & Marin Blvd* (moved 116m) |
| Exchange Place | `3183` closed May 2019 → `3792` *Columbus Dr at Exchange Pl* opens 88m away 52 days later → `JC106` → `JC116` *Exchange Pl* (moved 141m) |

Name agreement is used as an **independent check**, not as the matching key:
at least 90% of linked legacy → current pairs keep their name (asserted in
the tests). `fct_trips` joins each trip to the version live *at the time of
the trip*, a point-in-time lookup on the validity window.

## Findings

**Real growth is about a fifth of what the raw counts suggest.** From 2021
the files include Hoboken, a separate city that joined the network, and
Jersey City kept adding stations. Tracking the 49 stations that ran from
January 2019 to December 2024 through all their ID changes:

| | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|---|---|
| All trips in the files | 100 | 83 | 155 | 216 | 238 | **257** |
| Jersey City stations | 100 | 83 | 100 | 123 | 129 | 137 |
| Same 49 stations | 100 | 80 | 96 | 117 | 123 | **131** |

A naive reading says ridership grew 2.6×. Like-for-like, it grew 31%. The
same-station series is only possible because the dimension carries a station
through its renumbering. Without it, every 2019 station "closes" in January
2021.

**Rain costs a third of the day's rides.** A wet day (5mm or more) has
**33.5% fewer trips** than a dry day in the same year, month and
weekday/weekend class. The comparison spans 130 matched cells and 443 wet
days. Temperature matters less than you'd expect once the month is held
fixed: from 5°C to 35°C, dry days sit within ±5% of their month. Below 0°C
costs 33%, and 0–5°C costs 8%.

**Every weekday morning, the PATH stations fill and the neighbourhoods
drain.** On weekday mornings (07:00–10:00, 2023–24), Grove St PATH gains
**59 bikes** net, and Hoboken Terminal gains 35. Hamilton Park, Liberty Light
Rail and Brunswick St each lose 8–12. That is the rebalancing truck route,
in one query.

**Who rides changed.** Casual riders were 11% of trips in 2019, 31% in 2020,
41% in 2021 and 24% by 2024.

## Data problems handled

| Problem | Handling |
|---|---|
| Two schemas: `tripduration, starttime, …, usertype, birth year, gender` until Jan 2021, then `ride_id, rideable_type, …, member_casual` | files routed by **header**, not date, at ingest; unified by name in `stg_trips` |
| Inconsistent file names in the bucket (`citbike` typo, `.zip` vs `.csv.zip`) | ingest reads the bucket listing, never builds a URL |
| **24 rides published twice**: May 31 rides ending on June 1 appear in both monthly files, the June copy with millisecond timestamps, so rows aren't byte-identical | de-duplicated on `ride_id`, keeping the copy from the start month; found by the uniqueness test |
| E-bike coordinates are rider GPS, not the dock | dock position uses classic-bike sightings only |
| An operations depot (`JCBS Depot`) appears as a station | `is_public` flag; excluded from station analyses |
| Dockless ends, sub-minute and over-24h trips | flagged on `fct_trips`, never silently dropped (`01_reconciliation`) |
| E-bike share falls smoothly to 5% through 2023, then jumps to 61% on 1 Jan 2024 | flagged as a labelling change in the feed, not interpreted as a trend |

## Run it

```bash
pip install -r requirements.txt
python scripts/ingest.py     # 72 monthly files (~140 MB zipped) + weather from Open-Meteo
python run.py                # build data/citibike.duckdb (~10 s), write results/*.csv
pytest                       # 16 tests
```

The tests come in two layers:
- `tests/test_models.py` builds the warehouse from a hand-written fixture
  covering a renumbering, a relocation, a same-name-different-station trap,
  a duplicate across files, e-bike GPS drift and a dockless trip. It checks
  that each is resolved correctly.
- `tests/test_full_data.py` asserts invariants on the real data: no
  overlapping versions, every trip lands exactly once, unambiguous
  point-in-time joins, and the known station histories above.

Data: [Citi Bike System Data](https://citibikenyc.com/system-data) (Lyft
Bikes and Scooters). Weather: [Open-Meteo](https://open-meteo.com/)
historical archive (ERA5).
