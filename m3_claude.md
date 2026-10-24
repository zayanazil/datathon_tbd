# M3 network and indicators: status

**Owner:** Al (M3) · **Branch:** `m3-network` · **Last updated:** 24 Oct 2026, after Step 4 (independent parts)

This file says what M3 has built, what it needs from the rest of the team, and what comes next. It's updated after each major step. Team: M1 Zayan (GIS), M2 Eish (movement), M3 Al (network), M4 Saroof (lead, dashboard).

## Status at a glance

| Step | Status |
|---|---|
| 1. `timetable.py` → `connections.csv` | Done |
| 2. `routing.py` + toy tests | Done; matches the reference table in `M3_network.md` for all 23 islands |
| 3. `access_results.csv` + `island_summary.csv` (H3) | Done, with a **placeholder walk-only last mile** |
| 4. Indicators, HDX, NSDS, scenarios, best ferry change | Done except the parts that need M1/M2 files (below) |
| 4. Observed boat times, bus and taxi sliders | **Waiting** for Eish's and Zayan's files |
| 5. Final figures for slides 5–6 | Not started; best done once the real last mile and observed times are in |

Tests: `python -m pytest tests` → 11 passed.

## What each member needs to know

### Saroof (M4): config, dashboard, merge

- **`config.py` doesn't exist yet**, so my code takes the config as an argument. When you write it, use the BUILD_PLAN §5 names. My code uses: `DAY`, `NEXT_DAY`, `ACCESS_MIN`, `BOAT_TRANSFER_MIN`, `TERMINAL_EXIT_MIN`, `WALK_M_PER_MIN`, `STEP_MIN`, `THRESHOLDS_MIN`, `INCLUDE_SENAHIYA`, plus two path settings the plan doesn't name: **`SHEETS_DIR`** (`data/sheets`) and **`PROCESSED_DIR`** (`data/processed`). Tell Al if you name them differently.
- **The dashboard entry point is `scenarios.run_scenario(params)`**, which returns `(access_results, island_summary)` and is cached. Its params:

  | Param | Status | Meaning |
  |---|---|---|
  | `ferry_factor` | works | `{route_id: factor}`, 0.5–3 |
  | `extra_runs` | works | `[(route_id, minute)]`, e.g. `[("307", 1080)]` for 18:00 |
  | `thulusdhoo_hospital` | works | `True` adds K.Thulusdhoo as an atoll hospital (`any_hospital` only) |
  | `observed` | waiting for Eish | raises `NotImplementedError` if set |
  | `bus_factor` | waiting for Zayan | raises `NotImplementedError` if not 1 |
  | `taxi_availability` | waiting for Zayan | raises `NotImplementedError` if not 0 |
  | `label` | optional | value of the `scenario` column |

  `run_scenario({})` gives exactly the base `access_results.csv`. One scenario takes about a second.
- **There are extra tables for the dashboard and slides**, beyond the §4 contracts, all in `data/processed/` (described below): `population_within.csv`, `hdx_comparison.csv`, `nsds_figures.csv` and `best_ferry_change.csv`.
- **Branch files:** this branch adds `data/sheets/` (copied from `datasets/data_pack/sheets/`, current versions only) and an empty `src/kaafu/__init__.py`. If you set up the repo layout differently, keep the package importable as `kaafu`.

### Zayan (M1): last mile

- **Until `last_mile.csv` exists, `routing.placeholder_last_mile()` stands in.** It produces walk-only rows in the exact `last_mile.csv` layout:
  - terminal to hospital on the same island: `TERMINAL_EXIT_MIN` + straight line ÷ 80 m/min;
  - atoll-hospital islands: `TERMINAL_EXIT_MIN` + the hospital's `walk_minutes`.

  The terminal coordinates are hardcoded from Team Kandu's bus stops (codes 1008, 1101, 507, 1301).
- **When you drop `data/processed/last_mile.csv` in, my code uses it automatically.** It needs:
  - columns `stop_id, facility_id, hour, mode, minutes, available, detail`;
  - `stop_id` using the terminal IDs `T_MALE_NORTH`, `T_MALE_WEST`, `T_HULHUMALE`, `T_VILLIMALE`;
  - rows for `AA.Rasdhoo` → H07, `ADh.Mahibadhoo` → H08 and `V.Felidhoo` → H09;
  - `available` as true/false (or yes/no).
- **Plausibility from the placeholder,** for you to compare against: Jetty NO5 → IGMH on foot 23 min, Hulhumalé Ferry Terminal → Hulhumalé Hospital 12.5 min.
- **For the sliders, I'll need two things:**
  - **Bus wait in the `detail` column:** for bus rows, the wait in a form I can parse, e.g. `wait=7.5`. `bus_factor` uses it: minutes − wait + wait ÷ factor.
  - **A taxi function** with availability as an input, so `taxi_availability` doesn't recompute your formula.
- **Bus sheets:** `bus_service_hours.csv` (45 rows) and `bus_headways.csv` (117 rows) are now in `data/sheets/` on this branch. The copies in `datasets/data_pack/sheets/` were missing or outdated.

### Eish (M2): observed boat times

- **I need `data/processed/observed_pairs.csv`**, with columns `from_key, to_key, speed_class, n_trips, n_devices, median_min, p90_min, trips_per_day, first_hour, last_hour`, keyed by `island_key`. Use `K.Malé` / `K.Hulhumalé` for the Greater Malé end, or tell me if you use terminal IDs.
- **What I'll do with it:**
  1. Replace scheduled leg durations with the `slow` median where `n_trips ≥ 5`.
  2. Add synthetic speedboat departures for busy `fast` pairs (`trips_per_day ≥ 5`). To agree with Saroof.
  3. Fill `observed_gap_min` in `island_summary.csv`.

## How to run

Until `config.py` exists, pass any object with the attributes above. Once it exists, from the repo root:

```bash
PYTHONPATH=src python -m kaafu.timetable    # data/processed/connections.csv
PYTHONPATH=src python -m kaafu.indicators   # access_results, island_summary, population_within, hdx_comparison, nsds_figures
PYTHONPATH=src python -m kaafu.scenarios    # best_ferry_change.csv (~85 s; one-off, not for the live dashboard)
python -m pytest tests
```

## Files (M3 owns these)

| File | What it does |
|---|---|
| `src/kaafu/timetable.py` | Ferry sheet to connections: Wednesday legs, plus **Thursday's own legs** at +1440 (`trip_id` + `_d2`). Greater Malé stops become terminal IDs. Stops if a name isn't in `island_names.csv`. |
| `src/kaafu/routing.py` | Connection scan (`earliest_arrival`), door-to-door times (`door_to_door`), trip breakdown, placeholder last mile, and `access_results()` for all islands × departures × targets. |
| `src/kaafu/indicators.py` | `island_summary`, `population_within`, `hdx_comparison`, `nsds_figures`; `main()` writes the base outputs. |
| `src/kaafu/scenarios.py` | `run_scenario`, `scale_route` (ferry factor), `extra_run`, Thulusdhoo hospital, `best_ferry_change`. |
| `tests/test_routing.py` | 11 toy tests: direct boat, next morning, transfer time, staying on board, later never earlier, breakdown adds up, own hospital, re-spacing, extra run. |

## Outputs in `data/processed/`

| File | Rows | Notes |
|---|---|---|
| `connections.csv` | 600 | 50 CFN + 250 Villimalé legs per day, Wed + Thu. (`M3_network.md` said "about 40" CFN legs; a hand count gives 50.) |
| `access_results.csv` | 4,416 | 23 islands × 96 departures × 2 targets. A blank `total_min` means unreachable; `path` then says `unreachable: …`. |
| `island_summary.csv` | 23 | Target `gm_hospital`. A blank median or worst value means unreachable for most daytime departures. `observed_gap_min` is blank until Eish's file arrives. |
| `population_within.csv` | 1,940 | Share within 30/60/90/120/240 min, Kaafu and all 23 islands, both targets, every departure plus `day_median`. |
| `hdx_comparison.csv` | 10 | Daytime median against HDX car-only: Kaafu against HDX Kaafu, all 23 against HDX Maldives. Percentages only. |
| `nsds_figures.csv` | 10 | Direct boat to Greater Malé, same-day boat with changes, health facility within 30 min, hospital within 2 h. |
| `best_ferry_change.csv` | 27 | One extra run per CFN route × 18:00/20:00/22:00, ranked. |

## Current results (public CFN ferries, Wednesday, walk-only last mile)

These **will change** once the real last mile and observed speedboat times are in. Public ferries alone make the islands near Malé look much worse than reality, because most people there take speedboats.

- **Within 2 h of any hospital (daytime median):** 0% of Kaafu and 14.3% of all 23 islands. The 14.3% is just the three islands with their own atoll hospital. HDX's car-only estimate is 77.4% of Kaafu and 45.9% of the Maldives.
- **Direct scheduled boat to Greater Malé on Wednesday:** 100% of Kaafu and 76.9% of all 23. Mathiveri, Bodufolhudhoo (they change at Ukulhas) and all of Alif Dhaalu are missing. With changes allowed, same day: 81.9%.
- **Last practical departure to reach a Greater Malé hospital before midnight:**
  - K.Maafushi: 12:30.
  - Most other Kaafu islands: 06:15–07:45.
  - AA and V: 06:15–10:45.
  - Alif Dhaalu: none on Wednesday.
- **Best ferry change:**
  - **Top of the ranking:** an extra evening run on route 307 (Kaashidhoo and Gaafaru) or route 303 (AA). Each saves those islands' people about 640–790 minutes on average across the day's departure times.
  - **Biggest reach:** route 308 at 18:00 helps the most people (6,737), by about 6 hours each.
  - **No change on the new-within-2-hours count:** no extra run brings an island newly within 2 hours by ferry.

## Decisions and assumptions (for the limits slide)

- **Breakdown for journeys with a change of boat:** the breakdown uses the *latest* boats that still give the same arrival, so waiting happens at home and not overnight at a transfer island. Totals are unaffected.
- **Own atoll hospital:** islands with their own atoll hospital score `ACCESS_MIN` (5) for `any_hospital`, as the plan says.
- **`ferry_factor`:**
  - Runs are re-spaced per direction and per day, between the route's first and last run that day.
  - Each copy follows the nearest original run.
  - A route with a single run that day (305, 307 on Wednesday) is left unchanged; use `extra_runs` for those.
  - At least one run is always kept.
- **`extra_runs`:** copies the route's run nearest that time, choosing one that starts outside Greater Malé (towards Malé) when the route has one.
- **Thulusdhoo hospital (`H10`):** placed at the island's harbour point, with the same walk as its health centre (C04).
- **Best ferry change:** an unreachable departure is counted as arriving at the end of Thursday, so the minutes saved are a lower bound. "Newly within 2 h" uses any departure 06:00–18:00.
- **Direct boat (NSDS):** a boat leaving the island on Wednesday that reaches a Greater Malé terminal on the same trip.

## Data checks done on `datasets/`

- Everything M3 needs is present and matches the handover's row counts.
- `datasets/data_pack/sheets/` was missing `bus_headways.csv` and `bus_service_hours.txt`, and had an old 11-row `bus_service_hours.csv`. The correct versions are now in `data/sheets/`.
- `facilities.txt` there is the old note; `facilities (1).txt` is current and was copied as `data/sheets/facilities.txt`.
- `raw/followme_check.txt.txt` is a blank template. `MACL/` is missing, but it isn't used.

## Next

1. **When Zayan's `last_mile.csv` lands:** rerun `indicators` and `scenarios`, recheck the plausibility numbers, and then wire up `bus_factor` and `taxi_availability`.
2. **When Eish's `observed_pairs.csv` lands:** the observed-times switch, synthetic speedboat departures (agree with Saroof) and `observed_gap_min`.
3. **When Saroof's `config.py` lands:** check the names, run everything through `main()`, and merge `m3-network` at H3/H5.
4. **Step 5:**
   - charts for slides 5–6: worst-served islands, population within 1/2/4 h against HDX, share within 2 h through the day, last practical departures, scheduled against observed, best ferry change, NSDS figures;
   - every number labelled "Wednesday, CFN public ferries (+ observed speedboats if used), Jetty NO5 assumed".

## AI-assisted (for the README)

`timetable.py`, `routing.py`, `indicators.py`, `scenarios.py` and `tests/test_routing.py` were written with Claude Code (connection scan, journey breakdown, placeholder last mile, indicators, scenario functions, best ferry change, toy tests).
