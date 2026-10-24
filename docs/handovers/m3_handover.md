# M3 handover: network and indicators

**Owner:** Al (M3) · **Branch:** `m3-network` · **Written:** 24 Oct 2026, after Step 5

This is the full account of M3's work, for:
- a Claude session that picks it up, or answers questions about it;
- whoever turns it into slides.

It says what was built, how it connects to M1 (Zayan) and M2 (Eish), what we decided and why, and what we're unsure about. The day-to-day status file is [`m3_claude.md`](m3_claude.md); this one is the long-form version. Team: M1 Zayan (GIS), M2 Eish (movement), M3 Al (network), M4 Saroof (lead, dashboard).

---

## 1. The question M3 answers

**From each of 23 islands, how long does it really take to reach a hospital, door to door, at any time of day? Which islands are worst served, and which ferry change would help most?**

- **Islands:** the 9 inhabited Kaafu islands (17,749 people) and 14 islands in Alif Alif (AA), Alif Dhaalu (ADh) and Vaavu (V) with boats to Malé (13,665 people), 31,414 in total.
- **Targets:**
  - `gm_hospital`: the nearest Greater Malé hospital, H01–H06. This is the main measure.
  - `any_hospital`: also the atoll hospitals at Rasdhoo, Mahibadhoo and Felidhoo (H07–H09). This is for comparison with HDX.
- **Benchmark:** HDX's car-only estimate says 77.4% of Kaafu and 45.9% of the Maldives live within 2 h of a hospital. It ignores boats, which is the gap this project exposes.

---

## 2. What M3 built (the pipeline)

```
ferry_timetable.csv ─► timetable.py ─► connections.csv
                                           │
          terminals.csv, last_mile.csv ◄───┤  (M1)
          observed_pairs/trips.csv ◄───────┤  (M2)
                                           ▼
                       routing.py: connection scan, every island × 96 departures × 2 targets
                                           ▼
     indicators.py ─► access_results.csv, island_summary.csv, population_within.csv,
                      hdx_comparison.csv, nsds_figures.csv
     scenarios.py  ─► run_scenario(params) for the dashboard sliders, best_ferry_change.csv
     m3_figures.py ─► docs/figures/m3_*.png, m3_slide_numbers.md
```

| Step | File | What it does |
|---|---|---|
| 1 | `src/kaafu/timetable.py` | Turns the ferry sheet into one row per boat leg (`connections.csv`). It keeps **Wednesday's** legs and adds **Thursday's own legs** at +1440 min, so a late-evening start finds the next morning's boat. Greater Malé stops become terminal IDs (`T_MALE_NORTH`, `T_HULHUMALE`, `T_MALE_WEST`, `T_VILLIMALE`). 600 rows: 50 CFN + 250 Villimalé ferry legs per day. |
| 2 | `src/kaafu/routing.py` | **Connection scan** (earliest arrival): walk through every boat leg in time order and keep the earliest time each island or terminal can be reached. Rules: 5 min from home to the harbour (`ACCESS_MIN`); 10 min to change boats (`BOAT_TRANSFER_MIN`); staying on the same boat costs nothing. Then add M1's last mile from the terminal to the hospital, and split the trip into wait, boat, transfer and last-mile minutes. |
| 3 | `src/kaafu/indicators.py` | Runs every island × every 15-min departure (96 a day) × both targets: 4,416 rows in `access_results.csv`. Summarises per island in `island_summary.csv`: daytime median (departures 06:00–18:00), best and worst times, last practical departure, boats a day, `observed_gap_min`. Also the population shares (averaged over daytime departures, see 5.8), the HDX comparison and the NSDS figures. |
| 4 | `src/kaafu/scenarios.py` | `run_scenario(params)` for the dashboard sliders: ferry frequency, extra evening run, Thulusdhoo hospital, observed boat times (+ speedboats), bus frequency, taxi availability. Also the best-ferry-change ranking. |
| 5 | `src/kaafu/m3_figures.py` | Six slide charts and `m3_slide_numbers.md`. |
| tests | `tests/test_routing.py` | 14 toy tests: direct boat; next morning; transfer time; staying on board; leaving later never arrives earlier; breakdown adds up; own hospital; re-spacing; extra run; bus/taxi adjustment; observed durations; speedboats. |

**Checks passed:**
- Matches the reference table in `M3_network.md` for all 23 islands. Example: AA.Mathiveri changes at Ukulhas with exactly the 10-minute transfer; route 301 arrives 09:35, route 303 leaves 09:45.
- Every island has a result for every departure, or a stated reason it's unreachable.
- Leaving later never arrives earlier.
- Jetty NO5 → IGMH on foot is 23 min, within the 20–25 the plan expects.
- Hulhumalé terminal → Hulhumalé Hospital is 12.5 min, under the plan's 15.

**Run order** (repo root; ~2 min in total):
```bash
PYTHONPATH=src python -m kaafu.timetable
PYTHONPATH=src python -m kaafu.indicators
PYTHONPATH=src python -m kaafu.scenarios    # best_ferry_change.csv, 30-90 s
PYTHONPATH=src python -m kaafu.m3_figures   # charts + slide numbers
python -m pytest
```

---

## 3. How M3 relates to M1 (Zayan) and M2 (Eish)

### What M3 takes in

| From | File | How M3 uses it | Effect on results |
|---|---|---|---|
| M1 | `terminals.csv` | Terminal coordinates and which island each terminal is on. They map terminal IDs to island keys when matching M2's pairs. | None: same coordinates as my early stand-in. |
| M1 | `last_mile.csv` (walk, bus, taxi per terminal × hospital × hour; real Avas taxi times since 13:56) | Fastest available mode per hour, added after the boat. The bus and taxi sliders read the `wait <n>` text in its `detail` column. | **None: every result uses walking.** See 5.4. |
| M1 | `config.py` (shared) | Every path and parameter. M3 added `OBSERVED_MAX_SLOWDOWN` and `SPEEDBOAT_MIN_TRIPS_PER_DAY` to its M3 section. | — |
| M2 | `observed_pairs.csv` (FollowMe, Aug 2025, per island pair and speed class) | `slow` medians re-time ferry legs; busy `fast` pairs become synthetic speedboat departures. | Large, when the observed switch is on. See 4.3. |
| M2 | `observed_trips.csv` | Median of all tracked trips from each island to Greater Malé, for `observed_gap_min` and the scheduled-against-observed chart. | Descriptive only. |
| M2 → M1 | `avas_hourly.csv` | Reaches M3 only through M1's taxi rows in `last_mile.csv`. | None (see above). |

### What M3 gives back

| To | File | Used for |
|---|---|---|
| M1 | `connections.csv` | Zayan's boat-link map layer (`geo.py`). |
| M1 | `access_results.csv` (base scenario) | Zayan's island colours on the access map (`geo.islands_layer`, `map_access_wed_0900.png`). **That map shows public ferries only.** |
| M4 | `access_results.csv`, `island_summary.csv`, `run_scenario()` | Dashboard headline, map, island panel and sliders. |
| Slides | `docs/figures/m3_*`, `m3_slide_numbers.md` | Slides 5–6. |

### Where M2's and M3's stories meet (slide 5)

- **Eish shows** what people ride: 74–88% of trips from the islands near Malé are speedboats. Maafushi → Malé is 84–90 min by ferry against 41 by speedboat.
- **M3 shows** what that means for reaching a hospital. With public ferries alone, 2.4% of Kaafu is within 2 h; with the observed speedboats, 22.6%.
- **The two numbers are compatible, not competing.** Eish's 84 min is the slow-boat median for one leg; M3's `observed_gap_min` uses the median of *all* boats, ferries and speedboats together (Maafushi: 90 scheduled against 48 observed).
- **Eish's validation backs M3's re-timing.** For the 28 CFN legs with enough slow trips, observed and scheduled differ by a median of 5 min, which is why re-timing the ferries changes little.

---

## 4. Results (slide content)

Every number assumes the Wednesday CFN timetable and the Malé jetty as Jetty NO5. "Within 2 h" shares are averaged over every daytime departure (06:00–18:00): the chance that someone who needs a hospital at a random daytime moment gets there in time (5.8). Per-island times are the daytime median. "With speedboats" means observed FollowMe boat movements from Aug 2025, not a published schedule. All tables are regenerated in `docs/figures/m3_slide_numbers.md`.

### 4.1 Headline: within 2 h of a hospital

| | HDX car-only | Public ferries only | With observed speedboats |
|---|---|---|---|
| Kaafu (nearest hospital) | **77.4%** | **2.4%** | **22.6%** |
| All 23 islands, any hospital (HDX: whole Maldives) | 45.9% | 17.7% | 30.1% |
| All 23 islands, Greater Malé hospital | — | 1.4% | 13.7% |

- **Ferries only, all 23, any hospital:** 14.3 of the 17.7 points are the three islands with their own atoll hospital (Rasdhoo, Mahibadhoo, Felidhoo; 4,482 people).
- **Where the 2.4% comes from:** short windows around the morning boats. Himmafushi 07:00–07:45, Huraa 07:00–07:30, Gulhi 07:30–07:45, Thulusdhoo 07:00, Maafushi 12:30. Need a hospital at any other daytime moment and the boat has gone.
- **Kaafu, either target:** both give the same number, because no Kaafu island has an atoll hospital.
- **By time of day** (Kaafu, Greater Malé hospital):
  - Ferries only: the 2-hour share peaks at **31% for someone leaving at 07:00** and is 0% for most of the day.
  - With speedboats: it peaks at **54% leaving at 12:15** and stays around 10–30% from 03:00 to 22:00.

### 4.2 Worst served

- **Last practical departure** (latest time to leave home and still reach a Greater Malé hospital before midnight, ferries only):
  - Alif Dhaalu: **none** on Wednesday.
  - Thoddoo and Dhiffushi: 06:15.
  - Kaashidhoo and Guraidhoo: 06:45.
  - Most others: 07:00–10:45.
  - Maafushi: 12:30.
- **With speedboats,** the last practical departure moves to 22:15 (Thulusdhoo), 22:00 (Himmafushi), 21:30 (Thoddoo), 16:45 (Dhiffushi) and 15:30 (Huraa).
- **Daytime median, ferries only:** most Kaafu islands take 19–20 h, because miss the morning boat and you wait until tomorrow. Alif Dhaalu takes 27.5 h. **11 islands are "unreachable today"** (AA, V, Kaashidhoo, Gaafaru): most daytime departures find no hospital before the end of Thursday. See 5.2.
- **With speedboats:** Thulusdhoo 19.6 h → 1.4 h, Himmafushi 18.9 → 1.6, Dhiffushi 20.4 → 2.2, Thoddoo unreachable → 3.0, Huraa 19.1 → 6.0 (via Himmafushi).

### 4.3 What the observed data changes

| | Effect |
|---|---|
| Re-timed ferries only (Eish's slow medians on 55 CFN legs) | Island times move −6 to +37 min. **Kaafu within 2 h: 2.4% → 2.8%.** |
| + synthetic speedboats (Thulusdhoo 15 a day, Himmafushi 8, Dhiffushi 8, Thoddoo 6) | Kaafu within 2 h: 2.4% → **22.6%**. |

**The lesson for the slides:** the problem isn't how slow the ferry is but **how rarely it runs**. One or two boats a day means a missed boat costs a day.

### 4.4 Scheduled against observed boat time to Greater Malé

| Island | Quickest scheduled ferry | Observed median (all tracked boats) |
|---|---|---|
| AA.Thoddoo | 460 min | 73 min |
| V.Keyodhoo | 345 min | 108 min |
| K.Kaashidhoo | 280 min | 115 min |
| K.Maafushi | 90 min | 48 min |
| K.Huraa | 60 min | 24 min |

The full table is in `m3_slide_numbers.md`. Thoddoo's 460 min is route 303 looping via Rasdhoo and Ukulhas.

### 4.5 Best ferry change (slide 6)

One extra evening run, at 18:00, 20:00 or 22:00, on each CFN route, public ferries only:

| Run | People helped | Average saved per person | Islands |
|---|---|---|---|
| Route 307 at 22:00 | 3,822 | 13.2 h | Kaashidhoo, Gaafaru |
| Route 303 at 20:00 | 4,490 | 11.2 h | Rasdhoo, Thoddoo, Ukulhas |
| Route 308 at 18:00 | 6,737 | 6.0 h | Dhiffushi, Himmafushi, Huraa, Thulusdhoo |
| Route 306 at 20:00 | 7,366 | 5.2 h | Gulhi, Maafushi, the 4 V islands |
| Route 309 at 20:00 | 7,190 | 4.5 h | Gulhi, Guraidhoo, Maafushi |

- **No single extra ferry brings any island newly within 2 h.** The far islands are too far by ferry, and the near ones already make it on the morning boat. The gain is hours of waiting saved.
- **Routes 301, 302, 304 and 305 save nothing:** they're intra-atoll routes, or (305 on Wednesday) only run outbound.

### 4.6 NSDS-style indicators (MBS has no base year for these)

| Indicator | Kaafu | All 23 |
|---|---|---|
| On an island with a direct scheduled boat to Greater Malé on Wednesday | 100% | 76.9% |
| Greater Malé reachable by scheduled boat the same day (changes allowed) | 100% | 81.9% |
| Within 30 min of any health facility (on-island health centre) | 100% | 100% |
| Within 2 h of a Greater Malé hospital (averaged over daytime departures, ferries) | 2.4% | 1.4% |
| Within 2 h of any hospital (averaged over daytime departures, ferries) | 2.4% | 17.7% |

**Why the direct-boat figure isn't 100%:** Mathiveri and Bodufolhudhoo have to change at Ukulhas, and all of Alif Dhaalu has no Wednesday boat.

**Slide angle:** everyone has a health centre within 30 min, but almost no one reaches a hospital within 2 h by public boat. A repeatable method for both NSDS indicators.

### 4.7 The last mile doesn't matter (a finding)

- From every Malé and Hulhumalé terminal, the nearest hospital is a **6.6–11.2 min walk**. A bus or taxi to any other hospital takes longer, at every hour.
- So **all 3,200 reachable rows use walking**, and the real Avas taxi times changed nothing.
- **The boat is the whole problem.** This is a result, not an assumption: it holds because M1 checked walking, buses and taxis at every hour.

---

## 5. Decisions we made, and why

### 5.1 From the plan, carried out as written
- **Service day:** Wednesday. Thursday's own legs are added at +1440, not a copy of Wednesday, because routes 303, 305, 306 and 307 alternate by day.
- **Malé jetty:** all CFN Malé stops use Jetty NO5 (`T_MALE_NORTH`), flagged as assumed.
- **Senahiya (H03)** is included.
- **Islands with their own atoll hospital** score 5 min (`ACCESS_MIN`) for `any_hospital`.

### 5.2 Blank daytime medians (11 islands): kept as is
- **Why they're blank:** the scan covers Wednesday and Thursday only. Where most daytime departures can't reach a hospital by the end of Thursday, because the next boat is at the weekend, the median is infinite.
- **The Alif Dhaalu oddity:** ADh has a number (27.5 h) even though it has no Wednesday boat, because its boat is on Thursday, inside the scan. The AA and V islands' next boats are at the weekend.
- **Considered:** scanning a full week, using "more than X h", or a median over reachable departures only. The last would make Thoddoo look 493 min from just 2 of its 49 departures, which is misleading.
- **Decided:** keep the blanks for the demo; it's a real finding. The dashboard shows them as "unreachable today", and slide 5 ranks by last practical departure. A full-week scan goes on the roadmap slide.

### 5.3 Trip breakdown with a change of boat
- **The scan finds the earliest arrival.** For Alif Dhaalu, that showed people taking Wednesday's local boat to Mahibadhoo and waiting overnight: a 1,520-minute "transfer".
- **The fix:** the breakdown now uses the latest boats that still give the same arrival, so the wait happens at home. Totals are unchanged.

### 5.4 Last mile: nearest hospital, so walking wins
- **Considered:** a third target, "IGMH only" or "public hospitals only". The nearest hospital from Jetty NO5 is ADK, which is private.
  - IGMH from Jetty NO5: 23 min on foot against 16.8 by taxi.
  - IGMH from Hulhumalé: no walking route; 24.6 min by taxi.
  - With that target, M1's taxi and bus data would drive the results.
- **Not done:** it's a team judgement call. Have the answer ready if a judge asks about private hospitals.

### 5.5 Observed boat times (`observed: True`)
- **Re-timing:** a ferry leg takes Eish's `slow` median where there are at least 5 trips. It doesn't if the median is more than **1.5× the scheduled time** (`OBSERVED_MAX_SLOWDOWN`; Eish's suggestion). The slow class includes cargo dhonis: e.g. Malé → Himmafushi is 74 min observed against 40 scheduled.
- **Delays:** a boat can't leave a stop before it arrives there, so a slowed leg delays the rest of its trip.
- **Synthetic speedboats (agreed with Saroof):**
  - **Which pairs:** island → Greater Malé pairs with at least **5 fast trips a day** (`SPEEDBOAT_MIN_TRIPS_PER_DAY`).
  - **Spacing:** evenly spaced between the first and last hour seen, at `(last − first) × 60 / trips_per_day` min.
  - **Timing and arrival:** each takes the observed median, on Wednesday and Thursday, arriving at Jetty NO5.
  - **Labels:** `route_id = SPEEDBOAT`, `estimated = yes`, "observed boat movements, not a published schedule".
- **Eish's hours are taken as recorded,** including Dhiffushi's boats from 01:00.
- **The default stays ferries only** (`observed: False`). The committed `access_results.csv` and Zayan's map are ferries only.

### 5.6 `observed_gap_min`
- **Definition:** the quickest scheduled ride from the island to a Greater Malé terminal on one trip, minus the median of **all** tracked trips from the island to Malé, Hulhumalé or Villimalé (at least 5 trips).
- **Blank where there's no direct scheduled boat:** Mathiveri, Bodufolhudhoo, and the ADh islands except Mahibadhoo.

### 5.7 Sliders and scenarios
- **`ferry_factor`:**
  - Re-spaces a route's runs evenly between its first and last run, per direction and per day.
  - Each copy follows the nearest original run.
  - A route with one run that day (305, 307 on Wednesday) can't be re-spaced, so use `extra_runs`.
  - At least one run is always kept.
- **`extra_runs`:** copies the route's run nearest that time, choosing one heading towards Malé if the route has one.
- **`thulusdhoo_hospital`:**
  - What it represents: the hospital under construction.
  - Adds H10 at the Thulusdhoo harbour point, for `any_hospital` only.
  - The walk is the same as for its health centre.
- **`bus_factor` and `taxi_availability`:** they work, but change nothing (5.4), so they may not be worth showing on the dashboard.
- **Best ferry change:**
  - **Unreachable departures** are counted as arriving at the end of Thursday, so the savings are a lower bound.
  - **"Newly within 2 h"** uses any departure 06:00–18:00.
  - **Ranking** is by people-hours saved.

### 5.8 "Within 2 h": averaged over the day, not the median (changed 24 Oct)
- **Before:** an island counted only if its *median* daytime trip was ≤ 2 h. That made each island all or nothing, so Kaafu showed 0% and hid the people who do catch the morning boat.
- **Now:** each island contributes its population × the share of its 49 daytime departures (06:00–18:00) that arrive within 2 h. This answers "if you need a hospital at a random daytime moment, what's the chance you get there in 2 h?", which is like for like with HDX's "leave whenever you need to".
- **Why people "leave after the boat":** the departure time is when the need arises, not a choice. Planned trips are covered by the best time and the last practical departure.
- **Changed:** `population_within.csv` (`departure = daytime`, was `day_median`), `hdx_comparison.csv`, the two hospital rows of `nsds_figures.csv` (renamed `*_within_120_daytime`), `m3_within_vs_hdx.png`, `m3_slide_numbers.md`.
- **Unchanged:** `access_results.csv`, `island_summary.csv` (`day_median_min` still describes each island's typical trip and drives the worst-served chart), and every per-departure number (e.g. 30.8% leaving at 07:00).
- **Dashboard:** Saroof's daytime cards still use the median, so they need the same rule to match the slides.

---

## 6. Doubts and limits (for the limits slide and Q&A)

**Data**
- **Speedboat departures are modelled, not scheduled.** They come from 2025 trackers and are spread evenly over the hours seen. Some may be private, resort or chartered boats, which the plan puts out of scope, and we assume anyone can board.
- **Trackers cover some boats only.** Counts are boat movements, not passengers.
- **Time mismatch:** FollowMe is from Aug 2025, while the timetable is 2026 and Avas is Aug–Sep 2026.
- **The Malé jetty is assumed** (Jetty NO5) for every CFN route and every speedboat.
- **The Villimalé ferry is generated** from frequency bands, with an 8-min crossing.
- **HDX is car-only** with its own modelled population, and it has no ADh or V rows. **Compare percentages only.**

**Model**
- **One day:** Wednesday only. Alif Dhaalu has no Malé boat that day, and no single day has a boat from every atoll.
- **Two-day horizon:** a departure that can't arrive by the end of Thursday is "unreachable", which produces the blank medians.
- **Fixed assumptions:** home to harbour is 5 min, a boat change takes 10 min, and walks are straight-line distances at 80 m/min.
- **15-minute departure steps** make the through-the-day chart spiky. That's real (boats are discrete), but the exact peaks depend on the step.
- **Speedboats from Maafushi go mostly to the airport (Hulhulé), and those aren't modelled.**
  - Maafushi → Hulhulé fast trips: 6 a day. Maafushi → Malé: 3.8 a day, below the 5-a-day threshold.
  - There's no terminal or last mile on Hulhulé, so Maafushi gets no speedboats. Its 6.2 h median is ferry-based and probably overstates reality.
  - Huraa (4.0 a day) and Guraidhoo (3.3) are also just under the threshold.
- **Nearest hospital includes ADK, which is private.** "Within 2 h of a hospital" doesn't mean "of a hospital you can afford", and IGMH would be slower (5.4).
- **Out of scope:** ambulance boats, charters and air travel.

**Open questions (none block the demo)**
- Should the threshold for synthetic speedboats be lower, e.g. 3 a day, to include Huraa, Maafushi and Guraidhoo? It's a one-line config change, but it should be agreed with the team.
- Is a "public hospitals only" target worth adding for Q&A?

---

## 7. Suggested slide content

**Slide 4 (method), M3 line:**
- Timetable → every boat leg → earliest arrival from each island, every 15 min of the day → plus the walk, bus or taxi to the hospital → door-to-door time.
- 23 islands × 96 departures × 2 targets.

**Slide 5 (findings):**
- **Headline:** HDX's car-only estimate puts 77% of Kaafu within 2 h of a hospital. Need a hospital at a random daytime moment and, by public ferry, there's a 2.4% chance of getting there in 2 h. With the speedboats people actually use, 23%.
- **Miss the morning boat:** on most islands the last practical departure for a Malé hospital is before 09:00, and Alif Dhaalu has none on a Wednesday.
- **The ferry isn't slow, it's rare:** re-timing ferries to observed speeds changes nothing; adding the observed speedboats changes everything.
- **The last mile isn't the problem:** every terminal is a 7–11 min walk from a hospital.
- **Charts:** `m3_within_vs_hdx.png` (headline), `m3_last_departure.png` or `m3_worst_served.png`, `m3_within_2h_through_day.png`, `m3_scheduled_vs_observed.png` (shared with Eish).

**Slide 6 (policy):**
- **For MTCC:** one extra evening run on route 307 or 303 saves the Kaashidhoo/Gaafaru and AA islands 11–13 hours on average per person. Route 308 at 18:00 helps the most people (6,737). Chart: `m3_best_ferry_change.png`.
- **For MBS:** two NSDS indicators now have a repeatable base-year method (section 4.6).
- **Scenario to mention:** Thulusdhoo's new hospital, available as a dashboard slider.

**Slide 7 (limits), M3 items:**
- Wednesday only, and a two-day horizon.
- Malé jetty assumed.
- Speedboats modelled from 2025 trackers, not a schedule.
- Airport-bound speedboats not modelled.
- Straight-line walks; fixed 5/10-min access and transfer.
- Nearest hospital may be private.

**Slide 8 (roadmap):**
- All 20 atolls and all 7 days, with a full-week scan.
- A GTFS feed for CFN.
- Live FollowMe for real-time speedboat availability.
- Public-hospital and ambulance-boat scenarios.

---

## 8. Where everything is

| What | Where |
|---|---|
| Code | `src/kaafu/timetable.py`, `routing.py`, `indicators.py`, `scenarios.py`, `m3_figures.py` |
| Tests | `tests/test_routing.py` (14) |
| Outputs | `data/processed/connections.csv`, `access_results.csv`, `island_summary.csv`, `population_within.csv`, `hdx_comparison.csv`, `nsds_figures.csv`, `best_ferry_change.csv` |
| Figures and slide numbers | `docs/figures/m3_*.png`, `docs/figures/m3_slide_numbers.md` |
| Status and team notes | `m3_claude.md` |
| Plan and data notes | `docs/BUILD_PLAN.md`, `docs/CLAUDE_HANDOVER.md`. M3's brief (`M3_network.md`) is in Al's local `claude/` folder, not committed. |
| M1 and M2 status | `m2_claude.md` (Eish); Zayan's notes on the `zayan` branch |

**AI-assisted (for the README):** all M3 code, tests and figures were written with Claude Code.
