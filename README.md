# Kaafu Connect – Maldives Datathon 2026

## Problem

Global accessibility estimates (HDX) assume you can drive to hospital: by that measure **77.4% of Kaafu** and 46% of Maldivians are within 2 hours of a hospital. Island people go by boat, on a timetable. Kaafu Connect estimates the real door-to-door time (wait + ferry + transfer + walk, bus or taxi) from **23 islands** (9 in Kaafu, plus 14 in Alif Alif, Alif Dhaalu and Vaavu with direct boats to Malé; 31,414 people, Census 2022) to a hospital in Greater Malé, at any time of day.

Users: MTCC and the Ministry of Transport (where to add or retime ferries) and MBS (two NSDS indicators with no base year).

## What it shows

A Streamlit dashboard with:
- the headline: HDX's car-only 77.4% against the share of Kaafu within 2 h *with real boats leaving at a chosen time*, plus the 30/60/90/120/240-minute table next to HDX;
- a map of islands coloured by minutes to hospital, boat links, hospitals and terminals;
- an island panel: the trip as wait / boat / transfer / last mile, boats per day, last practical departure, scheduled vs observed;
- the share within 2 h through the day, and Avas unserved taxi requests by hour;
- what-if sliders: ferry frequency, an added evening run, bus frequency, taxi availability, Thulusdhoo hospital opening, scheduled vs observed boat times;
- a ranking of the single ferry change that helps the most people.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate     # Python 3.11+
pip install -r requirements.txt                       # also installs src/kaafu in editable mode
python -m kaafu.pipeline                              # builds data/processed/ (add --skip-followme to skip GPS)
pytest
streamlit run app/streamlit_app.py
```

**Raw data** (never committed) goes in `data/raw/`, shared by USB or drive:
- `avas_rides_aug_sep_2026.csv` → taxi speeds and unserved share (`avas_hourly.csv`), taxi OD medians;
- `followme_kaafu_aug2025.parquet` or `FollowMe_august_2025/*.csv` → `observed_trips.csv`, `observed_pairs.csv`;
- Team Kandu `rtl_bus_stops.csv`, `rtl_bus_routes.csv`, `rtl_bus_departures.csv` → bus last mile and exact terminal coordinates;
- optional Geofabrik `gis_osm_places_a_free_1.shp` → island outlines (otherwise 600 m circles).

Every step works without its raw file and says what it fell back to. The app runs from a fresh clone with only the committed `data/sheets/` and `data/processed/`.

### Sheets

`data/sheets/` holds the team's sheets from `main`, including the real CFN ferry timetable (effective 1 Aug 2026), bus service hours and headways, and the HDX benchmark. If `ferry_timetable.csv` is ever missing, `python tests/make_placeholders.py` writes an invented stand-in to `data/placeholder/` (git-ignored) and the app shows a red banner.

## Repository layout

```
CLAUDE.md                one line: read docs/CLAUDE_HANDOVER.md, then docs/BUILD_PLAN.md
docs/                    handover, build plan, model note (PDF), sheet notes, members/
data/sheets/             islands, facilities, island_names, hdx_benchmark (committed)
data/placeholder/        stand-in ferry timetable (generated)
data/raw/                restricted raw data (git-ignored)
data/processed/          pipeline outputs (BUILD_PLAN section 4 contracts)
src/kaafu/
  config.py              every parameter (BUILD_PLAN section 5)
  load.py                sheet loaders and data checks
  geo.py                 terminals, island zones, footpaths, map links
  lastmile.py            terminal → hospital by walk, bus, taxi, per hour
  avas.py                taxi speed and unserved share by zone and hour
  followme.py            GPS pings → stops → trips → observed pair times (IMEIs hashed)
  timetable.py           ferry sheet → connections (+ next day), observed swap-in
  routing.py             connection scan, door-to-door breakdown
  indicators.py          shares within X, last practical departure, HDX, NSDS
  scenarios.py           what-if levers, run_scenario(), best_ferry_change()
  pipeline.py            builds every processed output in order
app/streamlit_app.py     the dashboard
tests/                   test_data.py, test_routing.py, make_placeholders.py
```

## Method

The model is a timetable journey planner, not a trained model. All scheduled boat legs for the chosen day (Wednesday by default), plus the next day shifted by 24 h, are scanned once in departure order ("connection scan"), keeping the earliest time each island or Greater Malé terminal can be reached. Staying on the same boat is free; changing boats needs 10 min. At each terminal the fastest available last mile (walk, bus within service hours, or taxi with Avas speeds and a retry penalty for unserved requests) is added to reach the hospital door. This runs for 23 islands × 96 leave-home times × 2 targets (nearest Greater Malé hospital; any hospital including the atoll hospitals). FollowMe GPS tracks give observed boat times, which can replace scheduled durations where at least 5 trips back them, and add observed speedboat runs.

## Limits

- Assumptions in `src/kaafu/config.py`: 5 min home to harbour, 5 min boat to street, 10 min boat change, 80 m/min straight-line walking, taxi base wait 5 min + unserved share × 10 min.
- Malé ferry rows without a named terminal land at Jetty NO5. Jetty NO5 and Maafannu terminal coordinates are estimates until `rtl_bus_stops.csv` is loaded.
- One service day at a time; ferries differ by day.
- FollowMe is Aug 2025 against a 2026 timetable; not every boat has a tracker; trips are boat movements, not passengers.
- Avas is Aug–Sep 2026 and covers rides of 2 km or more.
- Out of scope: flights, chartered speedboats, ambulance boats. 23 islands only.
- Senahiya military hospital is included (`INCLUDE_SENAHIYA`); public emergency access is unconfirmed.
- HDX is a car-only model with its own population: compare percentages, not head counts.

## Data sources and credits

| Source | Accessed |
|---|---|
| Census 2022 population: MBS Statistical Yearbook 2026, table 3.3, via Team Kandu shared datasets | 23 Oct 2026 |
| Facility and harbour locations © OpenStreetMap contributors (ODbL), via Overpass | 23 Oct 2026 |
| Team Kandu shared datasets (odi_connections, RTL bus routes, stops and departures) | 23 Oct 2026 |
| MTCC/RTL ferry and bus timetables | 23–24 Oct 2026 |
| FollowMe boat GPS (Aug 2025) and Avas rides (Aug–Sep 2026), from the organisers | 24 Oct 2026 |
| HDX hospital accessibility indicators (car-only benchmark) | 23 Oct 2026 |
| Bus route road geometry: OSRM (router.project-osrm.org) on OpenStreetMap roads, © OpenStreetMap contributors (ODbL) | 24 Oct 2026 |

MTCC.xlsx passenger counts are randomly generated and are not used for findings. MACL flight data is not used.

## AI-assisted parts

- **Prep (23 Oct):** `islands.csv`, `facilities.csv` and `island_names.csv` were built with AI-assisted scripts outside this repo (Overpass queries, name matching).
- **Build (24 Oct), Claude Code:** the project scaffold, every module in `src/kaafu/`, `app/streamlit_app.py`, the tests, `tests/make_placeholders.py` (the placeholder timetable) and this README. The team reviewed the method against `docs/BUILD_PLAN.md`; add each member's own session notes here.
