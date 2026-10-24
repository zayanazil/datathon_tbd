# Handover: Kaafu Connect datasets

Context for a Claude session picking up data work for this team. Paths are relative to the repo root (`maldives-datathon-2026-datasets/`). Written 23 Oct 2026.

## Project

**Kaafu Connect** (Maldives Datathon 2026, event 24 Oct 2026). Door-to-door travel time from each inhabited Kaafu island, plus 14 inbound islands in AA/ADh/V, to a hospital in Greater Malé: wait + ferry + transfer + bus or car + walk. Output is a dashboard map, the share of population within 30/60/90/120 min, a comparison with the HDX car-only estimate, and what-if sliders.

**Build plan: [`BUILD_PLAN.md`](BUILD_PLAN.md)** (in this folder). It turns the team lead's prep guide into workstreams, file contracts and checks for the 24th; follow it.

**Scope:** destinations are hospitals only. Out of scope: schools, flights and other air travel, privately chartered speedboats, ambulance boats.

**Rules:** all project code is written on the day (24th). Prep is data only. Anything AI-assisted must be listed in the README. Don't commit IMEIs or raw restricted data.

## Provided datasets

| Path | What | Key facts and caveats |
|---|---|---|
| `FollowMe/FollowMe_august_2025/1.csv`…`31.csv` | Boat GPS pings, Aug 2025, one file per day, 1.8 GB total | ~440k rows/day, ~1,430 devices nationwide. Columns: `poll_id, imei, timestamp, device_date, latitude, longitude, speed, heading, network (1=Dhiraagu, 2=Ooredoo), cellid, gsm_level`. **Speed units unknown**: derive speed from positions. Some lat/lon are 0. Pings are not passengers. Too big for pandas in one go: use DuckDB or Polars, or filter per day. |
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

Each CSV has a `.txt` beside it with full column docs. They are UTF-8 with a BOM.

- **`islands.csv`** (27 rows): 23 origin islands, 3 Greater Malé destinations, Hulhulé as a transfer point. Harbour point, Census 2022 population, health facility IDs. Origin population: Kaafu 17,749 + inbound 13,665 = 31,414.
- **`facilities.csv`** (29 rows): 9 hospitals and 20 health centres, from OSM (Overpass, 23 Oct). Access point is the nearest RTL bus stop in Greater Malé or the island harbour elsewhere. `walk_minutes` = straight-line metres / 80.
- **`island_names.csv`** (172 rows): spelling variant → `island_key`. Use it to normalise any new file before joining.

## Things that will bite you

- **Always join on `island_key`** (`K.Maafushi`, `ADh.Dhangethi`, `V.Thinadhoo`), never on the plain name. Thinadhoo, Guraidhoo and Omadhoo each exist in two atolls; GDh Thinadhoo has 6,217 people vs Vaavu's 258.
- The Census spells two islands differently: `Dhagethi` (Dhangethi) and `Hangnameedhoo` (Hangnaameedhoo).
- Malé population = four wards (137,238). The Census row `Maale` (211,908) is the whole city.
- In `islands.csv`, `harbour_quality=island_point` means an island centre, which is 100–300 m from the harbour. Only 5 points are real harbours or terminals. The `K.Malé` point is not a ferry terminal: the arrival terminal must come from the ferry timetable.
- `facilities.csv` has 8 rows with `location_quality=estimated` (placed at island centre, or at the bus stop for Villimalé Hospital). Unconfirmed items:
  - IGMH and Dharumavantha Hospital are on the same site.
  - Senahiya (military) may not take public emergencies.
  - OSM may have mislabelled the atoll hospitals at Rasdhoo and Mahibadhoo.
- Thulusdhoo has a new hospital under construction, a ready-made what-if scenario.

## Prep status (23 Oct, evening)

- **Done by teammates (files not in this folder yet):**
  - The ferry timetable for Kaafu and the inbound islands.
  - `bus_service_hours`.
  - `hdx_benchmark`.
  - The FollowMe check (are pings boats, what are the speed units).
- **Before H0:** copy them into `data_pack/sheets/` (and the FollowMe subset into `data_pack/raw/`) under the names in BUILD_PLAN.md section 2. Check that ferry rows into Greater Malé name their arrival terminal.
- **Dropped:** `flight_times` (no air travel in scope).

## Environment notes (this machine)

- **No Python installed. Node.js v24 and Git Bash are available.** The build scripts for the sheets were throwaway Node scripts outside the repo; only the CSVs matter.
- **Overpass API:** send a `User-Agent` header or it returns 406. Large or case-insensitive regex queries time out (502), so use small `around:` queries.
- Data credits needed on the slides:
  - © OpenStreetMap contributors (ODbL)
  - MBS Statistical Yearbook 2026, table 3.3, via Team Kandu
  - Team Kandu shared datasets
