# Handover: Kaafu Connect datasets

Context for a Claude session picking up data work for this team. Paths are relative to the repo root (`maldives-datathon-2026-datasets/`). Written 23 Oct 2026; updated the evening of 23 Oct when the data pack was finished.

## Project

**Kaafu Connect** (Maldives Datathon 2026, event 24 Oct 2026). Door-to-door travel time from each inhabited Kaafu island, plus 14 inbound islands in AA/ADh/V, to a hospital in Greater Malé: wait + ferry + transfer + bus or car + walk. Output is a dashboard map, the share of population within 30/60/90/120 min, a comparison with the HDX car-only estimate, and what-if sliders.

**Build plan: [`BUILD_PLAN.md`](BUILD_PLAN.md)** (in this folder). It turns the team lead's prep guide into workstreams, file contracts and checks for the 24th; follow it.

**Scope:** destinations are hospitals only. Out of scope: schools, flights and other air travel, privately chartered speedboats, ambulance boats.

**Rules:** all project code is written on the day (24th). Prep is data only. Anything AI-assisted must be listed in the README. Don't commit IMEIs or raw restricted data.

## Provided datasets

| Path | What | Key facts and caveats |
|---|---|---|
| `FollowMe/FollowMe_august_2025/1.csv`…`31.csv` | Boat GPS pings, Aug 2025, one file per day, 1.8 GB total | ~440k rows/day, ~1,430 devices nationwide. Columns: `poll_id, imei, timestamp, device_date, latitude, longitude, speed, heading, network (1=Dhiraagu, 2=Ooredoo), cellid, gsm_level`. **`device_date` is UTC** (add 5 h). **`speed` is in knots.** Some lat/lon are 0. Pings are not passengers. Don't load these on the day: use the subset in `data_pack/raw/` (below). |
| `Avas_Ride/avas_rides_aug_sep_2026.csv` | 371,788 taxi requests, Greater Malé, Aug–Sep 2026 | `date_started, pickup/dropoff lat/lng, distance_km, time_sec, status`. ~7% `ride_expired` (unserved), 15–17% at 07–08 and 17–18. Pickups near the airport: 25% expire overall, 64% at 23:00. |
| `Avas_Ride/car_fare_matrix.csv` | Zone-to-zone taxi fares (MVR) | 6 zones: Malé, Hulhumalé Ph1/Ph2, airport, seaplane, domestic terminal |
| `MACL/MACL/Airport traffic_Dataset_27092026.csv` (+ `Metadata.csv`) | 169k flights at Velana, 2012–2026 | Passenger counts by arrival/departure/transit; carriers and routes anonymised. **Not used:** flights are out of scope. |
| `MTCC/MTCC.xlsx` | Bus and ferry passengers 2023–2025 | **Passenger numbers are randomly generated** (says so in its README sheet). Use for demo only, never for findings. |

## Team Kandu shared files (`team-shared-datasets/Team_Kandu/`)

- `observations.csv`: Statistical Yearbook tables in long format. Census 2022 population per island (`metric=census_population`, `date=2022`; total includes foreigners), domestic airport movements and passengers, vehicles.
- `odi_connections.csv`: 58 island pairs (Kaafu, AA, ADh, V to Malé or the airport). **Coordinates are island centres, not harbours** (checked against OSM). No times.
- `rtl_routes/trips/stops/connections.csv`: RTL ferries for Zones 1, 2, 4, 5 and 6. **No Zone 3 (Kaafu)**.
- `rtl_bus_routes/stops/departures.csv`: Greater Malé buses. Departures only cover 19:54–23:59 (fetched at 19:53); estimate the wait from `trips_per_day`.
- Also: `mma_series.csv` (economic series, e.g. fuel imports), `qa_flags.csv` (Yearbook inconsistencies), `maldivian_destinations.csv` (airport codes).

## Sheets we built (`data_pack/sheets/`)

Each CSV has a `.txt` beside it with full column docs. They are UTF-8 with a BOM. All pass the BUILD_PLAN section 9 data checks (names resolve, stops exist, population totals, departure before arrival, no leg over 80 km/h).

- **`islands.csv`** (27 rows): 23 origin islands, 3 Greater Malé destinations, Hulhulé as a transfer point. Harbour point, Census 2022 population, health facility IDs. Origin population: Kaafu 17,749 + inbound 13,665 = 31,414.
- **`facilities.csv`** (29 rows): 9 hospitals and 20 health centres, from OSM (Overpass, 23 Oct). Access point is the nearest RTL bus stop in Greater Malé or the island harbour elsewhere. `walk_minutes` = straight-line metres / 80.
- **`island_names.csv`** (172 rows): spelling variant → `island_key`. Use it to normalise any new file before joining.
- **`ferry_timetable.csv`** (794 rows): one row per boat leg, with a shared `trip_id` per boat run. CFN Zone 3 routes 301–309 (MTCC/RTL "CFN All ferry schedule", effective 1 Aug 2026) and the Malé–Villimalé ferry (frequency bands from its 2026 V1 schedule, 8-minute crossing, `estimated = yes`). Names are already `island_key`s; Greater Malé stops carry a `terminal_id`. Notes: `ferry_timetable.txt`.
- **`bus_service_hours.csv`** (45 rows) and **`bus_headways.csv`** (117 rows): first/last bus and frequency bands for all 15 Greater Malé routes × Sun–Thu, Sat, Fri, from the MTCC/RTL route timetable PDFs. Notes: `bus_service_hours.txt`.
- **`hdx_benchmark.csv`** (16 rows): HDX car-only share within 30/60/90/120 min of a hospital: Maldives 45.9% and Kaafu 77.4% at 2 h, plus Malé and Alif Alif.

## Raw extracts (`data_pack/raw/`, never committed)

- **`followme_kaafu_aug2025.parquet`**: FollowMe pings inside lat 3.40–5.05, lon 72.70–73.80 (Kaafu, AA, ADh, V), 0,0 dropped. 9.8 million pings, 1,372 devices. Columns `device_id` (md5 of IMEI), `ts` (UTC), `lat, lon, speed, heading, day`.
- **`followme_check.txt`**: member 2's findings. Speed is in knots; 1,026 devices are boats; ~114 island-to-Greater-Malé trips a day (77–148); timestamps are UTC.
- Queries that made them: `data_pack/prep/followme_queries.sql` (DuckDB CLI).

## Things that will bite you

- **Always join on `island_key`** (`K.Maafushi`, `ADh.Dhangethi`, `V.Thinadhoo`), never on the plain name. Thinadhoo, Guraidhoo and Omadhoo each exist in two atolls; GDh Thinadhoo has 6,217 people vs Vaavu's 258.
- The Census spells two islands differently: `Dhagethi` (Dhangethi) and `Hangnameedhoo` (Hangnaameedhoo).
- Malé population = four wards (137,238). The Census row `Maale` (211,908) is the whole city.
- In `islands.csv`, `harbour_quality=island_point` means an island centre, which is 100–300 m from the harbour. Only 5 points are real harbours or terminals. The `K.Malé` point is not a ferry terminal: the arrival terminal must come from the ferry timetable.
- `facilities.csv` has 8 rows with `location_quality=estimated` (placed at island centre, or at the bus stop for Villimalé Hospital). Confirmed by the team on 23 Oct:
  - IGMH and Dharumavantha Hospital are one destination (H01, renamed "IGMH (Dharumavantha Hospital)").
  - Senahiya (H03) takes public emergencies 24/7 and is covered by Aasandha, so it's a destination.
  - Rasdhoo (H07) and Mahibadhoo (H08) are the atoll hospitals, in the mapped places.
  - Still unconfirmed, low impact: Gulhi's "Island Clinic" (C07) as the government health centre.
- **Ferries run on different days.** Routes 303, 305, 306 and 307 run only on some days, and nothing on CFN Zone 3 runs on Friday. The build uses **Wednesday**; filter `ferry_timetable.csv` on `days`, and add Thursday's rows (not Wednesday's) at +1440. On Wednesday Alif Dhaalu has no Malé-bound boat.
- **The Malé jetty is assumed.** The CFN schedule only says "Male'"; every Malé stop uses `T_MALE_NORTH` (Jetty NO5), flagged `terminal_assumed = yes`.
- **FollowMe times are UTC**: add 5 hours. **FollowMe speed is in knots.**
- **Bus routes R3–R6** only had Ramadan 2024 timetables; their times are adjusted to RTL live data and marked `estimated = yes`. R10–R12 and R14 had no Saturday table (Sun–Thu assumed).
- **HDX** uses its own modelled population, not the Census: compare percentages only. It has no Alif Dhaalu or Vaavu rows and nothing past 120 min.
- Thulusdhoo has a new hospital under construction, a ready-made what-if scenario.

## Prep status (23 Oct, late evening)

- **Done:** every sheet and raw extract above, in `data_pack/`, with checks run. `ferry_links_filled` (the earlier ferry sheet) is superseded by `ferry_timetable.csv`; don't use it.
- **Decided:** service day Wednesday; Malé jetty = Jetty NO5; Senahiya included; Villimalé crossing 8 min; route 307's 11:40 stop is Hulhumalé.
- **Before H0:** install Python on every laptop. At H0, copy `data_pack/sheets/` to `data/sheets/` and `data_pack/raw/` to `data/raw/` in the project repo.
- **Dropped:** `flight_times` (no air travel in scope).

## Environment notes (this machine)

- **No Python installed. Node.js v24, Git Bash and the DuckDB CLI (`duckdb.exe`) are available.** The build scripts for the sheets were throwaway Node scripts outside the repo; only the CSVs matter.
- **Overpass API:** send a `User-Agent` header or it returns 406. Large or case-insensitive regex queries time out (502), so use small `around:` queries.
- Data credits needed on the slides:
  - © OpenStreetMap contributors (ODbL)
  - MBS Statistical Yearbook 2026, table 3.3, via Team Kandu
  - Team Kandu shared datasets
  - MTCC/RTL ferry and bus timetables
  - HDX Maldives accessibility indicators
