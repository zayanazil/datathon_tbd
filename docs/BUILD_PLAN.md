# Kaafu Connect: build plan

How the team builds Kaafu Connect on 24 Oct 2026, in an 8-hour build: one workstream per member, each with its own Claude Code session. It follows the team lead's prep guide ("Kaafu Connect: Island Access Map prep guide", 21 Oct), updated with the decisions made since. Written 23 Oct 2026; updated the evening of 23 Oct once the data pack was finished.

**Read [`CLAUDE_HANDOVER.md`](CLAUDE_HANDOVER.md) first.** It describes every dataset, the sheets in `data_pack/sheets/` and the data traps: join keys, "harbour" points that are really island centres, and estimated locations. This plan doesn't repeat that material.

At H0, member 4 copies this file, the handover and the sheet notes (`*.txt`) into the project repo's `docs/` folder. They also add a one-line `CLAUDE.md` at the repo root saying "Read docs/CLAUDE_HANDOVER.md, then docs/BUILD_PLAN.md", so every member's Claude session loads both automatically.

## 1. What we're building

**Question:** how long does it take someone on each of 23 islands to reach a hospital in Greater Malé, by scheduled boat and then walking, bus or taxi, at any time of day? Which islands are worst served, and which ferry change would help the most people?

The 23 islands are the 9 inhabited Kaafu islands (17,749 people) and 14 islands in Alif Alif, Alif Dhaalu and Vaavu that have direct boats to Malé (13,665 people). That's 31,414 people in total (Census 2022).

**Users:**
- **MTCC and the Ministry of Transport:** where to add or retime ferry runs.
- **Maldives Bureau of Statistics (MBS):** a repeatable method for two indicators in the National Strategy for the Development of Statistics (NSDS) that have no base year: population with scheduled ferry services, and population within a set time of health facilities.

**Decisions already made (don't reopen them on the day):**

| Topic | Decision |
|---|---|
| Islands | The 23 above. Covering all 20 atolls goes on the roadmap slide. |
| Destinations | Hospitals only. **Main measure:** the nearest Greater Malé hospital (H01–H06 in `facilities.csv`). **Second measure, for comparison with HDX:** the nearest hospital of any level, which adds the atoll hospitals at Rasdhoo, Mahibadhoo and Felidhoo (H07–H09). |
| Travel modes | Scheduled boats (public ferries and scheduled speedboats), then walking, bus or taxi in Greater Malé. |
| Out of scope | Flights and all other air travel; privately chartered speedboats; ambulance boats. Say so on the limits slide. |
| Waiting for boats | Use real departure times. Someone leaving at 14:00 waits for the next actual boat, which may be the next morning. "Half the gap between departures" is used only for frequent city buses. |
| Tools | Python 3.11+, pandas, geopandas, DuckDB, Streamlit with pydeck, pytest. NetworkX and MovingPandas aren't needed. |
| Time | 8-hour build. A timetable-only demo must run by H3; features freeze at H6. |
| Service day | **Wednesday** (`DAY = "Wed"`). Several CFN routes run only on some days, and no single day has a Malé-bound boat from every atoll. On Wednesday only Alif Dhaalu has none; say so on the limits slide. No CFN Zone 3 service runs on Fridays. |
| Malé ferry jetty | The CFN schedule doesn't name the Malé jetty. All Malé stops use `T_MALE_NORTH` (Jetty NO5), flagged `terminal_assumed = yes`. Accepted; limits slide. |
| Senahiya | Confirmed 23 Oct: public emergency department 24/7, covered by Aasandha. It's a destination (`INCLUDE_SENAHIYA = True`). |
| FollowMe clock | `device_date` is UTC. Add 5 hours before any time-of-day work. |

## 2. Before H0 (tonight)

**The data pack is finished** (23 Oct, evening). Every sheet below is in `data_pack/sheets/` with a `.txt` note beside it, and passes the data checks in section 9.

| Sheet | Rows | What it is |
|---|---|---|
| `islands.csv`, `island_names.csv` | 27, 172 | Islands, populations, harbour points; spelling → `island_key`. |
| `facilities.csv` | 29 | Hospitals and health centres. All four open questions resolved (H01 renamed "IGMH (Dharumavantha Hospital)", H03 Senahiya, H07, H08). |
| `ferry_timetable.csv` | 794 | One row per boat leg: CFN Zone 3 routes 301–309 (68 legs) and the Malé–Villimalé ferry (726 legs, generated from frequency bands). Already in `island_key`s, with terminals. |
| `bus_service_hours.csv` | 45 | First and last bus for all 15 Greater Malé routes × Sun–Thu, Sat, Fri. |
| `bus_headways.csv` | 117 | The published frequency bands behind those times (e.g. R1 every 15 min at 07:00, every 30 at 23:00). |
| `hdx_benchmark.csv` | 16 | HDX car-only shares within 30–120 min for the Maldives, Kaafu, Malé and Alif Alif. |

In `data_pack/raw/` (never committed): `followme_kaafu_aug2025.parquet` and `followme_check.txt`. The DuckDB queries that made them are in `data_pack/prep/followme_queries.sql`; list them in the README's AI-assisted section. Flight times are dropped.

Still to do tonight:
- [ ] **Every laptop:**
  - Install Python 3.11+, Git and Claude Code.
  - Run `pip install pandas geopandas duckdb streamlit pydeck pytest openpyxl pyarrow`.
  - Test that `import geopandas` works.
  - The laptop that built the data pack has no Python yet.

## 3. Repository layout (member 4 creates it at H0)

```
kaafu-connect/
├── CLAUDE.md                one line: read docs/CLAUDE_HANDOVER.md, then docs/BUILD_PLAN.md
├── README.md                problem, setup, data sources, AI-assisted parts
├── requirements.txt
├── .gitignore               data/raw/
├── docs/                    CLAUDE_HANDOVER.md, BUILD_PLAN.md, sheet notes (*.txt)
├── data/
│   ├── sheets/              copied from data_pack/sheets (committed)
│   ├── raw/                 FollowMe, Avas and Team Kandu files (never committed)
│   └── processed/           the outputs in section 4 (committed; no IMEIs)
├── src/kaafu/
│   ├── config.py            paths and parameters (section 5)          M4
│   ├── load.py              load and check every sheet                M4
│   ├── geo.py               terminals, island zones, map layers       M1
│   ├── lastmile.py          terminal to hospital: walk, bus, taxi     M1
│   ├── avas.py              taxi speed and unserved share by hour     M2
│   ├── followme.py          GPS pings to stops to trips               M2
│   ├── timetable.py         ferry sheet to boat connections           M3
│   ├── routing.py           earliest arrival, door-to-door times      M3
│   ├── indicators.py        population within X, last trip, HDX       M3
│   └── scenarios.py         what-if changes behind the sliders        M3
├── app/streamlit_app.py     the dashboard                             M4
└── tests/                   test_data.py (M4), test_routing.py (M3)
```

The member roles follow the guide: M1 is GIS, M2 movement data, M3 network and indicators, and M4 lead and dashboard (Zayan).

**Rules:**
- **One owner per file.** Others read its outputs and never edit it; ask the owner instead.
- **One branch per member:** `m1-gis`, `m2-movement`, `m3-network`, `m4-dashboard`. Member 4 merges into `main` at H3 and H5, and everyone pulls `main` right after.
- **Processed outputs are committed,** so the app runs from a fresh clone without the raw data.

## 4. File contracts

These schemas are the hand-offs between workstreams. Keep the column names exactly as written. Until a file arrives, its consumer works from a small placeholder with the same columns.

**Conventions:**
- Files are UTF-8 CSV.
- Times are whole minutes from 00:00 of the service day; values above 1440 fall on the next day.
- Islands are identified by `island_key` from `islands.csv`, and Greater Malé arrival points by `terminal_id`. `stop_id` means either.

**Input sheets** (already made; read-only on the day):

| Sheet | Columns |
|---|---|
| `ferry_timetable.csv` | `trip_id, route_id, route_name, days, day_type, from, to, depart, arrive, dep_min, arr_min, departure_terminal, arrival_terminal, operator, mode, estimated, terminal_assumed, source, notes`. `from`/`to` are `island_key`s; `days` is e.g. `Sat Sun Mon Tue Wed Thu` or `Sun Wed`. Greater Malé stops carry a `terminal_id` in `departure_terminal`/`arrival_terminal`. |
| `bus_service_hours.csv` | `route_number, route_name, first_stop, days, day_type, first_departure, last_departure, first_min, last_min, trips_per_day, trips_per_day_rtl, breaks, in_build_plan, estimated, source, checked_on, notes`. `day_type`: weekday (Sun–Thu), saturday, friday. |
| `bus_headways.csv` | `route_number, days, day_type, band_start, band_end, start_min, end_min, every_min, wait_min, estimated, source, notes`. Band end is inclusive. |
| `hdx_benchmark.csv` | `area, admin_level, threshold_min, population_within, share_pct, source, notes`. |

| File (owner, due) | Columns | Notes |
|---|---|---|
| `terminals.csv` (M1, H0:45) | `terminal_id, name, island_key, lat, lon, bus_stop_code, walk_to_stop_min` | Start set, with coordinates from `rtl_bus_stops.csv`: `T_MALE_NORTH` (Jetty NO5 stop, code 1008), `T_MALE_WEST` (Maafannu Ferry Terminal, 1101), `T_HULHUMALE` (Hulhumalé Ferry Terminal, 507), `T_VILLIMALE` (Villimale Ferry Terminal, 1301). Add `T_AIRPORT` only if the timetable uses it. |
| `connections.csv` (M3, H1:30) | `conn_id, trip_id, route_id, from_stop, to_stop, dep_min, arr_min, mode, operator, day_type, estimated, source` | One row per boat leg between consecutive stops of one trip. All rows are repeated at +1440 for the next day. |
| `avas_hourly.csv` (M2, H1:30) | `zone, hour, completed, expired, expired_share, median_speed_kmh` | `zone`: male, hulhumale, airport, all. Speed comes from completed rides only. |
| `island_zones.geojson` (M1, H1:45) | `island_key` plus a polygon | Island outline buffered by 300 m. |
| `last_mile.csv` (M1, H2:30) | `stop_id, facility_id, hour, mode, minutes, available, detail` | `mode`: walk, bus, taxi. One row per Greater Malé terminal × Greater Malé hospital × hour, plus rows for each island with an atoll hospital. `minutes` runs from stepping off the boat to reaching the hospital door. |
| `observed_trips.csv` (M2, H4:30) | `device, from_key, to_key, depart, arrive, duration_min, mean_speed_kmh, speed_class` | `device` is a short hash of the IMEI, never the IMEI itself. |
| `observed_pairs.csv` (M2, H4:30) | `from_key, to_key, speed_class, n_trips, n_devices, median_min, p90_min, trips_per_day, first_hour, last_hour` | `p90_min` is the 90th percentile. |
| `access_results.csv` (M3, H3) | `scenario, day_type, origin_key, dep_min, target, facility_id, total_min, wait_min, boat_min, transfer_min, lastmile_mode, lastmile_min, n_boats, path` | `target`: `gm_hospital` or `any_hospital`. One row per island × 15-minute departure × target. Blank `total_min` means unreachable. |
| `island_summary.csv` (M3, H3) | `origin_key, population, day_median_min, best_min, worst_day_min, last_practical_departure, boats_per_day, observed_gap_min` | "Day" means departures from 06:00 to 18:00. |

## 5. Parameters (`config.py`)

Every assumption lives here, never hard-coded, and every one goes on the limits slide.

| Name | Default | Reason |
|---|---|---|
| `WALK_M_PER_MIN` | 80 | Prep guide. Applied to straight-line distances. |
| `ACCESS_MIN` | 5 | Home to harbour on the origin island; these islands are under about 1 km across. |
| `BOAT_TRANSFER_MIN` | 10 | Least time needed to change boats. |
| `TERMINAL_EXIT_MIN` | 5 | Getting off the boat and reaching the street. |
| `TAXI_BASE_WAIT_MIN` | 5 | Assumption: Avas has no pickup-wait field. |
| `TAXI_RETRY_MIN` | 10 | Added in proportion to the Avas unserved share for that hour. |
| `TAXI_DETOUR` | 1.4 | Road distance ÷ straight-line distance; used only in the taxi fallback. |
| `STOP_SPEED_KMH`, `STOP_MIN`, `ZONE_BUFFER_M` | 2, 10, 300 | The guide's stop rule for FollowMe. |
| `OBSERVED_MIN_TRIPS` | 5 | An observed time is used only with at least 5 trips behind it. |
| `STEP_MIN` | 15 | Departure-time resolution. |
| `THRESHOLDS_MIN` | 30, 60, 90, 120, 240 | HDX's format plus the guide's 4-hour band. |
| `INCLUDE_SENAHIYA` | True | Confirmed 23 Oct: public 24/7 emergency department, covered by Aasandha. |
| `DAY` | "Wed" | The service day. Keep ferry rows whose `days` contains it, and bus rows with `day_type = weekday`. |
| `NEXT_DAY` | "Thu" | The day whose rows are added at +1440. |
| `FOLLOWME_UTC_OFFSET_H` | 5 | FollowMe timestamps are UTC; Malé is UTC+5. |
| `VILLIMALE_FERRY_MIN` | 8 | Team figure; already applied in `ferry_timetable.csv`. |

## 6. Method

### 6.1 Ferry timetable to connections (M3, `timetable.py`)

1. **Load and check names.** Load `ferry_timetable.csv`. `from` and `to` are already `island_key`s; still check each against `island_names.csv` and stop with a clear error if any is unknown.
2. **Layout:** one row per boat leg (from, to, depart, arrive, days), so each row becomes one connection. `dep_min`/`arr_min` are already given. (The old `rtl_connections` layout is no longer used; `ferry_links_filled` is superseded.)
3. **Terminals.** Where `from` or `to` is in Greater Malé, use `departure_terminal`/`arrival_terminal` as the stop instead of the island key: `T_MALE_NORTH` for Malé on CFN routes (assumed, `terminal_assumed = yes`), `T_HULHUMALE`, and `T_MALE_WEST` ↔ `T_VILLIMALE` for the Villimalé ferry.
4. **Keep multi-stop trips together.** Legs of the same boat run share a `trip_id`, so staying on board costs no transfer time. Stops outside the project (Himandhoo, Maalhos, Feridhoo, Mandhoo, Kunburudhoo, Fenfushi, Maamigili, Dhidhdhoo, Rakeedhoo) were left out and the legs either side merged; route 310 touches only one project island and has no rows.
5. **Day.** Keep rows whose `days` contains `DAY` (default Wednesday). The sidebar's day choice changes `DAY`; Friday has only the Villimalé ferry.
6. **Add the next day.** Add the `NEXT_DAY` rows (Thursday for Wednesday) at +1440, so a late-evening start finds the next morning's boat. Don't copy the same day's rows: routes alternate by day.

### 6.2 Earliest arrival (M3, `routing.py`)

This is a "connection scan". Go through every boat departure in time order and keep the earliest time each island or terminal can be reached. For origin `o`, leaving home at time `t`:

```
reach[o] = t + ACCESS_MIN;  reach[every other stop] = never
for each connection c, in order of dep_min, starting from time t:
    staying_on = c.trip_id has already been boarded
    can_board  = reach[c.from_stop] + (0 if c.from_stop == o else BOAT_TRANSFER_MIN) <= c.dep_min
    if staying_on or can_board:
        mark c.trip_id as boarded
        if c.arr_min < reach[c.to_stop]: reach[c.to_stop] = c.arr_min; came_by[c.to_stop] = c
```

This sketch is for the design only; the code itself is written on the day.

**From the stop to the hospital:**
- For every reached `stop_id` that has rows in `last_mile.csv`, hospital arrival = `reach[stop]` + `last_mile(stop, hospital, hour of reach[stop])`, using the fastest mode available at that hour.
- The answer for a target is the earliest hospital arrival minus `t`.
- Following `came_by` back from the stop gives the trip breakdown: wait at the first harbour, time on boats, transfer waits, and the last mile.

For the any-hospital target, an island with its own atoll hospital scores `ACCESS_MIN`. Other islands can reach an atoll hospital by boat, through that island's rows in `last_mile.csv`.

### 6.3 Last mile in Greater Malé (M1, `lastmile.py`)

For every terminal, Greater Malé hospital and hour (0–23), compute three options. Mark an option unavailable where it can't run.

- **Walk:** `TERMINAL_EXIT_MIN` + straight-line distance ÷ `WALK_M_PER_MIN`.
- **Bus:** the 11 timed routes (R1–R9, R13, R14), marked `in_build_plan = yes`. The Malé minibuses (R10–R12, R15) now have times too and can be added if there's time.
  - Board at the route's stop nearest the terminal. Get off at the route's stop nearest the hospital, which must come later in the route's stop `order`.
  - Wait = `wait_min` (half the headway) from the `bus_headways.csv` band that contains the hour, for `day_type = weekday`. The bus is unavailable outside `first_min`–`last_min` in `bus_service_hours.csv` (`last_min` can be over 1440, e.g. 00:30 = 1470) and during Friday `breaks`.
  - R3–R6 times come from Ramadan 2024 timetables adjusted to RTL live data (`estimated = yes`); limits slide.
  - Ride time = the median gap between the two stops' times on the same trip in `rtl_bus_departures.csv`. Only evening trips exist there, so assume the same ride time all day.
  - Add the walks at both ends.
- **Taxi:** `TERMINAL_EXIT_MIN` + `TAXI_BASE_WAIT_MIN` + `expired_share` (zone, hour) × `TAXI_RETRY_MIN` + drive time.
  - Drive time = the median Avas `time_sec` of completed rides that hour from within 400 m of the terminal to within 400 m of the hospital, if there are at least 10.
  - Otherwise, use straight-line distance × `TAXI_DETOUR` ÷ that hour's `median_speed_kmh`.

**Road links:**
- Malé, Hulhulé (the airport) and Hulhumalé are connected by road; Villimalé is not.
- From the Villimalé terminal, only walking and the R13/R14 buses within Villimalé count.
- Getting from Villimalé to Malé needs a boat: the Villimalé ferry is in `ferry_timetable.csv` (route `VILI`, 8 minutes, T_MALE_WEST ↔ T_VILLIMALE).

Also write one walk row, for every hour, for each island with an atoll hospital: `TERMINAL_EXIT_MIN` + that hospital's `walk_minutes` from `facilities.csv`.

### 6.4 Observed boat times from FollowMe (M2, `followme.py`)

1. **Load.** Read `data/raw/followme_kaafu_aug2025.parquet` with DuckDB (made tonight; see `followme_check.txt`).
   - It already covers Kaafu and the inbound atolls: lat 3.40–5.05, lon 72.70–73.80, 0,0 pings dropped. 9.8 million pings, 1,372 devices, 1–31 Aug 2025.
   - Columns: `device_id` (md5 of the IMEI; no IMEI in the file), `ts` (from `device_date`), `lat`, `lon`, `speed`, `heading`, `day`.
2. **Clean.**
   - **`ts` is UTC.** Add `FOLLOWME_UTC_OFFSET_H` (5 h) before any time-of-day work. Trips from origin islands then peak at 07:00–08:00 local.
   - Drop duplicate (`device_id`, `ts`) rows.
3. **Speed.** Compute speed from consecutive positions (distance ÷ time gap). The `speed` column is in **knots** (median ratio 0.508 against derived km/h; knots give 0.54), so × 1.852 for km/h; use it only as a cross-check.
4. **Keep boats.** Keep devices whose moving pings are mostly on water, i.e. outside `island_zones.geojson`.
5. **Stops.** A stop is a run of pings inside an island zone, slower than `STOP_SPEED_KMH`, lasting at least `STOP_MIN`. A stop at an island outside the project, such as a resort, ends a trip without starting one that counts.
6. **Trips.**
   - A trip runs between consecutive stops at two different project islands.
   - Departure is the last ping of the first stop; arrival is the first ping of the next stop.
   - Drop trips that average over 80 km/h or last over 6 hours.
7. **Speed class.**
   - Split trips into `slow` (ferry-like) and `fast` (speedboat-like) at the dip in the histogram of trip speeds.
   - Compare scheduled ferries only with `slow` trips, and report `fast` trips as context.
8. **Aggregate.** Combine trips per island pair and class into `observed_pairs.csv`. In routing, the observed median replaces the scheduled duration only where `n_trips` ≥ `OBSERVED_MIN_TRIPS`.

Develop on one week, then run the full month. Trip counts are boat movements, not passengers.

**Prep results to beat or match** (`followme_check.txt`, simple 1.2 km island-point rule): 1,026 devices are boats; 3,594 island-to-Greater-Malé trips in August, 77–148 a day (median 114). Busiest: Huraa 24.5 a day (median 16 min), Thulusdhoo 19.5, Himmafushi 15.5, Maafushi 12.4 (29 min, against 100 by ferry: speedboats dominate near Malé). Felidhoo 316 min observed vs 325 by ferry, Mahibadhoo 233 vs 260.

### 6.5 Taxi table from Avas (M2, `avas.py`)

For each pickup zone and hour, give:
- completed and expired requests, and `expired_share`;
- the median speed of completed rides (`distance_km` ÷ `time_sec`).

Zones are assigned by pickup point: Malé, Hulhumalé, airport. Avas covers Aug–Sep 2026, while FollowMe is Aug 2025; put that on the limits slide.

### 6.6 Indicators (M3, `indicators.py`)

- **Every trip time:** door-to-door minutes for every island × 15-minute departure × target, written to `access_results.csv`.
- **Per island (`island_summary.csv`):** daytime median (departures 06:00–18:00), best, worst daytime, boats per day, and the **last practical departure**: the latest time someone can leave and still reach a Greater Malé hospital before midnight.
- **Population within a threshold:** the share within 30, 60, 90, 120 and 240 minutes, for Kaafu (17,749) and for all 23 islands (31,414). Give it at the chosen departure time and for the daytime median.
- **HDX comparison:** the same thresholds next to `hdx_benchmark.csv`. HDX's car-only figures: 77.4% of Kaafu within 2 hours of a hospital, and 45.9% of the Maldives. HDX stops at 120 min (no 240 value) and has no Alif Dhaalu or Vaavu rows. It uses its own modelled population (Kaafu ~7,770), so compare percentages, not head counts.
- **NSDS-style figures:**
  - The share of population on islands with at least one daily scheduled boat to Greater Malé.
  - The share within 30 minutes of any health facility (the on-island health centres) against the share within 2 hours of a hospital.
- **Best ferry change (stretch):** for each route, try adding one departure at 18:00, 20:00 or 22:00. Rank the changes by people newly within 2 hours, then by population-weighted minutes saved.

### 6.7 What-if sliders (M3 writes the functions in `scenarios.py`; M4 wires them up)

| Slider | What it changes |
|---|---|
| Ferry frequency per route, ×0.5 to ×3 | Re-spread that route's departures evenly between its first and last. |
| Add an evening run | One extra departure on a chosen route at a chosen time. |
| Bus frequency, ×0.5 to ×3 | Divide the headway on the routes that serve terminals. |
| Taxi availability | Multiply `expired_share` by (1 − slider value). |
| Thulusdhoo hospital opens | Add K.Thulusdhoo as an atoll-level hospital (affects the any-hospital target). |
| Boat times | Scheduled or observed. |
| Departure time, day | Choose the inputs. The day defaults to Wednesday. |

Recomputing all 23 islands for one departure time checks a few thousand connections, so it's instant. The all-day chart (23 islands × 96 departures) takes seconds, so cache it per scenario with `st.cache_data`.

### 6.8 Dashboard (M4, `app/streamlit_app.py`)

- **Sidebar:** departure time, target (Greater Malé hospital or any hospital), day type, scheduled or observed boat times, and the scenario sliders.
- **Headline:** "Global car-only estimate: 77.4% of Kaafu within 2 hours of a hospital. With real boats leaving at <time>: Y%." Below it, the 30/60/90/120-minute table next to HDX's figures.
- **Map:** pydeck with its default Carto basemap, which needs no Mapbox token.
  - Islands are circles sized by population and coloured by minutes: up to 60, up to 120, over 120, or unreachable today.
  - Boat links are lines, wider for more boats a day.
  - Hospitals and terminals are shown; bus routes and observed trip lines are optional layers.
- **Island panel:** the trip as a stacked bar (wait, boat, transfer, last mile), plus boats per day, population, last practical departure, and scheduled vs observed time.
- **Through the day:** the share of population within 2 hours by departure time, and the Avas unserved share by hour.
- **Best ferry change** table (stretch).

## 7. Workstreams

### M1: GIS (places, last mile, map layers)

Owns `geo.py` and `lastmile.py`. Produces `terminals.csv`, `island_zones.geojson`, `last_mile.csv`, the map layers and static maps. Method: section 6.3.

| When | Step |
|---|---|
| H0:30–0:45 | Make `terminals.csv` and send it to M3. |
| 0:45–1:45 | Make `island_zones.geojson` from the Geofabrik extract: island outlines buffered by 300 m in UTM 43N (EPSG:32643). Send it to M2. If an outline is missing, use a 600 m circle around that island's `islands.csv` point. |
| 1:45–3:00 | Make `last_mile.csv`: walk and bus first, then taxi as soon as `avas_hourly.csv` arrives. Until then, use a flagged 20 km/h placeholder for taxis. |
| 3:00–5:00 | Map layers for the dashboard: boat links from `connections.csv`, hospitals, terminals, observed trip lines. |
| 5:00–6:30 | Static maps for slides 3–4 and for the backup. |

**Done when:**
- Every terminal × Greater Malé hospital × hour has a walk row.
- Bus rows are available only inside service hours.
- Villimalé to the Malé hospitals by road is unavailable.
- Walking from Hulhumalé Ferry Terminal to Hulhumalé Hospital takes under 15 minutes.

### M2: Movement (FollowMe and Avas)

Owns `avas.py` and `followme.py`. Produces `avas_hourly.csv`, `observed_trips.csv`, `observed_pairs.csv` and the validation numbers. Method: sections 6.4 and 6.5.

| When | Step |
|---|---|
| H0:30–1:30 | Make `avas_hourly.csv`. It's quick, and M1 needs it. |
| 1:30–3:00 | FollowMe cleaning, boat filter and stop detection on one week. Use 600 m circles until M1's island zones arrive. |
| 3:00–4:30 | Run the full month; make `observed_trips.csv` and `observed_pairs.csv`. |
| 4:30–6:30 | Validation: for two island pairs the team knows, compare scheduled with observed times and give the number of trips. Write the limits: speed units, which boats carry trackers, 2025 vs 2026 data. |

**Done when:**
- No IMEI appears anywhere in the outputs.
- The number of island-to-Malé trips per day is reported. The guide's rule is at least 5 a day for observed times to go in the demo.
- No observed median is faster than 80 km/h in a straight line.

### M3: Network and indicators

Owns `timetable.py`, `routing.py`, `indicators.py`, `scenarios.py` and `tests/test_routing.py`. Produces `connections.csv`, `access_results.csv` and `island_summary.csv`. Method: sections 6.1, 6.2, 6.6 and 6.7.

| When | Step |
|---|---|
| H0:30–1:30 | Make `connections.csv` from the ferry timetable. |
| 1:30–2:30 | Write `routing.py` and the toy tests in section 9. |
| 2:30–3:00 | Timetable-only results, with a walk-only last mile until `last_mile.csv` arrives. |
| **H3** | `access_results.csv` and `island_summary.csv` for the base scenario. |
| 3:00–5:00 | The switch to observed times, the HDX table, the scenario functions, and the best ferry change. |
| 5:00–6:30 | Final figures for slides 5–6. |

**Done when:**
- The tests pass.
- Every island has a result for every departure step, or a stated reason it's unreachable.
- Every island has a last practical departure, or "none".

### M4: Lead and dashboard (Zayan)

Owns the repo, `config.py`, `load.py`, `tests/test_data.py`, `app/streamlit_app.py` and `README.md`. Method: sections 6.7, 6.8 and 9.

| When | Step |
|---|---|
| H0–0:30 | Set up the repo: branches, `requirements.txt`, `.gitignore`, `docs/` and `CLAUDE.md`, with the sheets in `data/sheets/`. Write `config.py` and `load.py` with the data checks. Everyone pulls. |
| 0:30–3:00 | Build the Streamlit shell on a placeholder `access_results.csv`: sidebar, headline, map. |
| **H3** | Swap in the real results; the minimum demo runs. |
| 3:00–5:00 | Island panel, sliders wired to `scenarios.py`, the through-the-day chart, and the README's setup and data sections. |
| 5:00–6:30 | Merge, test from a fresh clone, and record a 60-second backup video. Features freeze at H6. |
| 6:30–8:00 | Slides 1, 2, 7 and 8; export the PDF; submit the declaration; two rehearsals. |

## 8. Timeline at a glance

| Time | M1 GIS | M2 Movement | M3 Network | M4 Lead |
|---|---|---|---|---|
| H0–0:30 | Kickoff; start Claude with `CLAUDE.md` | same | same | Repo, sheets, `config.py`, `load.py` |
| 0:30–1:45 | Terminals, island zones | Avas hourly table | Connections | Dashboard shell |
| 1:45–3:00 | Last mile | FollowMe: one week | Routing, tests, first results | Map and headline |
| **H3** | | | Base results | **Minimum demo runs** |
| 3:00–5:00 | Map layers | FollowMe: full month | Observed times, HDX, scenarios | Panel, sliders, charts |
| **H5** | | | | Freeze at H6 |
| 5:00–6:30 | Static maps | Validation, limits | Final figures | Merge, fresh clone, video |
| 6:30–8:00 | Slides 3–4 | Slides 4–5 | Slides 5–6 | Slides 1, 2, 7, 8; rehearse |

## 9. Checks

**Data checks** (`tests/test_data.py`, also run by `load.py` at startup):
- Every name resolves to an `island_key`.
- Every stop in `facilities.csv` and `connections.csv` exists in `islands.csv` or `terminals.csv`.
- Population totals: Kaafu 17,749, inbound 13,665, all 31,414.
- Every connection has `dep_min` before `arr_min`, and no boat leg is faster than 80 km/h in a straight line.

**Routing tests** (`tests/test_routing.py`), on a three-island toy timetable:
- Leaving before a direct boat gives that boat's arrival time.
- Leaving after the last boat gives the next morning's boat.
- Changing boats needs `BOAT_TRANSFER_MIN`; staying on the same boat needs none.
- Leaving later never gets you there earlier.

**Plausibility** (M2 and M3, by H5):
- For two island pairs the team knows, scheduled and observed times agree roughly. (Prep check already passed: Felidhoo and Mahibadhoo to Malé, see section 6.4.)
- Walking from the Jetty NO5 terminal to IGMH takes about 20–25 minutes.
- Nothing is reachable before the first boat of the day.

**End to end** (M4, by H5:30):
1. Make a fresh clone and run `pip install -r requirements.txt`.
2. Run `pytest`, then `streamlit run app/streamlit_app.py`.
3. Check that the headline shows numbers.
4. Click the worst island.
5. Move the evening-run slider and watch the number change.

## 10. Slides and demo

Eight slides:
1. **Problem:** the global car-only estimate against island reality. HDX says 46% of Maldivians, and 77.4% of Kaafu, are within 2 hours of a hospital by road.
2. **Question and users:** 23 islands, hospitals, MTCC and MBS.
3. **Data and credits:** FollowMe, the ferry timetable, RTL buses (Team Kandu), Avas, Census 2022, OSM, HDX.
4. **Method:** timetable → earliest arrival → door-to-door time; pings → stops → trips.
5. **Findings:** worst-served islands, population within 1, 2 and 4 hours, how access changes through the day, last practical departures, scheduled vs observed.
6. **Policy:** the ferry change that helps the most people, and the indicators MBS can now report.
7. **Limits:**
   - The assumptions in section 5.
   - Boat data from 2025 against a 2026 timetable.
   - Which boats carry trackers.
   - Straight-line walks.
   - Wednesday timetable only; Alif Dhaalu has no Malé-bound boat that day. Malé jetty assumed to be Jetty NO5.
   - FollowMe clock is UTC (shifted +5 h); speed column in knots.
   - Bus routes R3–R6 from Ramadan 2024 timetables adjusted to RTL live data.
   - No charters, ambulance boats or air travel.
   - 23 islands only.
8. **Roadmap:** all 20 atolls, a GTFS feed for RTL, a live FollowMe feed, an ambulance-boat scenario.

**Demo script (3 minutes):**
1. The headline number.
2. The map.
3. Click the worst island and walk through its trip legs.
4. Scheduled vs observed time.
5. Add an evening ferry and watch the headline change.

**Credits needed on slide 3:**
- © OpenStreetMap contributors (ODbL).
- MBS Statistical Yearbook 2026, table 3.3, via Team Kandu.
- Team Kandu shared datasets.
- FollowMe and Avas data from the organisers.
- HDX.

## 11. Risks and fallbacks

| Risk | Fallback |
|---|---|
| Ferry rows lack an arrival terminal | Done tonight: every Greater Malé row has a terminal (Malé assumed `T_MALE_NORTH`). |
| Too few FollowMe trips, or processing too slow | Timetable-only demo. Use observed times only for pairs with at least 5 trips, and only one week of data. |
| Island outlines missing | 600 m circles around the `islands.csv` points. |
| Too few Avas rides between a terminal and a hospital | The city-wide speed for that hour. |
| Routing bug at H3 | Direct boats only (no transfers) with a walk-only last mile still produces the map. |
| No internet for the basemap | Static maps in the slides. |
| Dashboard breaks | The 60-second video plus static maps. |
| Python problems on a laptop | One working laptop runs the app; the others push code to their branches. |

## 12. Submission checklist

- [ ] The repo runs from a fresh clone, and the README covers the problem, setup, data sources and AI-assisted parts.
- [ ] `requirements.txt` is in place, and no IMEIs, keys or raw restricted data are committed.
- [ ] Every dataset is credited with its source and the date it was accessed.
- [ ] The 8-slide PDF is exported, and originals of any video are sent.
- [ ] The team lead has submitted the declaration.
- [ ] Rehearsed with all four members speaking.

## 13. Starting your Claude session

Each member starts their own Claude Code session in the repo, which loads `CLAUDE.md`, and pastes:

> We're building Kaafu Connect today. I'm member <1–4>, <role>. Read docs/CLAUDE_HANDOVER.md and docs/BUILD_PLAN.md: sections 1, 4 and 5, the method sections for my workstream, and my workstream in section 7. Create or edit only the files my workstream owns. Read other members' outputs from data/processed/ and match the schemas in section 4 exactly. Take every parameter from src/kaafu/config.py. Work through my steps in order, and run the "done when" checks before calling a step finished. Keep a short list of what you wrote for the README's AI-assisted section.

Which method sections each member needs: M1 6.3; M2 6.4 and 6.5; M3 6.1, 6.2, 6.6 and 6.7; M4 6.7, 6.8 and 9.
