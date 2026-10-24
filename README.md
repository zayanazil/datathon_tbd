# Kaafu Connect – Maldives Datathon 2026

**How long does it really take to reach a hospital from an island, by scheduled boat?**

Global accessibility estimates (HDX) assume you can drive: by that measure **77.4% of Kaafu** and 46% of Maldivians are within 2 hours of a hospital. Island people go by boat, on a timetable. Kaafu Connect estimates the real door-to-door time (wait for the boat, ferry, boat changes, then walk, bus or taxi to the hospital door) from **23 islands** to a hospital, at any time of day: the 9 inhabited Kaafu islands plus 14 islands in Alif Alif, Alif Dhaalu and Vaavu with direct boats to Malé. That's 31,414 people (Census 2022).

**Users:** MTCC and the Ministry of Transport (where to add or retime ferry runs) and the Maldives Bureau of Statistics (a repeatable method for two NSDS indicators with no base year: population with scheduled ferry services, and population within a set time of a hospital).

## Key findings

Wednesday timetable, scheduled public boats only:
- **Leaving home at 07:00, 30.8% of Kaafu is within 2 hours of a hospital, against HDX's car-only 77.4%** (17.4% across all 23 islands).
- **Leaving at 09:00, 8 islands (8,847 people, 28%) have no scheduled boat that gets them to a Greater Malé hospital by Thursday night.** Their only boat to Malé leaves early in the morning on 2–3 days a week.
- **16 of 23 islands (17,487 people) have a direct boat to Malé on 3 days a week or fewer**; 6 islands have no direct boat at all and must change boats. Inner Kaafu has one six days a week. No public ferry runs on Fridays.
- **Once in Greater Malé, the nearest hospital is 7–12 minutes from each ferry terminal on foot.** The boat timetable, not the last mile, decides the trip.
- FollowMe boat tracks show heavy speedboat traffic near Malé (e.g. Hulhumalé–Malé: 32 fast trips a day, median 6 min); scheduled ferries and observed slow boats agree to within about 5 min per leg.

## What the dashboard shows

A Streamlit app (`app/streamlit_app.py`):
- **Headline:** HDX's car-only 77.4% against the share of Kaafu within 2 hours *with real boats leaving at a chosen time* (07:00 by default), plus the 30/60/90/120/240-minute table next to HDX.
- **Map:** islands coloured by minutes to hospital (blue up to 1 h, amber 1–2 h, red over 2 h, grey no scheduled boat), boat links, hospitals, terminals, and optional bus routes and observed boat trips.
- **Island panel:** the trip as wait / boat / transfer / last mile, boats per day, last practical departure, and scheduled against observed boat time.
- **Through the day:** the share within 2 hours by departure time, and Avas unserved taxi requests by hour.
- **What-if sliders:** ferry frequency per route, an added evening run, bus frequency, taxi availability, Thulusdhoo hospital opening, and scheduled or observed boat times.
- **Best ferry change:** the single added departure that brings the most people within 2 hours.

The model runs one service day, Wednesday. With default settings the app shows the published results in `data/processed/`; any other setting reruns the routing engine on the same inputs.

## Setup

Python 3.11 or newer.

**Windows (PowerShell):**
```powershell
git clone https://github.com/zayanazil/datathon_tbd.git
cd datathon_tbd
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q                         # 26 tests
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py
```

**macOS / Linux:**
```bash
git clone https://github.com/zayanazil/datathon_tbd.git
cd datathon_tbd
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q                                             # 26 tests
streamlit run app/streamlit_app.py
```

Then open http://localhost:8501. Stop the app with Ctrl+C.

- **No raw data is needed to run the app or the tests.** Everything they read is committed in `data/sheets/` and `data/processed/`.
- **On a slow connection,** add `--timeout 120 --retries 10` to `pip install`.

### Rebuilding the outputs (optional)

Only needed if inputs or parameters change. It needs the restricted raw data, which is never committed:

```
data/raw/followme_kaafu_aug2025.parquet        FollowMe pings, Kaafu/AA/ADh/V, Aug 2025 (no IMEIs)
data/raw/avas/avas_rides_aug_sep_2026.csv      Avas taxi requests
data/raw/team_kandu/rtl_bus_stops.csv          RTL bus stops (Team Kandu)
data/raw/team_kandu/rtl_bus_departures.csv     RTL bus departures (Team Kandu)
```

The FollowMe parquet is made from the organisers' raw daily CSVs by `prep/followme_queries.sql` (DuckDB CLI; it replaces each IMEI with its md5 hash). The input sheets in `data/sheets/` were compiled before the build from the sources below; how each was made is documented beside it in `docs/*.txt`.

Run from the repo root, with the package importable (`pip install -e .` once, or set `PYTHONPATH=src`), in this order:

```
python -m kaafu.geo              # terminals, OSM island zones, bus routes, static maps (needs internet once for OSM)
python -m kaafu.avas             # avas_hourly.csv
python -m kaafu.lastmile         # last_mile.csv (terminal -> hospital by walk, bus, taxi, per hour)
python -m kaafu.followme --month # observed_trips.csv, observed_pairs.csv
python -m kaafu.timetable        # connections.csv
python -m kaafu.indicators       # access_results.csv, island_summary.csv, indicators
python -m kaafu.scenarios        # best_ferry_change.csv
python -m kaafu.m3_figures       # slide charts in docs/figures/
```

The dashboard's bus routes on roads (`bus_road_paths.json`) come from `python -c "from kaafu import dashboard; dashboard.write_bus_road_paths()"`, which needs internet.

## Repository layout

```
app/streamlit_app.py     the dashboard (theme in .streamlit/, brand in app/assets/)
data/sheets/             input sheets: ferry timetable, bus hours and headways, islands, facilities, names, HDX
data/processed/          model outputs (committed, no IMEIs)
data/raw/                restricted raw data (git-ignored)
docs/                    notes on each input sheet (*.txt) and figures/ (slide maps and charts)
prep/followme_queries.sql  DuckDB query that made the FollowMe extract from the raw files
src/kaafu/
  config.py              paths and every parameter and assumption
  geo.py                 terminals, island zones, map layers, static maps          M1
  lastmile.py            terminal -> hospital by walk, bus, taxi, per hour        M1
  avas.py                taxi unserved share and speed by zone and hour          M2
  followme.py            GPS pings -> stops -> trips -> observed pair times      M2
  timetable.py           ferry sheet -> boat connections                         M3
  routing.py             connection scan, door-to-door breakdown                 M3
  indicators.py          island summary, population within X, HDX, NSDS          M3
  scenarios.py           what-if levers, run_scenario(), best ferry change       M3
  m3_figures.py          slide charts and numbers                                M3
  dashboard.py           the app's loaders, checks and slider -> scenario mapping M4
tests/                   test_routing.py, test_data.py, test_dashboard.py
```

## Method

1. **Boats.** The CFN Zone 3 ferry timetable (routes 301–309, effective 1 Aug 2026) and the Malé–Villimalé ferry become one row per boat leg. Wednesday's legs are kept, plus Thursday's shifted by 24 hours, so a late start finds the next morning's boat.
2. **Earliest arrival.** A connection scan goes through every leg in departure order and keeps the earliest time each island or Greater Malé terminal can be reached. Staying on the same boat is free; changing boats takes at least 10 minutes. Home to harbour takes 5 minutes.
3. **Last mile.** At each terminal, the fastest option at that hour is added:
   - walking: 5 min to leave the boat + straight line at 80 m/min;
   - a bus within its service hours: wait from the timetable headway, ride from RTL timetables;
   - a taxi: Avas drive times and speeds, plus a wait that grows with the share of unserved requests that hour.
4. **Results.** 23 islands × 96 leave-home times (every 15 min) × 2 targets: the nearest Greater Malé hospital, and any hospital including the atoll hospitals at Rasdhoo, Mahibadhoo and Felidhoo.
5. **Observed boats.** FollowMe GPS pings are matched to island zones (OpenStreetMap outlines + 300 m), turned into stops and trips, and split into slow (ferry-like) and fast (speedboat) boats. Observed medians can replace scheduled times where at least 5 trips back them.

## Limits and assumptions

All parameters are in `src/kaafu/config.py`.

**Model scope:**
- **One service day (Wednesday), searched together with Thursday.** "No scheduled boat" means none reaches a hospital by Thursday night, not that the island never has service. A full-week search is future work.
- **Scheduled public boats only.** Flights, chartered speedboats and ambulance boats are out of scope; in an emergency people may use them.

**Ferry data:**
- The CFN schedule names only "Male'"; every Malé stop is assumed to be Jetty NO5.
- FollowMe is Aug 2025 against a 2026 timetable. Not every boat carries a tracker, trips are boat movements, not passengers, and the "slow" class also includes cargo boats.

**Walking:**
- Walks are straight lines.
- Island points are often island centres, 100–300 m from the harbour.

**Bus:**
- Stops count within 550 m of a terminal or hospital (so the Malé terminals reach the routes that cross the bridge).
- One bus route per trip.
- Minibus ride times are estimated at 12 km/h.
- One R1 stop (Dharumavantha Hospital, West Side) is added from the official route map.
- R3–R6 times are adjusted from Ramadan 2024 timetables.

**Taxi:**
- Avas is Aug–Sep 2026 and has no rides under 2 km, so short taxi trips use straight-line distance × 1.4 at the zone's median speed.
- The taxi pickup wait is assumed (5 min + unserved share × 10 min).

**HDX** is a car-only model with its own population estimate, so compare percentages, not head counts.

## Data sources and credits

| Source | Accessed |
|---|---|
| Census 2022 population: MBS Statistical Yearbook 2026, table 3.3, via Team Kandu shared datasets | 23 Oct 2026 |
| Island outlines, facility and harbour locations © OpenStreetMap contributors (ODbL), via Overpass | 23–24 Oct 2026 |
| Team Kandu shared datasets (odi_connections, RTL bus routes, stops and departures) | 23 Oct 2026 |
| MTCC/RTL ferry and bus timetables | 23–24 Oct 2026 |
| FollowMe boat GPS (Aug 2025) and Avas rides (Aug–Sep 2026), from the organisers | 24 Oct 2026 |
| HDX hospital accessibility indicators (car-only benchmark) | 23 Oct 2026 |
| Bus route road geometry: OSRM (router.project-osrm.org) on OpenStreetMap roads, © OpenStreetMap contributors (ODbL) | 24 Oct 2026 |

MTCC.xlsx passenger counts are randomly generated and are not used for findings. MACL flight data is not used.

## AI tools used

**Tool:** Claude Code (Anthropic's AI coding assistant), used by every member to write code, run data checks and draft documentation. Every member directed and reviewed the work; the problem framing, scope decisions and the choice of assumptions are the team's.

- **Prep (23 Oct):** `islands.csv`, `facilities.csv` and `island_names.csv` were built with AI-assisted scripts outside this repo (Overpass queries, name matching). `prep/followme_queries.sql` (the FollowMe extract) was AI-assisted.
- **M1 (Zayan), GIS:** all of `src/kaafu/geo.py` and `src/kaafu/lastmile.py`, written with Claude Code:
  - terminals and their checks;
  - OSM island zones (Overpass, polygon building, buffering, fallback, caching);
  - map layers and `example_deck()`, static maps, `male_bound_days()`;
  - walk, bus and taxi last mile, including the R1 stop addition.
  
  Claude Code also ran the supporting analysis: the facilities cross-check, the bus-radius and R1 investigations, colour-vision validation of the map palettes, the boat-days table, and the fresh-clone test. Plus the repo setup and the first `config.py`.
- **M2 (Eish), movement:** `src/kaafu/avas.py`, `src/kaafu/followme.py` and M2's settings in `config.py`, written with Claude Code. So were the Avas and FollowMe data checks: speed against distance, pickup × dropoff zones, GPS jitter, tracker sleeps, too-fast trips, and timetable legs against observed medians.
- **M3 (Al), network and indicators:** all M3 code, tests and figures were written with Claude Code: `timetable.py`, `routing.py`, `indicators.py`, `scenarios.py`, `m3_figures.py` and `tests/test_routing.py`.
- **M4 (Saroof), lead and dashboard:** all M4 code was written with Claude Code: `app/streamlit_app.py` with its brand and theme, `src/kaafu/dashboard.py`, `tests/test_data.py` and `tests/test_dashboard.py`, the OSRM road snapping, and the checks against M3's outputs.
- **Writing:** member handovers, draft slide text and this README were prepared with Claude Code.

## Team

M1 Zayan (GIS) · M2 Eish (movement data) · M3 Al (network and indicators) · M4 Saroof (lead and dashboard)
