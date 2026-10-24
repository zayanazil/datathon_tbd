# M3 network and indicators: status

**Owner:** Al (M3) · **Branch:** `m3-network` · **Last updated:** 24 Oct 2026, after Step 5 (final figures for slides 5–6)

**Full write-up (decisions, doubts, links to M1/M2, slide content): [`m3_handover.md`](m3_handover.md).**

This file says what M3 has built, what it needs from the rest of the team, and what comes next. It's updated after each major step. Team: M1 Zayan (GIS), M2 Eish (movement), M3 Al (network), M4 Saroof (lead, dashboard).

## Status at a glance

| Step | Status |
|---|---|
| 1. `timetable.py` → `connections.csv` | Done |
| 2. `routing.py` + toy tests | Done; matches the reference table in `M3_network.md` for all 23 islands |
| 3. `access_results.csv` + `island_summary.csv` (H3) | Done, with **Zayan's real `last_mile.csv`** |
| 4. Indicators, HDX, NSDS, scenarios, best ferry change | Done, including the bus and taxi sliders |
| 4. Observed boat times | Done: leg durations, synthetic speedboat departures, `observed_gap_min` |
| 5. Final figures for slides 5–6 | Done: six charts and the slide numbers in `docs/figures/m3_*` |

Tests: `python -m pytest` → 14 passed.

**Branch contents:**
- `main`, `zayan` and `m2-movement` are all merged in. This branch has the official `config.py`, `pyproject.toml`, Zayan's `last_mile.csv` (real Avas taxi times) and Eish's `observed_pairs.csv`/`observed_trips.csv`.
- `data/sheets/` is identical to `main`'s.

## What each member needs to know

### Saroof (M4): config, dashboard, merge

- **My code uses the shared `config.py`** (the version with `SHEETS`, `PROCESSED`, the per-file `*_CSV` paths, `GM_HOSPITALS`, `ATOLL_HOSPITALS`, `DAYTIME_START_MIN`/`DAYTIME_END_MIN`, `EVENING_RUN_TIMES`, `READ_ENCODING`/`WRITE_ENCODING` and `MINUTES_PER_DAY`). Nothing is hardcoded on the M3 side.
  - It's the one from the `zayan` branch, merged in here.
  - **If you rename or remove any of those settings, tell Al.**
  - The M3 settings are the ones under "Routing and indicators (M3)", plus `DAY`, `NEXT_DAY`, `ACCESS_MIN`, `BOAT_TRANSFER_MIN`, `TERMINAL_EXIT_MIN`, `WALK_M_PER_MIN` and `INCLUDE_SENAHIYA`/`SENAHIYA_ID`.
- **The dashboard entry point is `scenarios.run_scenario(params)`**, which returns `(access_results, island_summary)` and is cached. Its params:

  | Param | Status | Meaning |
  |---|---|---|
  | `ferry_factor` | works | `{route_id: factor}`, 0.5–3 |
  | `extra_runs` | works | `[(route_id, minute)]`, e.g. `[("307", 1080)]` for 18:00 |
  | `thulusdhoo_hospital` | works | `True` adds K.Thulusdhoo as an atoll hospital (`any_hospital` only) |
  | `observed` | works | Re-times CFN legs with Eish's slow medians **and** adds synthetic speedboat departures (see "Synthetic speedboat departures" below). |
  | `speedboats` | works | Default `True`. With `observed`, `False` gives re-timed ferries only. |
  | `bus_factor` | works | 0.5–3; the bus wait is divided by it |
  | `taxi_availability` | works | 0–1; cuts the Avas unserved share (the part of the taxi wait above `TAXI_BASE_WAIT_MIN`) |

  **The bus and taxi sliders don't move the headline**, by design of the measure, so they may not be worth showing:
  - From every Malé/Hulhumalé terminal, the nearest Greater Malé hospital is a 6.6–11.2 min walk.
  - A bus or taxi to any other hospital takes longer, at every hour.
  - So the walk always wins, and changing bus or taxi times changes no row of `access_results`.
  | `label` | optional | value of the `scenario` column |

  `run_scenario({})` gives exactly the base `access_results.csv`. One scenario takes about a second.
- **A blank `day_median_min` (11 islands: AA, V, Kaashidhoo, Gaafaru) is expected, not missing data.**
  - Most daytime departures there can't reach a hospital before the end of Thursday, because the next boat is at the weekend.
  - On the map and in the island panel, show it as **"unreachable today"** (the BUILD_PLAN map category), not an empty cell.
  - For the worst-served ranking on slide 5, sort by `last_practical_departure`, which every island has.
  - If asked why Alif Dhaalu has a number but AA doesn't: we scan Wednesday + Thursday; Alif Dhaalu's boat is Thursday, while AA's next one is Sunday.
  - Scanning a full week goes on the roadmap slide.
- **There are extra tables for the dashboard and slides**, beyond the §4 contracts, all in `data/processed/` (described below): `population_within.csv`, `hdx_comparison.csv`, `nsds_figures.csv` and `best_ferry_change.csv`.
- **Branch files:**
  - `main` is merged into `m3-network`, and `data/sheets/` is identical to `main`'s.
  - The branch also adds an empty `src/kaafu/__init__.py`, the same as on `zayan`.
  - Zayan's `config.py` on the `zayan` branch is identical to the one my code was checked against.

### Zayan (M1): last mile

- **Your `last_mile.csv` is in use** (merged from `zayan`). It matches the contract, and the checks pass:
  - all 24 hours for every row;
  - Villimalé reaches only H06;
  - the walk times match my old placeholder exactly.
- **Bus and taxi waits:** the `bus_factor` and `taxi_availability` sliders read the wait from your `detail` text (`wait 7.5`). **Please keep the `wait <number>` wording in `detail`.**
- **Real Avas taxi times are in** (your `e9d0805`, pulled at 13:56). I reran `indicators` and `scenarios`: every output is identical, because no result uses a taxi (the nearest hospital is always a walk from the terminal).
- **Fallback:** `routing.placeholder_last_mile()` only runs if `last_mile.csv` is missing.
- **`docs/facilities.txt`** is now the current note (fixed on `zayan`).

### Eish (M2): observed boat times

- **Your `observed_pairs.csv` and `observed_trips.csv` are in use** (merged from `m2-movement`).
- **Observed switch (`scenarios.observed_durations`):**
  - A leg takes its pair's `slow` median where `n_trips ≥ OBSERVED_MIN_TRIPS`.
  - It doesn't if the median is more than **`OBSERVED_MAX_SLOWDOWN` (1.5×, new in `config.py`)** times the scheduled time. That's your cargo-dhoni suggestion.
  - A boat can't leave a stop before it arrives, so a slowed leg delays the rest of its trip.
  - 55 CFN legs are re-timed, mostly by a few minutes. The Villimalé ferry is unchanged (7.7 rounds to 8).
- **Effect on results:** island times move by −6 to +37 min, and the headline stays at 0% within 2 h. On their own, re-timed ferries don't change the picture.
- **`observed_gap_min`:**
  - Definition: scheduled minutes from the island to a Greater Malé terminal on one timetabled trip, minus your median of **all** tracked trips from the island to Malé/Hulhumalé/Villimalé (≥ 5 trips).
  - Positive means boats are faster than the timetable. E.g. Thoddoo 387 (route 303 loops via Rasdhoo and Ukulhas), V islands 206–237, Kaashidhoo 165, Huraa 37, Himmafushi 20.
  - Blank where there's no direct scheduled boat: Mathiveri, Bodufolhudhoo, and the ADh islands except Mahibadhoo.
- **Synthetic speedboat departures** are built from your four busy fast pairs (see the note below).

## How to run

From the repo root (or `pip install -e .` once, then drop the `PYTHONPATH=src`):

```bash
PYTHONPATH=src python -m kaafu.timetable    # data/processed/connections.csv
PYTHONPATH=src python -m kaafu.indicators   # access_results, island_summary, population_within, hdx_comparison, nsds_figures
PYTHONPATH=src python -m kaafu.scenarios    # best_ferry_change.csv (30-90 s; one-off, not for the live dashboard)
PYTHONPATH=src python -m kaafu.m3_figures   # docs/figures/m3_*.png and m3_slide_numbers.md (~10 s; run after the two above)
python -m pytest
```

Every `main()` and `run_scenario()` takes an optional `cfg` argument, which defaults to `kaafu.config`, so a test can pass its own.

## Files (M3 owns these)

| File | What it does |
|---|---|
| `src/kaafu/timetable.py` | Ferry sheet to connections: Wednesday legs, plus **Thursday's own legs** at +1440 (`trip_id` + `_d2`). Greater Malé stops become terminal IDs. Stops if a name isn't in `island_names.csv`. |
| `src/kaafu/routing.py` | Connection scan (`earliest_arrival`), door-to-door times (`door_to_door`), trip breakdown, placeholder last mile, and `access_results()` for all islands × departures × targets. |
| `src/kaafu/indicators.py` | `island_summary`, `population_within`, `hdx_comparison`, `nsds_figures`; `main()` writes the base outputs. |
| `src/kaafu/scenarios.py` | `run_scenario`, `scale_route` (ferry factor), `extra_run`, Thulusdhoo hospital, `best_ferry_change`, observed durations and speedboat departures, bus/taxi adjustment. |
| `src/kaafu/m3_figures.py` | Step 5: the slide charts and `m3_slide_numbers.md`, from the base scenario and the observed switch. |
| `tests/test_routing.py` | 12 toy tests: direct boat, next morning, transfer time, staying on board, later never earlier, breakdown adds up, own hospital, re-spacing, extra run, bus/taxi slider adjustment. |

## Outputs in `data/processed/`

| File | Rows | Notes |
|---|---|---|
| `connections.csv` | 600 | 50 CFN + 250 Villimalé legs per day, Wed + Thu. (`M3_network.md` said "about 40" CFN legs; a hand count gives 50.) |
| `access_results.csv` | 4,416 | 23 islands × 96 departures × 2 targets. A blank `total_min` means unreachable; `path` then says `unreachable: …`. |
| `island_summary.csv` | 23 | Target `gm_hospital`. A blank median or worst value means unreachable for most daytime departures. `observed_gap_min` is filled from Eish's data (see Eish's section). |
| `population_within.csv` | 1,940 | Share within 30/60/90/120/240 min, Kaafu and all 23 islands, both targets, every departure plus `day_median`. |
| `hdx_comparison.csv` | 10 | Daytime median against HDX car-only: Kaafu against HDX Kaafu, all 23 against HDX Maldives. Percentages only. |
| `nsds_figures.csv` | 10 | Direct boat to Greater Malé, same-day boat with changes, health facility within 30 min, hospital within 2 h. |
| `best_ferry_change.csv` | 27 | One extra run per CFN route × 18:00/20:00/22:00, ranked. |

## Synthetic speedboat departures (observed switch)

**Agreed with Saroof (M4).** Eish's hours are taken as recorded, including Dhiffushi's boats from 01:00.

**Why:**
- The timetable has public ferries only, once or twice a day, but Eish's FollowMe data shows that most trips from the islands near Malé are speedboats running all day (e.g. 87% of Thulusdhoo's trips).
- Re-timing the ferries alone leaves the headline at 0% within 2 h, so `observed: True` also adds these boats.

**How (`scenarios.speedboat_departures`):**
- **Which pairs:** island → Greater Malé pairs whose `fast` trips average at least **`SPEEDBOAT_MIN_TRIPS_PER_DAY` (5, new in `config.py`)** a day.
- **Spacing:** one departure every `round((last_hour − first_hour) × 60 / trips_per_day)` min, from `first_hour` to `last_hour`.
- **Timing:** each takes the observed median, on Wednesday and again on Thursday.
- **Arrival:** `T_MALE_NORTH`, the same Jetty NO5 assumption as the CFN.
- **Labels:** `route_id = SPEEDBOAT`, `mode = speedboat_observed`, `estimated = yes`, `source = "observed boat movements, not a published schedule"`.

| From | Departures a day | First–last | Ride |
|---|---|---|---|
| K.Thulusdhoo | 15 | 06:00–22:20 | 32 min |
| K.Himmafushi | 8 | 05:00–22:16 | 18 min |
| K.Dhiffushi | 8 | 01:00–16:59 | 47 min |
| AA.Thoddoo | 6 | 05:00–21:35 | 73 min |

**Limits (for the slide):**
- These are boat movements from August 2025 trackers, not a published 2026 schedule.
- We assume anyone can board them, but some may be private, resort or chartered boats.
- Departures are spread evenly across the hours seen.
- The ferry-only result stays the default (`observed: False`). Always say which one a number comes from.

**Effect** (within 2 h of a Greater Malé hospital, daytime median):

| | Ferries only | Re-timed ferries only | + speedboats |
|---|---|---|---|
| Kaafu | 0% | 0% | **21.5%** |
| All 23 islands | 0% | 0% | **12.1%** |

- **Daytime medians:**
  - Thulusdhoo: 1,176 → 83 min.
  - Himmafushi: 1,131 → 98.
  - Dhiffushi: 1,221 → 132.
  - Thoddoo: blank → 182.
  - Huraa: 1,146 → 358 (it connects via Himmafushi).
- **Last practical departures** move from early morning to 21:30–22:15 for Thulusdhoo, Himmafushi and Thoddoo.

## Current results (public CFN ferries, Wednesday, Zayan's last mile)

- **These are the ferry-only numbers.** For the speedboat effect, see the section above.
- **The real last mile changed nothing:** the nearest hospital is always a short walk from the terminal.

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
- `facilities.txt` there is the old note; `facilities (1).txt` is the current one. The sheet notes (`*.txt`) live in `docs/` on the `zayan` branch, not in `data/sheets/`.
- `raw/followme_check.txt.txt` is a blank template. `MACL/` is missing, but it isn't used.

## Next

1. **Merge:** `m3-network` into `main`. Code and outputs are checked against the shared `config.py`.
2. **Slides 5–6:** use the figures below. Rerun `m3_figures` if any input changes.

## Figures for slides 5–6 (`docs/figures/`)

Every chart has the same colours: orange ring = public ferries only, blue dot = with observed speedboats, grey = HDX car-only. Each carries the caption "Wednesday CFN timetable; observed speedboats from FollowMe, Aug 2025 (not a published schedule); Malé jetty assumed Jetty NO5".

| File | Slide | What it shows |
|---|---|---|
| `m3_within_vs_hdx.png` | 5 | Share within 30 min–4 h of the nearest hospital (daytime median) against HDX: Kaafu 0% / 22% against 77% at 2 h |
| `m3_within_2h_through_day.png` | 5 | Share of Kaafu within 2 h of a Malé hospital by departure time, with HDX as a line |
| `m3_worst_served.png` | 5 | Daytime median per island, worst first, with an "unreachable today" column |
| `m3_last_departure.png` | 5 | Last practical departure per island; ADh has none on Wednesday |
| `m3_scheduled_vs_observed.png` | 5 (with Eish) | Quickest scheduled ferry against the observed median boat time to Malé |
| `m3_best_ferry_change.png` | 6 | Best extra evening run of each CFN route, by people-hours saved |
| `m3_slide_numbers.md` | 5–6 | All the headline numbers as tables, including the NSDS figures |
