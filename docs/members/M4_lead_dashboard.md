# Member 4: Lead and dashboard (Zayan)

**Difficulty: 3 of 4.** None of the code is hard on its own. What makes this role demanding is that you set up everything at H0 that the others build on, keep merges clean, turn three other people's outputs into one working app by H3, and own the submission and slides. Stay on schedule rather than polishing.

You own the repo, `src/kaafu/config.py`, `src/kaafu/load.py`, `tests/test_data.py`, `app/streamlit_app.py`, `README.md`, and the final submission.

Read first: `docs/CLAUDE_HANDOVER.md`, then `docs/BUILD_PLAN.md` sections 1–5, 6.7, 6.8, 7 (M4), 9, 10, 12.

---

## Timeline

| When | What |
|---|---|
| **H0–0:30** | **Step 1: repo setup.** Everyone must be able to pull by 0:30. |
| 0:30–3:00 | **Step 2: `config.py`, `load.py`, data tests.** **Step 3: dashboard shell on placeholders.** |
| **H3** | **Step 4: merge #1, swap in real results. Minimum demo runs.** |
| 3:00–5:00 | **Step 5: island panel, sliders, charts, README.** |
| **H5** | Merge #2. |
| 5:00–6:30 | **Step 6: fresh-clone test, backup video.** Features freeze at H6. |
| 6:30–8:00 | **Step 7: slides 1, 2, 7, 8; submit; rehearse twice.** |

---

## Step 1: repo setup (H0–0:30)

On your laptop (Python 3.11+ and Git installed):

```bash
mkdir kaafu-connect && cd kaafu-connect && git init
mkdir -p docs/members data/sheets data/raw data/processed src/kaafu app tests
# copy in:
#   docs/            CLAUDE_HANDOVER.md, BUILD_PLAN.md, every *.txt from data_pack/sheets,
#                    docs/members/M1..M4 files
#   data/sheets/     every CSV from data_pack/sheets
#   data/raw/        followme_kaafu_aug2025.parquet, followme_check.txt,
#                    avas_rides_aug_sep_2026.csv, car_fare_matrix.csv, the Team Kandu rtl_* files
touch src/kaafu/__init__.py
```

`CLAUDE.md` (repo root, one line):
```
Read docs/CLAUDE_HANDOVER.md, then docs/BUILD_PLAN.md, then your own file in docs/members/.
```

`.gitignore`:
```
data/raw/
*.duckdb
*.exe
__pycache__/
.venv/
```

`requirements.txt`:
```
pandas
geopandas
shapely
duckdb
pyarrow
streamlit
pydeck
pytest
openpyxl
requests
```

Then: commit, push to GitHub (private until submission if the rules allow), create branches `m1-gis`, `m2-movement`, `m3-network`, `m4-dashboard`, add the others as collaborators. **Share `data/raw/` by USB or a shared drive, never Git.** Everyone runs `pip install -r requirements.txt` and `python -c "import geopandas"`.

---

## Step 2: `config.py`, `load.py`, `tests/test_data.py` (0:30–1:15)

`config.py`: paths (`SHEETS`, `RAW`, `PROCESSED`) plus every parameter in BUILD_PLAN section 5, with these values:

| Name | Value |
|---|---|
| WALK_M_PER_MIN | 80 |
| ACCESS_MIN | 5 |
| BOAT_TRANSFER_MIN | 10 |
| TERMINAL_EXIT_MIN | 5 |
| TAXI_BASE_WAIT_MIN, TAXI_RETRY_MIN, TAXI_DETOUR | 5, 10, 1.4 |
| STOP_SPEED_KMH, STOP_MIN, ZONE_BUFFER_M | 2, 10, 300 |
| OBSERVED_MIN_TRIPS | 5 |
| STEP_MIN | 15 |
| THRESHOLDS_MIN | [30, 60, 90, 120, 240] |
| INCLUDE_SENAHIYA | True |
| DAY, NEXT_DAY | "Wed", "Thu" |
| FOLLOWME_UTC_OFFSET_H | 5 |
| GREATER_MALE | ["K.Malé", "K.Hulhumalé", "K.Villimalé", "K.Hulhulé"] |
| BUS_ROUTES | all 15 (M1 found that only the minibuses serve Jetty NO5) |

Push `config.py` first (by ~0:40) because everyone imports it.

`load.py`: one function per sheet (`load_islands()`, `load_facilities()`, `load_ferry()`, `load_bus_hours()`, `load_bus_headways()`, `load_hdx()`), each reading with `encoding="utf-8-sig"`, plus `check_all()` running the checks below and raising a clear error.

`tests/test_data.py` (these all passed on the data pack last night, so they should pass now):
- every `from`/`to` in `ferry_timetable.csv` and every `island_key` in `facilities.csv` is in `island_names.csv` and `islands.csv`;
- origin population: Kaafu 17,749, inbound 13,665, total 31,414;
- `dep_min < arr_min` for every ferry row;
- no ferry leg faster than 80 km/h straight-line (fastest is about 25 km/h);
- every Greater Malé ferry stop has a terminal;
- once M3's `connections.csv` and M1's `terminals.csv` exist: every stop is in `islands.csv` or `terminals.csv`.

---

## Step 3: dashboard shell on placeholders (1:15–3:00)

Make a tiny `tests/make_placeholders.py` that writes fake `access_results.csv` and `island_summary.csv` with the exact columns from BUILD_PLAN section 4 (random minutes for the 23 islands × 96 steps × 2 targets). Build against those; the real files drop in at H3 with no code change.

`app/streamlit_app.py` layout:

**Sidebar**
- Departure time: `st.select_slider` over 00:00–23:45 in 15-min steps (default 08:00).
- Target: "Nearest Greater Malé hospital" / "Any hospital".
- Day: Wednesday (default); others optional.
- Boat times: scheduled / observed.
- Scenario sliders (wired in Step 5).

**Headline** (BUILD_PLAN 6.8):
> HDX's car-only estimate: **77.4%** of Kaafu within 2 hours of a hospital. With real boats leaving at **08:00**: **Y%**.

Y = population-weighted share of the 9 Kaafu origins with `total_min ≤ 120` at that departure. Below it, a small table: 30/60/90/120/240 min, our Kaafu %, our all-23 %, HDX Kaafu % (75.8, 76.8, 77.3, 77.4, n/a), HDX Maldives % (45.4, 45.8, 45.9, 45.9, n/a), from `hdx_benchmark.csv`.

**Map** (pydeck, default Carto basemap, no token): `ScatterplotLayer` for islands (M1's `islands_layer`), `LineLayer`/`ArcLayer` for boat links, small icons or dots for hospitals and terminals. Initial view: lat 4.2, lon 73.3, zoom 8.

**Through the day**: line chart of the share within 2 h vs departure time (`st.line_chart` or Altair, both come with Streamlit), and the Avas unserved share by hour.

Use `@st.cache_data` on every loader and on scenario runs.

---

## Step 4: H3 merge, minimum demo

1. Merge `m3-network` (results), `m1-gis` (terminals, last mile), `m2-movement` (Avas) into `main`. Resolve conflicts only in files you own; ask owners for theirs.
2. Point the app at `data/processed/` real files. Run `pytest` and `streamlit run app/streamlit_app.py`.
3. **Minimum demo = headline with numbers + coloured map.** If that works, tell everyone to pull `main`.
4. If routing is broken: use M3's fallback (direct boats only, walk-only last mile; BUILD_PLAN section 11).

---

## Step 5: panel, sliders, charts, README (H3–H5)

**Island panel** (select an island on a dropdown; clicking on pydeck maps is unreliable):
- stacked horizontal bar: wait / boat / transfer / last mile (from `access_results.csv` columns);
- boats per day, population, last practical departure, scheduled vs observed time (from `island_summary.csv` and M2's `observed_pairs.csv`).

**Sliders** call M3's `scenarios.py`. Agree the signature at H3, e.g. `run_scenario(params: dict) -> (access_results, island_summary)`, where params carries `ferry_factor`, `extra_run`, `bus_factor`, `taxi_availability`, `thulusdhoo_hospital`, `observed`, `day`. Cache by params.

**README.md** sections: Problem; What it shows; Setup (`pip install -r requirements.txt`, where to put `data/raw/`, `streamlit run app/streamlit_app.py`); Data sources and credits with access dates (BUILD_PLAN 10 list + MTCC/RTL timetables + HDX); Method (one paragraph); Limits; **AI-assisted parts** (collect each member's list: the data-pack scripts and DuckDB queries from prep, plus today's Claude Code sessions).

---

## Step 6: freeze and test (H5–H6:30)

1. Merge #2 at H5. Nothing new after H6, only fixes.
2. Fresh clone into a new folder, copy `data/raw/`, `pip install -r requirements.txt`, `pytest`, `streamlit run …`. Check: headline shows numbers; pick the worst island; move the evening-run slider and see the number change.
3. Record a 60-second screen video of exactly that (backup if the live demo fails).
4. `git grep -i imei` and check `git status` for raw files before the final push.

## Step 7: slides and submission (H6:30–8:00)

Your slides: 1 (problem: HDX 46% / 77.4% vs island reality), 2 (question and users: 23 islands, 31,414 people, MTCC and MBS), 7 (limits: BUILD_PLAN 10 list plus Wednesday-only, jetty assumed, UTC/knots, Ramadan bus tables, Avas ≥2 km), 8 (roadmap). Collect 3–4 from M1, 4–5 from M2, 5–6 from M3. Export PDF, submit the declaration, run through BUILD_PLAN section 12, rehearse twice with everyone speaking.

## Start your Claude session with

> We're building Kaafu Connect today. I'm member 4, lead and dashboard. Read docs/CLAUDE_HANDOVER.md, docs/BUILD_PLAN.md (sections 1–5, 6.7, 6.8, 9, 10, 12) and docs/members/M4_lead_dashboard.md. Create or edit only config.py, load.py, tests/test_data.py, tests/make_placeholders.py, app/streamlit_app.py and README.md. Do Step 2 first (config.py, then load.py and the tests), and stop after config.py so I can push it. Keep a list of what you wrote for the README's AI-assisted section.
