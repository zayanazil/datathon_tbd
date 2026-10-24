# M4 handover: lead and dashboard

**Owner:** Saroof (M4) · **Branches:** `m4-dashboard` (the dashboard on the team's code; merge this one) and `Saroof` (the earlier work) · **Written:** 24 Oct 2026

This is the full account of M4's work, for:
- a Claude session that picks it up, merges it, or answers questions about it;
- whoever turns it into slides (M4 owns slides 1, 2, 7 and 8, and the demo).

It says what was built, how it connects to M2 (Eish) and M3 (Al), and through them M1 (Zayan), what we decided and why, and what is still open. Team: M1 Zayan (GIS), M2 Eish (movement), M3 Al (network), M4 Saroof (lead, dashboard). Companion files: [`m3_handover.md`](https://github.com/zayanazil/datathon_tbd/blob/m3-network/m3_handover.md) (Al), [`m2_claude.md`](https://github.com/zayanazil/datathon_tbd/blob/m2-movement/m2_claude.md) (Eish).

---

## 1. What M4 is responsible for

- **The dashboard** (`app/streamlit_app.py`): the thing the judges see in the demo.
- **Turning three workstreams into one app:** M1's map layers and last mile, M2's observed boat times and taxi data, M3's journey results and indicators.
- **The repo, the merge into `main`, the README** and the submission.
- **Slides 1, 2, 7, 8** and the 3-minute demo (BUILD_PLAN section 10).

---

## 2. What I built, in order

On the `Saroof` branch of `zayanazil/datathon_tbd` (from `main`, `b6efe25`), then ported onto the team's code as `m4-dashboard`.

| Commit | What it did |
|---|---|
| `fd86987` | **Scaffold and a complete working pipeline**, following BUILD_PLAN's layout: `config.py`, `load.py` (loaders and data checks), `geo.py`, `lastmile.py`, `avas.py`, `followme.py`, `timetable.py`, `routing.py` (connection scan), `indicators.py`, `scenarios.py`, `pipeline.py`, the dashboard, and 17 tests. Built before the team's outputs existed, so the app could run from H0. |
| `985d22f` | **M1's map layers** (Zayan's `islands_layer`, `boat_links_layer`, `hospitals_layer`, `terminals_layer`, `bus_routes_layer`, `observed_trips_layer`, and his colour bands `ACCESS_BANDS` / `UNREACHABLE`) copied into `geo.py` from `zayan`. **Fixed a bug** where every island turned grey when any slider moved (section 6.3). |
| `1e5b00b` | **Bus routes follow the roads.** M1's routes were straight stop-to-stop lines; each leg is now snapped to OpenStreetMap roads via OSRM and saved in `data/processed/bus_road_paths.json` (144 of 144 legs on roads). |
| `940edc8` | **Brand and UI refresh:** logo and wordmark, Inter font, one teal accent for controls only, tabs, stat cards. Fixed invisible island circles and a time-axis timezone bug found while checking the rendered page. |
| `88d5ed3` | **Real team data only.** `data/processed/` now holds each owner's files, byte-identical to their branches. Removed every placeholder: the invented ferry timetable, its generator, the 20 km/h taxi stand-in, the placeholder banners. Matched M3's definitions for the island summary and the observed switch. |
| `m4-dashboard` | **The dashboard ported onto the team's code**, ready to merge into `main` (section 7.1). |

### The dashboard, as it stands

- **Sidebar:**
  - **Trip:** leave-home time (15-min steps), destination (nearest Greater Malé hospital / any hospital), observed boat times on/off. The service day is Wednesday (M3's engine models one day).
  - **What if:** ferry route and frequency, add an evening run, bus frequency, cut unserved taxi requests, Thulusdhoo hospital opens.
- **Header:** title, context chips (day, time, destination, boat times, "Scenario on").
- **Headline:** HDX car-only 77.4% against the real-boat share for Kaafu at the chosen time.
- **Four stat cards:** Kaafu within 2 h, all 23 within 2 h (both with "vs base" when a slider moves), population-weighted median trip, and people on islands with no scheduled boat (Wed–Thu), with a note naming those islands.
- **Tabs:**
  - **Map:** M1's layers (island circles coloured by minutes, boat links, hospitals, terminals; optional bus routes and observed trips) and an island panel (trip time, wait/boat/transfer/last-mile bar, route, population, boats a day, last practical departure, daytime median, scheduled − observed).
  - **Through the day:** share within 2 h by leave-home time, Kaafu and all 23, with the HDX line; Avas unserved taxi requests by hour.
  - **Benchmarks:** 30/60/90/120/240-min table against HDX; M3's NSDS figures.
  - **Ferry changes:** M3's best-ferry-change ranking.
  - **Data:** every island at this departure, assumptions, and a line saying whether the numbers are M3's published results or a recomputation.

---

## 3. Where the dashboard's data comes from

All data is the team's own; there is no placeholder or dummy data left. No raw data is on GitHub (`data/raw/` is git-ignored on every branch), and the app doesn't need any.

| Files in `data/processed/` | Owner (branch) | Dashboard use |
|---|---|---|
| `access_results.csv`, `island_summary.csv`, `connections.csv` | M3 (`m3-network`) | Headline, cards, map colours, island panel, through-the-day chart, boat links |
| `nsds_figures.csv`, `best_ferry_change.csv` | M3 | Benchmarks and Ferry changes tabs, as published |
| `hdx_comparison.csv`, `population_within.csv` | M3 | Committed, not read by the app (the app computes the same table at the chosen time) |
| `last_mile.csv`, `terminals.csv`, `island_zones.geojson`, `bus_routes.csv` | M1 (`zayan`) | Last mile in recomputed scenarios; map layers |
| `avas_hourly.csv`, `observed_trips.csv`, `observed_pairs.csv` | M2 (`m2-movement`) | Taxi chart; observed switch; observed-trips layer; scheduled − observed |
| `bus_road_paths.json` | M4 (`Saroof`) | Bus routes on roads (derived from M1's `bus_routes.csv`) |
| `data/sheets/*` | team (`main`) | Timetable, islands, facilities, names, HDX |

**The one rule that decides which numbers are shown:**
- **Default settings** (Wednesday, scheduled boats, no what-ifs): the app shows **M3's published files as they are**.
- **Any other setting:** the app runs M3's `scenarios.run_scenario` on the same inputs (on `m4-dashboard`; on `Saroof` it was this branch's own copy).
- The Data tab says which one you are looking at.

---

## 4. How M4 relates to M2 (Eish)

### What M4 takes from M2

| File | Where it shows up | Notes |
|---|---|---|
| `observed_pairs.csv` | The **"Observed boat times"** switch; the **Observed trips** map layer (slow and fast lines) | Rules are M3's (section 5.3): slow medians re-time ferry legs; busy fast pairs become speedboat runs |
| `observed_trips.csv` | **Scheduled − observed** in the island panel (via M3's `observed_gap_min`) | Device IDs are hashed; no IMEIs anywhere |
| `avas_hourly.csv` | **Taxi requests unserved, by hour** chart (zone `all`); taxi wait in the last mile, through M1's `last_mile.csv` | The taxi slider scales M2's unserved share |

### Things from M2 that the dashboard respects
- **"Slow" includes cargo dhonis,** so a slow median only replaces a ferry leg if it is at most 1.5× the scheduled time (Eish's suggestion, adopted by Al).
- **Trips are boat movements, not passengers,** from Aug 2025 trackers; the timetable is 2026. The observed switch is labelled as observed, never as a schedule.
- **Avas speeds are flat through the day** (ride times look modelled), so only the unserved share varies by hour. The chart shows the unserved share, not speed.

### What M2 gets from M4
- The **observed switch and map layer** make Eish's speedboat finding visible in the demo: with observed boats, Kaafu within 2 h (daytime median) goes from **0% to 21.5%**.

---

## 5. How M4 relates to M3 (Al)

### What M4 takes from M3
- **Results:** `access_results.csv`, `island_summary.csv`, `connections.csv` (shown as published at default settings).
- **Indicators:** `nsds_figures.csv` and `best_ferry_change.csv` (shown as published, with M3's definitions in the table).
- **Methods, adopted so recomputed scenarios match M3:**
  - **Island summary** (`indicators.island_summary`): daytime = departures 06:00–18:00; best and worst are over daytime departures; an unreachable median, best or worst is blank; last practical departure = latest step reaching the hospital before midnight.
  - **`observed_gap_min`:** quickest scheduled boat ride to Greater Malé minus M2's median of all tracked trips to Malé, Hulhumalé or Villimalé (not the airport), with at least 5 trips.
  - **Observed switch:** slow medians within `OBSERVED_MAX_SLOWDOWN` = 1.5× the schedule; a delayed boat can't leave a stop before it arrives; speedboat runs for island → Greater Malé pairs with at least `SPEEDBOAT_MIN_TRIPS_PER_DAY` = 5 fast trips a day, spaced `(last − first) × 60 / trips_per_day` minutes apart, to Jetty NO5. (The speedboat rule was agreed between Al and Saroof.)

### How we know the two engines agree
Run on M3's `connections.csv` and M1's `last_mile.csv`, the `Saroof` branch's own engine reproduces M3's base run **exactly** (on `m4-dashboard` the app uses M3's engine directly, which also reproduces it):
- **all 4,416 journeys** (island × 96 departures × 2 targets) within 0.15 min;
- **every `island_summary` column for all 23 islands** (daytime median, best, worst, last practical departure, boats a day, observed gap);
- the observed-switch headline figures in M3's handover (21.5% / 12.1% / 26.4%, the 54% peak at 12:15).

So "vs base" deltas on the dashboard compare like with like.

### What M3 gets from M4
- The **sliders** expose M3's scenarios live: ferry frequency, extra evening run, Thulusdhoo hospital, observed boat times, bus and taxi.
- The **Ferry changes** tab is M3's slide-6 table, readable on screen.

---

## 6. Decisions, and what we considered

### 6.1 Show M3's files at default settings; recompute otherwise
- **Considered:** always recomputing (hides the team's published outputs), or calling M3's own `run_scenario` (its parameters differ, and M3's code isn't on this branch).
- **Decided:** published files for the base view, recomputation for everything else, after proving the engines agree (section 5).

### 6.2 Take each file from its owner's branch
- `last_mile.csv` from M1's latest (`zayan`, 13:56, real Avas taxi times). M2's branch has an older copy (11:56); M3 pulled M1's.
- M3's results from `m3-network` (latest island summary, with M2's observed gap).
- **The pipeline never overwrites a teammate's file:** `python -m kaafu.pipeline` only fills in missing files; `--rebuild` regenerates everything.

### 6.3 Bug fixed: islands going grey
M1's `islands_layer` filters on `scenario == "base"` by default. A moved slider gives the run another name, so every island came back blank (grey). The app now passes the current scenario's name.

### 6.4 Bus routes on roads (OSRM)
- **Why:** M1's routes drew straight lines between stops, across water and buildings.
- **How:** each stop-to-stop leg is routed on OpenStreetMap roads by the public OSRM server, once; the result is committed, so the app never goes online. Only public bus-stop coordinates were sent.
- **Airport problem:** OSM tags the Velana domestic-terminal roads one-way, so leaving that stop OSRM sent buses on an 11 km loop via Hulhumalé. For any leg longer than 2 × straight + 500 m, the shorter of the forward path and the reverse path (flipped) is drawn.
- **Considered:** dropping the bad legs to straight lines (they crossed the runway), or bearings and wider snapping (didn't change OSRM's choice).
- **Cost:** on a few airport legs the line shows the road, not which side of a divided road the bus uses.

### 6.5 Visual system
- **Map colours are M1's:** blue ≤ 1 h, amber 1–2 h, red > 2 h, grey "no scheduled boat (Wed–Thu)". Blue, not green, because green and red look alike to colourblind viewers.
- **Brand teal (`#0E7C86`) is for controls only,** so it never reads as data.
- **Island circles** use M1's size (area ∝ population) scaled ×4 with a 4 px minimum; at M1's scale they were 2–3 px at the starting zoom.
- **Time axis** uses `utcFormat`; `timeFormat` shifted it by the viewer's timezone (5 h in Malé).
- **"Observed boat times" is a toggle,** not a two-option button, because Streamlit's test harness can't drive the latter.

### 6.6 Removed: all placeholder data
The invented timetable (`data/placeholder/`), `tests/make_placeholders.py`, the placeholder fallback in `load.py`, the 20 km/h taxi stand-in, the app's placeholder banners, and this branch's own `nsds_indicators.json`.

---

## 7. Doubts and things to note

### 7.1 The merge into `main`: done on `m4-dashboard`, ready to merge
- **The problem:** the `Saroof` branch had its own copies of the shared modules (`config.py`, `geo.py`, `lastmile.py`, `avas.py`, `followme.py`, `timetable.py`, `routing.py`, `indicators.py`, `scenarios.py`, `tests/test_routing.py`). Merging it conflicted in 16 files, and BUILD_PLAN's rule is one owner per file. Merging only the dashboard didn't conflict but crashed at once: the app relied on 11 pieces that exist only on `Saroof`.
- **The fix, on the `m4-dashboard` branch:**
  1. Built from the team's code: `main` + `m2-movement` + `m3-network` + `zayan`. These merge with no conflicts and M3's 14 tests pass.
  2. Added only M4-owned files: `app/`, `.streamlit/`, `src/kaafu/dashboard.py`, `tests/test_data.py`, `tests/test_dashboard.py`, `data/processed/bus_road_paths.json`, `docs/members/M4_lead_dashboard.md`, `README.md`, this handover, and `altair` in `requirements.txt`. **No file owned by M1, M2 or M3 is changed.**
  3. The app now imports only `kaafu.dashboard` and the team's modules, and its sliders run **M3's `run_scenario`**.
- **The 11 missing pieces, and what replaced each:**

  | # | Piece the app used on `Saroof` | On `m4-dashboard` |
  |---|---|---|
  | 1 | `kaafu.load`: `check_all`, `load_islands`, `load_origins`, `load_facilities`, `load_hdx`, `load_processed` | `dashboard.check_data` and the same five loaders (`load_hdx` pivots the team's long HDX sheet) |
  | 2 | `geo.terminals` | `geo.load_terminals` (M1's, already there) |
  | 3 | `scenarios.connections_for` | `dashboard.scenario_connections`: the scenario's boat legs, built with M3's own functions (`observed_durations`, `speedboat_departures`, `scale_route`, `extra_run`) in `run_scenario`'s order |
  | 4 | `timetable.legs` (the route list) | `dashboard.route_ids`, from M3's `connections.csv` |
  | 5 | `timetable.next_day` | `config.NEXT_DAY` (already in the team's config) |
  | 6 | `config.DAYS` | Dropped: M3's engine models one day (`config.DAY`, Wednesday), so the day picker became a note |
  | 7 | `config.TARGETS` | `dashboard.TARGETS` |
  | 8 | `indicators.at_departure` | `dashboard.at_departure` |
  | 9 | `indicators.share_within` | `dashboard.share_within` |
  | 10 | `indicators.through_day` | `dashboard.through_day` |
  | 11 | `indicators.hdx_table` | `dashboard.hdx_table` |

  Also in `dashboard.py`: `m3_params` (slider values → M3's `run_scenario` parameters: `ferry_factor` as `{route: factor}`, `extra_runs` as a list), `run` (published files at default settings, `run_scenario` otherwise), and `bus_routes_layer`, which wraps M1's layer with the road shapes so M1's `geo.py` stays untouched.
- **Checked on `m4-dashboard`:**
  - 26 tests pass (M3's 14, M4's 12), including the app run through the demo.
  - M3's engine reproduces its published results (4,416/4,416 journeys).
  - The adapter's default connections equal M3's `connections.csv`.
  - Observed times give 21.5% at 09:00, M3's figure.
  - The 09:00 map shows M1's 8 grey islands (8,847 people).
  - Rendered in a browser, the dashboard looks as on `Saroof`.
- **To merge:** `m4-dashboard` contains every team branch's latest commit, so merging it into `main` brings all four workstreams. If a member pushes again first, merge their branch into `m4-dashboard`, run `python -m pytest`, then merge into `main`.
- **`Saroof` stays as the record of the earlier work;** don't merge it.

### 7.2 Things the judges may ask about
- **The bus and taxi sliders change nothing.** The nearest hospital from every terminal is a 6.6–11.2 min walk, so all 3,200 reachable trips walk (M3, section 4.7). This is a finding: the boat is the whole problem. Consider hiding these sliders, or saying so in the demo.
- **The headline depends on the leave-home time.** At the default 08:00 it is 0%; at 07:00 it is 30.8% (Kaafu), because the morning boats have just gone. Pick the demo time on purpose (section 9).
- **"Nearest hospital" includes ADK, which is private.** IGMH would be slower. M3 asks whether to add a public-hospitals-only target.
- **Speedboats are modelled, not scheduled:** 2025 trackers spread evenly over the hours seen. Some may be private or resort boats.
- **Maafushi's speedboats mostly go to the airport (Hulhulé)** and aren't modelled, so its observed time is probably pessimistic. Huraa (4.0 a day) and Guraidhoo (3.3) are just under the 5-a-day threshold. M3 asks whether to lower it to 3.
- **Blank daytime medians** ("unreachable today") are real: the scan covers Wednesday and Thursday, and some islands' next boat is at the weekend. At 12:00, 11 islands (11,813 people, 38%) have no scheduled boat to a Greater Malé hospital before the end of Thursday.

### 7.3 Smaller notes
- **The repo is public:** `docs/`, including the model PDF, is visible. No raw data or IMEIs are committed.
- **Not done yet:** the fresh-clone test and the 60-second backup video (BUILD_PLAN section 9, M4 step 6).

---

## 8. Numbers for the slides (checked against the committed data)

Wednesday CFN timetable, Jetty NO5 for Malé, nearest Greater Malé hospital unless stated. "With speedboats" = the observed switch (M2's 2025 boat tracks, M3's rules).

### 8.1 Headline: within 2 hours of a hospital
| | HDX car-only | Public ferries | With observed speedboats |
|---|---|---|---|
| Kaafu, daytime median | 77.4% | **0%** | **21.5%** |
| All 23 islands, Greater Malé hospital | — | 0% | 12.1% |
| All 23 islands, any hospital (HDX: whole Maldives 45.9%) | 45.9% | 14.3% | 26.4% |

### 8.2 It depends when you leave (Kaafu, Greater Malé hospital)
| Leave home at | Public ferries | With speedboats | People with no scheduled boat (Wed–Thu), all 23 |
|---|---|---|---|
| 07:00 | **30.8%** | — | 4,452 (2 islands) |
| 08:00 | 0% | 10.1% | 4,452 (2 islands, 14%) |
| 09:00 | 0% | 21.5% | **8,847 (8 islands, 28%)** |
| 12:00 | 0% | — | 11,813 (11 islands, 38%) |
| 12:15 | 0% | **53.8%** (the day's peak) | — |

### 8.3 What-if results (dashboard sliders, daytime median)
- **Double every ferry route** (×2): Kaafu within 2 h stays at **0%**. Frequency within the same hours doesn't fix it; the gaps are overnight.
- **Thulusdhoo hospital opens** (any hospital): Thulusdhoo goes from 23.9 h to 5 min at 09:00; any-hospital share within 2 h becomes **10.1% for Kaafu** and **20.0% for all 23** (from 0% and 14.3%).
- **Extra run on route 307 at 22:00:** Kaashidhoo and Gaafaru go from "unreachable today" to 13.9 h and 12.4 h daytime medians (M3's ranking: 13.2 h saved per person, 3,822 people).

### 8.4 Last mile and taxis
- Every terminal is a 6.6–11.2 min walk from a hospital; all 3,200 reachable trips walk.
- Taxis (M2, Avas Aug–Sep 2026): 7.7% of requests unserved overall; 18% at 07:00 and 16% at 18:00; two in three at the airport at 23:00.

---

## 9. Demo script (3 minutes) and checklist

1. **Headline** at 07:00: "HDX says 77.4% of Kaafu is within 2 hours of a hospital. With real boats leaving at 07:00: 30.8%." Move to **08:00**: it drops to **0%**. "Miss the morning boat and you wait a day."
2. **Map** at 09:00: 8 grey islands, 8,847 people with no scheduled boat until the weekend.
3. **Island panel:** the worst island is preselected; walk through wait / boat / last mile and the last practical departure.
4. **Observed boat times on:** Kaafu within 2 h goes to 21.5%; show the observed-trips layer. "People already use speedboats the timetable doesn't show."
5. **What if:** add an evening run on route 307 at 22:00, or open the Thulusdhoo hospital, and watch the cards and map change. Then the **Ferry changes** tab.

**Before presenting:**
- [ ] Fresh clone of `main` (after merging `m4-dashboard`) → `pip install -r requirements.txt` → `python -m pytest` (26 pass) → `streamlit run app/streamlit_app.py`.
- [ ] Headline shows numbers; worst island selectable; evening-run slider changes the numbers.
- [ ] Record the 60-second backup video of steps 1–5.
- [ ] `git grep -i imei` returns nothing; `git status` shows no raw files.

---

## 10. Suggested slide content (M4's slides)

**Slide 1, problem:**
- "Global car-only estimates say 77.4% of Kaafu and 46% of Maldivians live within 2 hours of a hospital. Islanders don't drive to hospital; they wait for a boat."
- Visual: the dashboard headline, 77.4% against 0%.

**Slide 2, question and users:**
- "From each of 23 islands (31,414 people), how long does it really take to reach a hospital, door to door, at any time of day? Which islands are worst served, and which ferry change helps most?"
- Users: **MTCC / Ministry of Transport** (where to add or retime ferries); **MBS** (two NSDS indicators with no base year).

**Slide 3, credits (add to the team's list):** route geometry by OSRM on © OpenStreetMap contributors (ODbL).

**Slide 7, limits (M4 items, plus M2's and M3's lists):**
- Wednesday timetable; other days recomputed, not cross-checked.
- Jetty NO5 assumed for Malé; straight-line walks; fixed 5/10-min access and transfer.
- Speedboats modelled from 2025 trackers; airport-bound speedboats not modelled.
- Nearest hospital may be private (ADK).
- FollowMe 2025, Avas 2026, timetable 2026.
- Out of scope: flights, charters, ambulance boats.

**Slide 8, roadmap:**
- All 20 atolls and all 7 days (full-week scan).
- A GTFS feed for CFN; live FollowMe for real-time speedboat availability.
- Public-hospital-only and ambulance-boat scenarios.
- The dashboard as a tool MTCC can rerun when timetables change.

---

## 11. Where everything is, and how to run it

| What | Where |
|---|---|
| Dashboard | `app/streamlit_app.py`, brand in `app/assets/`, theme in `.streamlit/config.toml` |
| Dashboard adapter (M4) | `src/kaafu/dashboard.py`: loaders, data checks, slider → M3 mapping, indicators at a chosen time, bus routes on roads |
| Tests (M4) | `tests/test_data.py`, `tests/test_dashboard.py` |
| Engine (team) | M3: `timetable.py`, `routing.py`, `indicators.py`, `scenarios.py`; M1: `geo.py`, `lastmile.py`; M2: `avas.py`, `followme.py` |
| Data | `data/sheets/` (team), `data/processed/` (M1, M2, M3, plus `bus_road_paths.json`) |
| Plan and data notes | `docs/BUILD_PLAN.md`, `docs/CLAUDE_HANDOVER.md`, `docs/members/M4_lead_dashboard.md`, model note PDF |

```bash
pip install -r requirements.txt
python -m pytest                          # 26 tests
streamlit run app/streamlit_app.py        # http://localhost:8501
git add -A && git commit -m "..." && git push origin m4-dashboard
```

**AI-assisted (for the README):** all M4 code was written with Claude Code: on `Saroof`, the scaffold and engine; on both branches, the dashboard and its brand, the OSRM road snapping, the checks against M3's outputs, `dashboard.py`, the tests, this handover and the README.
