# M1 handover: GIS (places, last mile, map layers, static maps)

**Owner:** Zayan (M1) · **Branch:** `zayan` · **Last updated:** 24 Oct 2026, after the real Avas taxi data and the static maps

This file says what M1 has built, how it connects to M2, M3 and M4, what we considered and decided, what is still uncertain, and what can go on the slides. Read it after `docs/CLAUDE_HANDOVER.md` and `docs/BUILD_PLAN.md`. Team: M1 Zayan (GIS), M2 Eish (movement), M3 Al (network), M4 Saroof (lead, dashboard).

## Status at a glance

| Step (docs/members/M1_gis.md) | Status |
|---|---|
| 1. `terminals.csv` | Done. 4 terminals, checked against the RTL bus stops |
| 2a. Island zones, circle fallback | Done, then replaced by 2b |
| 2b. Island zones from OSM outlines | Done. All 27 from OSM, none fell back to a circle; checked on satellite imagery |
| 3. `last_mile.csv` | Done, **with real Avas taxi data** (M2's `avas_hourly.csv`). All "done when" checks pass |
| 4. Map layers for the dashboard | Done. Six layer functions plus `example_deck()`; they work from a fresh clone |
| 5. Static maps | Done. Three PNGs in `docs/figures/` |
| Slides 3–4 | To do (content suggestions below) |

Everything is pushed to `origin/zayan`. Al has merged `zayan` into `m3-network`, and Eish's final files are on `zayan`.

## Outputs

| File | Rows | What it is | Used by |
|---|---|---|---|
| `data/processed/terminals.csv` | 4 | `terminal_id, name, island_key, lat, lon, bus_stop_code, walk_to_stop_min`: T_MALE_NORTH (Jetty NO5), T_MALE_WEST (Maafannu Ferry Terminal), T_HULHUMALE, T_VILLIMALE | M3 routing, M4 map |
| `data/processed/island_zones.geojson` | 27 | `island_key, source, geometry`. OSM island outline + 300 m, one per `islands.csv` row | M2 FollowMe stop detection |
| `data/processed/last_mile.csv` | 1,800 | `stop_id, facility_id, hour, mode, minutes, available, detail`. 4 terminals × 6 Greater Malé hospitals × 24 h × walk/bus/taxi, plus walk rows for the 3 atoll-hospital islands | M3 routing and the bus/taxi sliders |
| `data/processed/bus_routes.csv` | 195 | Greater Malé bus stops in route order (15 routes), for the bus map layer | M4 map |
| `docs/figures/map_access_wed_0900.png` | | Door-to-door time to a Greater Malé hospital, leaving Wed 09:00 | Slides, demo backup |
| `docs/figures/map_male_boat_days.png` | | Days a week with a direct boat to Malé, per island | Slides |
| `docs/figures/map_greater_male.png` | | Terminals, hospitals, walking times, Villimalé ferry | Method slide |

Code: `src/kaafu/geo.py` (terminals, zones, layers, static maps, `male_bound_days()`) and `src/kaafu/lastmile.py`. Run `python -m kaafu.geo` and `python -m kaafu.lastmile` to rebuild. Building needs `data/raw/` (not committed); the map layers only read committed files.

## What we did, what we considered, and why

### Terminals (Step 1)
- Coordinates are the RTL bus stop at each ferry terminal (`rtl_bus_stops.csv`). Each build checks that every `bus_stop_code` exists and matches to about 1 m, and that every `island_key` is in `islands.csv`.
- No `T_AIRPORT`: the ferry timetable never uses the airport.
- **Assumption (limits slide):** every CFN "Male'" stop is Jetty NO5 (`terminal_assumed = yes` in the timetable). This was decided before the build.

### Island zones (Step 2)
- **Considered:** circles around the `islands.csv` point (600 m, or 1,500 m for Malé, Hulhumalé, Hulhulé and Dhigurah) against real outlines. We shipped circles first so M2 wasn't blocked, then switched to OSM outlines.
- **Why outlines:** the circles cut off long islands. Hulhumalé's point is its ferry terminal at the south-west corner, so the circle missed northern Hulhumalé, and likewise Hulhulé (5.5 km) and Dhigurah (4.1 km).
- **Method:** one small Overpass query per island (`place=island|islet` within 1.5 km). Take the outline containing the island point (or the nearest one), buffer 300 m in UTM 43N (EPSG:32643), save in WGS84. Fall back to the circle if the buffered outline doesn't contain the point. Overpass replies are cached in `data/raw/osm/`.
- **Result:** all 27 from OSM, 83–872 ha. Every zone contains its island point, and all 4 terminals are inside their island's zone.
- **Overlaps:** only Hulhumalé–Hulhulé (98 ha), because the islands are joined by land. M2 gives a ping in both zones to the nearer island point. Malé touches neither Hulhulé nor Villimalé.
- **Checked by eye** on satellite imagery (geojson.io) for Malé, Hulhulé and Hulhumalé.
- **Technical note:** the first Overpass run failed with Windows error 10048 (out of local ports). Fixed by reusing one HTTP session.

### Last mile (Step 3)
One row per stop × hospital × hour × mode. Unavailable options are kept with `available = no` and the reason in `detail`. `minutes` = from stepping off the boat to the hospital door.

**Which links exist:** walking only within the same island. Bus and taxi only within the same road network: Malé, Hulhulé and Hulhumalé are bridged, Villimalé isn't. From T_VILLIMALE only Villimalé Hospital (H06) is reachable, by walk or the R13/R14 bus. H06 is unreachable by road from the other terminals, so routing reaches it by the Villimalé ferry. There are no taxis from T_VILLIMALE.

**Walk:** 5 min to leave the boat + straight-line metres ÷ 80 m/min. All 9 values match the M1 guide's table, e.g. Jetty NO5 → IGMH 1,443 m / 23 min, Maafannu → IGMH 129 m / 7 min, Hulhumalé terminal → Hulhumalé Hospital 598 m / 12 min. Atoll hospitals, harbour to door: Rasdhoo 7, Mahibadhoo 8, Felidhoo 7 min.

**Bus:**
- **All 15 routes are used, not just the 11 timed ones.** Only minibuses stop near Jetty NO5, so the timed routes alone left the busiest terminal without a bus.
- **Board and alight within `BUS_STOP_RADIUS_M` = 550 m.** The guide said 400 m. At 400 m no route linked Malé and Hulhumalé, because the cross-bridge routes stop 435 m (Maafannu Bus Terminal) and 535 m (Carnival) from the Malé terminals. **Decision:** Malé and Hulhumalé are separate islands joined by a bridge, so the bus matters there; we raised the radius to 550 m. The reason is in `config.py`.
- **Missing R1 stop added.** The official R1 route map shows R1 looping through West Park past *Dharumavantha Hospital (West Side)*, next to IGMH. Team Kandu's stop list cuts the loop off at Maafannu Bus Terminal OPP. We added that stop (code 120, coordinates from R11) as R1 order 19 in `lastmile.BUS_STOP_ADDITIONS`; the raw file is untouched. This gave Hulhumalé terminal → IGMH a bus (about 50 min). Four other loop stops on the map (Food Court, West Park, Dharumavantha Hospital east side, Ministry of National Planning) have no coordinates in any file and don't affect hospital trips.
- **Timing:**
  - Wait = `wait_min` from `bus_headways.csv` for that hour. It's written in `detail` so M3's bus slider can rescale it.
  - The bus is unavailable outside `first_min`–`last_min`. `last_min` can pass midnight (1470 = 00:30); hours after midnight are also checked as next-day minutes.
  - Ride time = the median timetabled gap on the same trip (`rtl_bus_departures.csv`) as far as times exist, then distance along the route at 12 km/h, marked "estimated". The estimate applies to minibuses and the added R1 stop: 122 of 324 available bus rows.
- **Routes that end up used:** R1, R2, R6, R10, R11, R12, R13, R14.
- **The bus never beats walking or a taxi on time.** It matters as a fallback when taxis are scarce (the taxi slider) and for trips across the bridge.

**Taxi:**
- **Formula:** 5 min exit + 5 min base wait + `expired_share` (zone, hour) × 10 min + drive.
- **Drive time:** the median Avas `time_sec` of completed rides from within 400 m of the terminal to within 400 m of the hospital, if there are at least 10 that hour; otherwise straight-line km × 1.4 ÷ the zone's `median_speed_kmh`.
- **Completed** means `ride_completed` + `payment_completed`. Expired requests also carry a `time_sec`, so they're excluded.
- **Avas has no rides under about 2 km,** so taxis inside Malé always use the fallback. Cross-bridge pairs use real medians (e.g. Jetty NO5 → Tree Top, 227–239 rides). 157 of 360 available taxi rows use real medians.
- **Placeholder, now replaced:** 20 km/h and 0.07 until M2's `avas_hourly.csv` arrived. Now 28.8 km/h in Malé and 32.2 in Hulhumalé (same-zone rides; see M2's notes for why), plus the real hourly unserved share.
- **Effect:** median −0.7 min. Rush hours show: Malé taxi waits are longest at 18:00 (24% of requests unserved), Hulhumalé's at 07:00–08:00 (23%).

### Map layers (Step 4)
In `geo.py`, each returns a DataFrame ready for pydeck, with a `tooltip` column:

| Function | pydeck layer | Rows |
|---|---|---|
| `islands_layer(access_results, dep_min, target, scenario="base")` | ScatterplotLayer: area ∝ population, colour = access band | 23 |
| `boat_links_layer(connections)` | LineLayer: width by boats a day (√ scale), first day only | 28 |
| `hospitals_layer()` / `terminals_layer()` | ScatterplotLayer | 9 / 4 |
| `bus_routes_layer()` | PathLayer (optional) | 15 |
| `observed_trips_layer()` | LineLayer (optional), M2's pairs with ≥ 5 trips | 194 (122 fast, 72 slow) |

- `example_deck(access_results, connections, dep_min, target, show_bus=False, show_observed=False)` returns the whole map. In Streamlit: `st.pydeck_chart(geo.example_deck(...))`.
- **Fresh clone:** the layers read only committed files (`terminals.csv`, `bus_routes.csv`, `facilities.csv`, …). Tested by hiding `data/raw/`; every layer still built.

**Colours (considered and changed from the plan):**
- **The plan said green / amber / red.** We ran the colour-vision validator: green vs red measured ΔE 4.1 for deuteranopes (about 1 in 12 men), so a ≤ 1 h island and a > 2 h island would look the same.
- **Now:** blue `#1f6fd1` (up to 1 hour), amber `#fab219` (1–2 h), red `#d03b3b` (over 2 h), grey `#8c8c88` (unreachable). Every pair is ≥ ΔE 10.1 under every colour-vision type. Each band also has a text label in the legend and tooltips, so colour never carries meaning alone.
- In code: `geo.ACCESS_BANDS` and `geo.UNREACHABLE`.

### Static maps (Step 5)
`geo.write_static_maps(dep_min=540)` (also run by `python -m kaafu.geo`) saves:
1. **`map_access_wed_0900.png`:** islands by access band, labelled with minutes. The subtitle carries the headline: 8 islands, 8,847 people (28%), have no scheduled boat that gets them to a hospital by Thursday night.
2. **`map_male_boat_days.png`:** days a week with a direct boat to Greater Malé, from `geo.male_bound_days()`. It uses a one-hue blue ordinal scale (validated).
3. **`map_greater_male.png`:** terminals, hospitals, walking times and the Villimalé ferry over the OSM outlines.

The maps are drawn from M3's latest `access_results.csv` (re-checked after the Avas update: no change). `write_static_maps(420)` draws a 07:00 version, which shows the blue and amber bands for a before/after pair.

## What each member needs to know

### Eish (M2)
- **Your stops use `island_zones.geojson` (OSM + 300 m).** If I change the zones, you rerun `python -m kaafu.followme --month`.
- **Two zone details you may see in the data:**
  - The Waterdrome (seaplane lagoon) is inside Hulhulé's zone, so seaplane-like tracks may make stops there. They should fail the 80 km/h filter.
  - Malé's long south-west pier sticks out past the zone edge; a boat moored at its very end can sit just outside. If Malé stops look under-counted, a bigger buffer for Malé alone is a one-line change.
- **`last_mile.csv` uses your `avas_hourly.csv` as is.** Zones `male` / `hulhumale` (no terminal is on Hulhulé, so `airport` is unused).
- **`observed_trips_layer()` reads your `observed_pairs.csv` directly** and drops pairs with `n_trips` < `OBSERVED_MIN_TRIPS`.

### Al (M3)
- **`last_mile.csv` contract:** filter `available == "yes"`, take the fastest mode per stop × hospital × hour, and add it to the boat arrival time at that stop.
- **H06 Villimalé Hospital is reachable only from T_VILLIMALE,** via the VILI ferry.
- **Why the Avas update changed none of your outputs:** taxis are the fastest last leg in 285 of 456 stop × hospital × hour slots, but mostly to the farther hospitals. Each terminal's nearest hospital is a short walk (Maafannu → IGMH 7 min, Jetty NO5 → ADK 11, Hulhumalé → Tree Top 11, Villimalé → H06 7), and taxis only tie with those walks. So "nearest hospital" results are walk-led and don't move with taxi times.
- **The bus `detail` text holds `wait X`,** which your bus slider rescales.
- **`geo.male_bound_days()`** gives days per week and departure times for each origin island's direct boats to Greater Malé (outbound runs excluded). It may be useful for the NSDS "population with scheduled ferry services" figure.
- **Blank `total_min` / `day_median_min`:** we agree with your note. They're expected, caused by the Wed + Thu scan, and a full-week scan goes on the roadmap. My map label is "no scheduled boat (Wed-Thu)"; your note says "unreachable today". **Saroof should pick one wording** for the dashboard, maps and slides (see doubts).

### Saroof (M4)
- **Map:** `geo.example_deck(...)`, or build your own from the six layer functions. Use `geo.ACCESS_BANDS` / `geo.UNREACHABLE` for the legend, so the colours and labels match the static maps.
- **`config.py`:** M1 changed `BUS_STOP_RADIUS_M` to 550 (comment explains why). M1 uses `TAXI_ZONE`, `ROAD_NETWORK`, `GM_HOSPITALS`, `ATOLL_HOSPITALS`, the `ZONE_*` and `OVERPASS_*` settings, `TAXI_*` and `MINIBUS_SPEED_KMH`; tell Zayan before renaming any of them.
- **README:** data credits (below), the AI-assisted list (below), and `python -m kaafu.geo` / `python -m kaafu.lastmile` in the rebuild steps (both need `data/raw/`).
- **Backup:** if the live demo fails, use the three PNGs in `docs/figures/`.

## Doubts and open questions

1. **Wording for unreachable islands.** "No scheduled boat (Wed-Thu)" (M1) vs "unreachable today" (M3 note, BUILD_PLAN). "Today" isn't quite right: the scan includes Thursday, and some of these islands had a boat early on Wednesday. Suggest: **"no scheduled boat until the weekend"** on slides, and the shorter M1 label on the map.
2. **The 550 m bus radius** is our judgement, not a published standard. A 6–7 min walk to the stop is included in the bus time, so it doesn't flatter the bus.
3. **R3 and R7 probably loop like R1** (both end at "West Park"), but we only had R1's map. Adding their loop stops would add bus options, but no faster ones.
4. **Taxi speed inside Malé** (28.8 km/h) is high for a congested 1–2 km hop. It comes from only 360 same-zone Malé rides; for 15 of 24 hours Malé uses its all-day median. Malé taxi times may be a few minutes optimistic. They rarely beat walking anyway.
5. **Gulhi's "Island Clinic"** (C07) is still assumed to be the government health centre (low impact; only the "30 min to any health facility" indicator).
6. **About 22 island points are island centres,** not harbours (100–300 m off). The 300 m zone buffer covers this; the walk-to-hospital times on those islands may be a few minutes off.
7. **Senahiya (H03)** is included (military hospital, public 24/7 emergency department, Aasandha). It's never the nearest hospital from any terminal, so it doesn't change the results.

## Limits (for slide 7)

- Walks are straight lines at 80 m/min plus 5 min to leave the boat. Real walks are a little longer.
- **Bus:**
  - minibus ride times are estimated at 12 km/h;
  - the wait is half the headway;
  - the stop radius is 550 m;
  - one stop was added to R1 from the route map;
  - R3–R6 times are adjusted from Ramadan 2024 (data pack).
- **Taxi:**
  - Avas covers Aug–Sep 2026 and has no rides under 2 km, so taxis inside Malé use the 1.4 × straight-line distance fallback;
  - there is no pickup-wait field, so the wait is assumed: 5 min + unserved share × 10.
- Only one bus route per trip (no bus-to-bus transfers).
- Island zones are OSM outlines + 300 m; island points are often island centres, not harbours.
- Malé's ferry jetty is assumed to be Jetty NO5 for every CFN route.

## Findings and talking points (numbers checked against the committed files)

**Boats to Malé per week** (`geo.male_bound_days()`, direct boats only, outbound runs excluded):

| Days a week | Islands | People |
|---|---|---|
| 6 (every day but Friday) | 7: Dhiffushi, Thulusdhoo, Huraa, Himmafushi, Gulhi, Maafushi, Guraidhoo | 13,927 |
| 3 | 7: Kaashidhoo, Gaafaru (Sat Mon Wed); Felidhoo, Fulidhoo, Keyodhoo, Thinadhoo (Sat Mon Wed); Mahibadhoo (Sun Tue Thu) | 8,321 |
| 2 | 3: Rasdhoo, Thoddoo, Ukulhas (Sun Wed) | 4,490 |
| 0, must change boats | 6: Mathiveri, Bodufolhudhoo, Dhangethi, Dhigurah, Hangnaameedhoo, Omadhoo | 4,676 |

16 of 23 islands (17,487 people) have a boat to Malé on 3 days a week or fewer, usually a single early-morning run. No public ferry runs on Fridays.

**Leaving home Wednesday 09:00, nearest Greater Malé hospital:**
- 8 islands, 8,847 people (28%), have no scheduled boat that gets them there by Thursday night: Kaashidhoo, Gaafaru, Thoddoo, Mathiveri, Bodufolhudhoo, Felidhoo, Keyodhoo, Thinadhoo.
- The other 15 (22,567 people) take over 2 hours. Nobody is within 2 hours, because the morning boats have gone.

**Leaving 07:00:** 3 islands (5,467 people) reach a Greater Malé hospital in 1–2 hours, 18 take over 2 hours, and 2 have no boat. For any hospital, the 3 atoll-hospital islands (4,482 people) are within 1 hour.

**Thoddoo (1,924 people):** 96% of daytime departure times can't reach a hospital within the Wed–Thu window. Its boat to Malé runs Sunday and Wednesday at 06:30.

**Talking points:**
1. "If you fall ill on a Wednesday after the morning boat has left, 8,847 people on 8 islands, 28% of everyone we studied, have no scheduled boat to a Malé hospital until the weekend."
2. "Where you live decides how often you can reach a hospital: inner Kaafu has a boat to Malé six days a week, Vaavu and outer Kaafu three, and six islands have no direct boat at all."
3. "Global car-only estimates miss this. HDX says 77.4% of Kaafu is within 2 hours of a hospital, but it assumes you can leave when you like. Here the timetable decides when you can leave." (See M3's `hdx_comparison.csv` for our matching figures.)
4. "It's fixable. The boats and routes exist; the gaps are in which days they run." This leads into M3's `best_ferry_change.csv`.
5. **Honest framing:** this is *scheduled public boats*, our scope. Ambulance boats, charters and private speedboats exist; FollowMe shows heavy speedboat traffic near Malé (e.g. Hulhumalé–Malé fast boats: 32 trips a day, median 6 min).

**Last mile (method slide):** a ferry passenger in Greater Malé is 7–12 min from the nearest hospital on foot: Maafannu → IGMH 7, Jetty NO5 → ADK 11, Hulhumalé → Tree Top 11, Villimalé → Villimalé Hospital 7. The boat timetable, not the last mile, decides door-to-door times.

## Suggested content for slides 3–4 (M1's slides)

**Slide 3, Data and credits:**
- Sources: MTCC/RTL CFN ferry schedule (Zone 3, effective 1 Aug 2026) and Greater Malé bus timetables; Census 2022 (MBS Statistical Yearbook 2026, table 3.3, via Team Kandu); Team Kandu shared datasets (RTL bus stops and departures); OpenStreetMap (island outlines, hospitals); FollowMe boat GPS (Aug 2025) and Avas taxi requests (Aug–Sep 2026) from the organisers; HDX accessibility indicators.
- Visual: `map_male_boat_days.png`.
- Credit line: © OpenStreetMap contributors (ODbL); MBS via Team Kandu; Team Kandu shared datasets; MTCC/RTL timetables; FollowMe and Avas data from the organisers; HDX.

**Slide 4, Method:**
- Pipeline: timetable → connections → earliest arrival (M3) + last mile by walk/bus/taxi (M1) → door-to-door time; pings → island zones (M1) → stops → trips (M2).
- Visuals: `map_greater_male.png` (last mile) and `map_access_wed_0900.png` (result).
- One line on zones: "Island zones are OpenStreetMap outlines plus 300 m; a boat is 'at an island' when it stops inside one."

## How to rerun

```powershell
.\.venv\Scripts\Activate.ps1          # or call .\.venv\Scripts\python.exe directly
python -m kaafu.geo                   # terminals, bus_routes, static maps, island zones (needs data/raw/, OSM cache)
python -m kaafu.lastmile              # last_mile.csv (needs data/raw/ for buses and Avas rides)
pytest -q
```
- Rerun `lastmile` if `avas_hourly.csv`, the bus sheets or `config.py` change, then tell Al.
- Rerun `geo` after Al pushes new `access_results.csv`, to redraw the maps.

## AI-assisted (for the README)

All M1 code was written with Claude Code, reviewed and directed by Zayan:
- `src/kaafu/geo.py`: terminals and checks; OSM island zones (Overpass, polygon building, buffering, fallback, caching); pydeck map layers and `example_deck()`; static maps; `male_bound_days()`.
- `src/kaafu/lastmile.py`: walk, bus (stop matching, headways, service hours, ride times, the R1 stop addition) and taxi (Avas point-to-point medians, fallback) options, with the "done when" checks.
- Analysis run with Claude Code:
  - the facilities sheet cross-check;
  - the bus-radius and R1 investigations;
  - colour-vision validation of the map palettes;
  - the per-island boat-days table;
  - the fresh-clone test.
- Setup: repo layout, `.gitignore`, `config.py` (first version), `pyproject.toml`.

## Corrections made along the way (so nobody repeats them)

- **An early day-by-day boat table counted outbound boats** (leaving Malé) as Malé-bound and wrongly showed Thursday service for Gaafaru, Felidhoo and Thinadhoo. Fixed: `male_bound_days()` counts only departures whose trip reaches Greater Malé later.
- **An early explanation said taxis are never the fastest last leg.** Wrong: they often are, but only to hospitals that are never the nearest (see the Al section above).
- **The first `facilities.txt` copied into `docs/` was the older version.** The current one marks the H01, H03, H07 and H08 questions as DONE.
