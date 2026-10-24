# Member 1: GIS (places, last mile, map layers)

**Difficulty: 2 of 4.** Mostly distance tables and map layers, with one fiddly part (buses) and one part that depends on M2 (taxis). Nothing you do is on the H3 critical path except `terminals.csv`, which is 15 minutes of work and needed first.

You own `src/kaafu/geo.py` and `src/kaafu/lastmile.py`. Your outputs go to `data/processed/`.

Read first: `docs/CLAUDE_HANDOVER.md`, then `docs/BUILD_PLAN.md` sections 1, 4, 5, 6.3 and 7 (M1).

---

## What you deliver

| File | Due | Who waits | Columns (exact) |
|---|---|---|---|
| `terminals.csv` | **H0:45** | M3 (routing), M4 | `terminal_id, name, island_key, lat, lon, bus_stop_code, walk_to_stop_min` |
| `island_zones.geojson` | H1:45 | M2 (FollowMe stops) | `island_key` + polygon |
| `last_mile.csv` | H2:30 | M3 (routing) | `stop_id, facility_id, hour, mode, minutes, available, detail` |
| Map layer functions in `geo.py` | H5 | M4 (dashboard) | see Step 4 |
| Static maps (PNG) | H6:30 | slides 3–4, backup | |

---

## Timeline

| When | What |
|---|---|
| H0–0:30 | Kickoff, pull, start Claude. |
| 0:30–0:45 | **Step 1: `terminals.csv`.** Push, tell M3. |
| 0:45–1:45 | **Step 2: island zones.** Push, tell M2. |
| 1:45–3:00 | **Step 3: `last_mile.csv`** (walk + bus first, taxi when M2's Avas table lands). |
| 3:00–5:00 | **Step 4: map layers** for M4. |
| 5:00–6:30 | **Step 5: static maps.** |
| 6:30–8:00 | Slides 3–4 (data, method maps), rehearse. |

---

## Step 1: `terminals.csv` (15 min)

Coordinates are the RTL bus stops at each terminal (from `rtl_bus_stops.csv`). Use exactly these:

| terminal_id | name | island_key | lat | lon | bus_stop_code | walk_to_stop_min |
|---|---|---|---|---|---|---|
| T_MALE_NORTH | Jetty NO5 | K.Malé | 4.178784 | 73.513422 | 1008 | 0 |
| T_MALE_WEST | Maafannu Ferry Terminal | K.Malé | 4.172281 | 73.502060 | 1101 | 0 |
| T_HULHUMALE | Hulhumalé Ferry Terminal | K.Hulhumalé | 4.216739 | 73.537853 | 507 | 0 |
| T_VILLIMALE | Villimale Ferry Terminal | K.Villimalé | 4.175107 | 73.486942 | 1301 | 0 |

No `T_AIRPORT`: the ferry timetable never uses the airport. Write it with `encoding="utf-8"` so é survives.

---

## Step 2: `island_zones.geojson` (1 hour)

Purpose: M2 decides "this boat is at island X" by whether a ping falls inside X's zone. One polygon per row of `islands.csv` (27 rows).

1. **Ship the fallback first (10 min):** a circle around each `islands.csv` point, built in UTM 43N (`EPSG:32643`) and saved in `EPSG:4326`:
   - radius 600 m for ordinary islands;
   - radius 1,500 m for K.Malé, K.Hulhumalé and K.Hulhulé (they're 2–4 km long);
   - radius 1,500 m for ADh.Dhigurah (long island, its point is 1.4 km from OSM's).
   Push it immediately so M2 isn't blocked.
2. **Then upgrade to real outlines if time allows:** fetch island polygons from OpenStreetMap (Overpass; send a `User-Agent` header or it returns 406; use small `around:` queries, one per island):
   ```
   [out:json][timeout:25];
   (way["place"="island"](around:1500,LAT,LON);
    relation["place"="island"](around:1500,LAT,LON););
   out geom;
   ```
   Build the polygon with shapely, pick the one that contains the island point, buffer by `ZONE_BUFFER_M` (300 m) in EPSG:32643. Keep the circle for any island where this fails, and add a column `source` (`osm` or `circle`).
3. Check on a quick map that every zone covers its harbour and that Malé, Hulhulé and Hulhumalé zones don't swallow each other badly (some overlap at Hulhulé–Hulhumalé is fine; if a ping is in two zones, the nearest point wins).

---

## Step 3: `lastmile.py` → `last_mile.csv` (≈ 1.5 hours)

One row per **stop × hospital × hour (0–23) × mode**, where:
- stops = the 4 terminals (Greater Malé hospitals H01–H06), **plus** AA.Rasdhoo, ADh.Mahibadhoo and V.Felidhoo (their own atoll hospitals H07, H08, H09);
- modes = `walk`, `bus`, `taxi`;
- `minutes` = from stepping off the boat to the hospital door;
- `available` = yes/no; `detail` = a short text for the island panel ("walk 1.4 km", "R6 from stop X to Y, wait 8", "taxi, 3.1 km").

H03 Senahiya **is included** (`INCLUDE_SENAHIYA = True`, confirmed last night).

### Which links exist at all

- **Road-connected:** Malé, Hulhulé (airport) and Hulhumalé. Taxi and bus work between them.
- **Villimalé is separate.** From T_VILLIMALE only H06 (walk, or R13/R14 bus) is available. From the Malé or Hulhumalé terminals, H06 is **unavailable** by road; routing reaches it through the Villimalé ferry (M3 has it in the timetable: T_MALE_WEST → T_VILLIMALE, 8 min).
- **Walking only within the same island.** Mark walk unavailable when terminal and hospital are on different islands.

### Walk

`minutes = TERMINAL_EXIT_MIN (5) + straight-line metres / WALK_M_PER_MIN (80)`. Same for every hour. Here's what you should get (distance / minutes), so you can check your code:

| terminal | H01 IGMH | H02 ADK | H03 Senahiya | H04 Hulhumalé | H05 Tree Top | H06 Villimalé |
|---|---|---|---|---|---|---|
| T_MALE_NORTH | 1443 m / 23 | 475 m / 11 | 860 m / 16 | n/a | n/a | n/a |
| T_MALE_WEST | 129 m / 7 | 1496 m / 24 | 1604 m / 25 | n/a | n/a | n/a |
| T_HULHUMALE | n/a | n/a | n/a | 598 m / 12 | 495 m / 11 | n/a |
| T_VILLIMALE | n/a | n/a | n/a | n/a | n/a | 195 m / 7 |

(BUILD_PLAN's check "Jetty NO5 to IGMH about 20–25 minutes": 23. ✓)

Atoll hospital rows: `minutes = 5 + walk_minutes` from `facilities.csv` (Rasdhoo 2.0, Mahibadhoo 3.5, Felidhoo 2.0), every hour, mode walk.

### Bus

Inputs: `rtl_bus_stops.csv` (`route_number, order, stop, code, lat, lon`), `bus_service_hours.csv`, `bus_headways.csv`, `rtl_bus_departures.csv`.

**Important finding:** the 11 "timed" routes in BUILD_PLAN don't stop near Jetty NO5. Within 500 m of each terminal:
- T_MALE_NORTH: R10 (at the stop), R12 (54 m), R11 and R15 (447 m): **minibuses only**.
- T_MALE_WEST: R11 (at the stop), R10 and R15 (306 m), R1, R3, R7 (435 m).
- T_HULHUMALE: R5 (at the stop), R1, R2, R4, R6 (379 m).
- T_VILLIMALE: R13, R14 (at the stop).

So **use all 15 routes**, minibuses included; they now have times in `bus_service_hours.csv` (`in_build_plan = no (minibus)` only means they weren't in the original plan). Tell M4 so the config/README match.

For each terminal × hospital × hour:
1. Candidate routes: a stop within 400 m of the terminal (board) and a later stop (higher `order`) within 400 m of the hospital (alight).
2. **Available** only if the hour is inside `first_min`–`last_min` for that route (`day_type = weekday`; `last_min` can exceed 1440, e.g. 1470 = 00:30).
3. **Wait** = `wait_min` of the `bus_headways.csv` band containing that hour.
4. **Ride time:** for timed routes, the median difference between the two stops' times on the same `trip` in `rtl_bus_departures.csv`. Minibuses have no departures data: use distance along the stops in route order ÷ 12 km/h, and say "estimated" in `detail`.
5. `minutes = TERMINAL_EXIT_MIN + walk to boarding stop + wait + ride + walk from alighting stop`. Keep the best route per hour.

In practice walking wins inside Malé; the bus matters for Hulhumalé ↔ Malé (R1, R2, R4, R6, R7, R8 cross the bridge). Store `wait` in `detail` so M3's bus-frequency slider can rescale it.

### Taxi

Inputs: `avas_hourly.csv` (from M2, ~H1:30), the raw Avas file for point-to-point times.

`minutes = TERMINAL_EXIT_MIN + TAXI_BASE_WAIT_MIN (5) + expired_share(zone, hour) × TAXI_RETRY_MIN (10) + drive`.
- `zone` = the terminal's zone (male / hulhumale).
- **drive** = median Avas `time_sec` of completed rides that hour from within 400 m of the terminal to within 400 m of the hospital, if at least 10 rides; else straight-line km × `TAXI_DETOUR` (1.4) ÷ that hour's `median_speed_kmh`.
- **Avas only has rides ≥2 km**, so every Malé-terminal → Malé-hospital taxi uses the fallback. That's expected, not a bug.
- Until M2's file arrives, use a flagged placeholder of 20 km/h and `expired_share = 0.07`.

### Done when

- Every terminal × same-island hospital × hour has a walk row.
- Bus rows are available only inside service hours.
- Villimalé ↔ Malé hospitals by road: unavailable.
- Hulhumalé Ferry Terminal → Hulhumalé Hospital walk is under 15 min (12 ✓).

---

## Step 4: map layers in `geo.py` (H3–H5)

Agree the function names with M4 at H3. Suggested, each returning a DataFrame ready for pydeck:
- `islands_layer(access_results, dep_min, target)`: one row per origin, `lat, lon, population, total_min, colour` (≤60 green, ≤120 amber, >120 red, unreachable grey), radius ∝ √population.
- `boat_links_layer(connections)`: one row per island pair, `from_lat, from_lon, to_lat, to_lon, boats_per_day`.
- `hospitals_layer()`, `terminals_layer()`.
- Optional: `bus_routes_layer()` (paths from `rtl_bus_stops.csv` in `order`), `observed_trips_layer(observed_pairs)`.

## Step 5: static maps (H5–H6:30)

With geopandas + matplotlib, save PNGs to `docs/figures/`: (1) all 23 islands coloured by daytime median minutes; (2) Greater Malé inset with terminals, hospitals and walk lines. These go on slides 3–4 and are the backup if the live demo fails.

## Pitfalls

- é in names: always read/write UTF-8 (the sheets have a BOM; use `encoding="utf-8-sig"` to read).
- Distances: compute in metres with haversine or in EPSG:32643, never in raw degrees.
- Don't edit the sheets in `data/sheets/`; they're inputs.

## Start your Claude session with

> We're building Kaafu Connect today. I'm member 1, GIS. Read docs/CLAUDE_HANDOVER.md, docs/BUILD_PLAN.md (sections 1, 4, 5, 6.3, 7) and docs/members/M1_gis.md. Create or edit only src/kaafu/geo.py and src/kaafu/lastmile.py. Take every parameter from src/kaafu/config.py. Do Step 1 first, then the circle fallback of Step 2, and stop so I can push them. Keep a short list of what you wrote for the README's AI-assisted section.
