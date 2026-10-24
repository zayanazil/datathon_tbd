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
pip install -r requirements.txt
python -m pytest                                      # 26 tests
streamlit run app/streamlit_app.py                    # http://localhost:8501
```

The app runs from a fresh clone with only the committed `data/sheets/` and `data/processed/`: no raw data needed.

**Rebuilding outputs** needs the raw data in `data/raw/` (never committed; shared by USB or drive) and is done by each owner's module, from the repo root with `PYTHONPATH=src`:
- M1: `python -m kaafu.geo`, `python -m kaafu.lastmile` → terminals, island zones, bus routes, `last_mile.csv`;
- M2: `python -m kaafu.avas`, `python -m kaafu.followme --month` → `avas_hourly.csv`, `observed_trips.csv`, `observed_pairs.csv`;
- M3: `python -m kaafu.timetable`, `python -m kaafu.indicators`, `python -m kaafu.scenarios` → connections, results, indicators, best ferry change;
- M4: `python -c "from kaafu import dashboard; dashboard.write_bus_road_paths()"` → `bus_road_paths.json` (needs internet once).

### Where the data comes from

All data is the team's own; there is no placeholder or dummy data.

| Files | Owner |
|---|---|
| `data/sheets/`: ferry timetable (CFN, effective 1 Aug 2026), bus hours and headways, islands, facilities, names, HDX | team |
| `terminals.csv`, `island_zones.geojson`, `last_mile.csv`, `bus_routes.csv` | M1 Zayan |
| `avas_hourly.csv`, `observed_trips.csv`, `observed_pairs.csv` | M2 Eish |
| `connections.csv`, `access_results.csv`, `island_summary.csv`, `best_ferry_change.csv`, `nsds_figures.csv`, `hdx_comparison.csv`, `population_within.csv` | M3 Al |
| `bus_road_paths.json`: M1's bus routes snapped to OSM roads via OSRM | M4 Saroof |

With the default settings (Wednesday, scheduled boats, no what-ifs) the dashboard shows M3's `access_results.csv` and `island_summary.csv` as published. Any other setting runs M3's `scenarios.run_scenario` on the same inputs (it reproduces the published run exactly: all 4,416 journeys). The Data tab says which one is on screen.

## Repository layout

```
CLAUDE.md                one line: read docs/CLAUDE_HANDOVER.md, then docs/BUILD_PLAN.md
docs/                    handover, build plan, sheet notes, members/, figures/
m2_claude.md, m3_claude.md, m3_handover.md, m4_handover.md   members' status and handovers
data/sheets/             team sheets (committed)
data/raw/                restricted raw data (git-ignored)
data/processed/          outputs (BUILD_PLAN section 4 contracts; committed, no IMEIs)
src/kaafu/
  config.py              paths and every parameter (shared)
  geo.py                 terminals, island zones, map layers, static maps          M1
  lastmile.py            terminal → hospital by walk, bus, taxi, per hour          M1
  avas.py                taxi unserved share and speed by zone and hour            M2
  followme.py            GPS pings → stops → trips → observed pair times           M2
  timetable.py           ferry sheet → connections                                 M3
  routing.py             connection scan, door-to-door breakdown                   M3
  indicators.py          island summary, population within X, HDX, NSDS            M3
  scenarios.py           what-if levers, run_scenario(), best ferry change         M3
  m3_figures.py          slide charts and numbers                                  M3
  dashboard.py           loaders, checks, slider → M3 mapping, indicators at a
                         chosen time, bus routes on roads (the dashboard's adapter) M4
app/streamlit_app.py     the dashboard (theme in .streamlit/, brand in app/assets/) M4
tests/                   test_routing.py (M3), test_data.py and test_dashboard.py (M4)
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
- **Build (24 Oct), Claude Code, M4:** `app/streamlit_app.py` and its brand and theme, `src/kaafu/dashboard.py`, `tests/test_data.py`, `tests/test_dashboard.py`, the OSRM road snapping (`bus_road_paths.json`), the checks against M3's outputs, `m4_handover.md` and this README.
- **M1, M2, M3:** each member's Claude Code work is listed in their own files (`m2_claude.md`, `m3_claude.md` / `m3_handover.md`, Zayan's notes on `zayan`).
