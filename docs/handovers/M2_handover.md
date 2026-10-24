# M2 movement data (FollowMe and Avas): handover

**Owner:** Eish (M2) · **Branch:** `m2-movement` · **Last updated:** 24 Oct 2026, after Steps 1–3 and merging `zayan` and `m3-network`

This file records everything M2 has done:
- what was built and why;
- what M1 (Zayan), M3 (Al) and M4 (Saroof) need from it;
- the alternatives that were considered;
- open doubts;
- numbers and draft text for the slides.

It is the source for M2's parts of slides 4, 5 and 7. A Claude session picking up M2 work should read it after `docs/CLAUDE_HANDOVER.md` and `docs/BUILD_PLAN.md`.

Team: M1 Zayan (GIS), M2 Eish (movement), M3 Al (network), M4 Saroof (lead, dashboard).

---

## 1. Summary

M2 turns two raw datasets into three committed tables:

| Output | From | Used by | Purpose |
|---|---|---|---|
| `data/processed/avas_hourly.csv` | Avas taxi requests, Aug–Sep 2026 | M1 `lastmile.py` | Taxi wait (unserved share) and fallback taxi speed, by zone and hour |
| `data/processed/observed_pairs.csv` | FollowMe boat GPS, Aug 2025 | M3 `scenarios.py` (observed switch), M1 `geo.py` (map) | Observed boat time and frequency per island pair, ferry-like (`slow`) or speedboat-like (`fast`) |
| `data/processed/observed_trips.csv` | FollowMe boat GPS, Aug 2025 | Map lines, checks | One row per observed boat trip |

**Headline results:**
- **Observed slow boats match the ferry timetable.** The median gap is 5 minutes over 28 legs, and the Villimalé ferry is 8 minutes in both.
- **Speedboats dominate near Malé.** 74–88% of trips from the nearby islands are fast. Maafushi → Malé takes 84–90 min by ferry and 41 min by speedboat.
- **The taxi last mile:** 7.7% of requests go unserved overall. That rises to 18% at 07:00, and to 67% at the airport at 23:00.

---

## 2. What was done, in order

| # | What | Commit (on `m2-movement` unless noted) |
|---|---|---|
| 0 | **`config.py` and `src/kaafu/__init__.py` pushed to `main`.** At Zayan's request, his latest `config.py`, byte-for-byte (blob `e374d1c`), was pushed first so the merges later on would be clean. | `b6efe25` on `main` |
| 1 | **M2 settings added to `config.py`**, as new lines only (listed in §8). | `ae38c18` |
| 2 | **Step 1:** `avas.py` → `avas_hourly.csv`. | `0d95123` |
| 3 | **Step 2:** `followme.py` on one week (4–10 Aug 2025), with the first rough `observed_*` files. | `8cae9d9` |
| 4 | **Step 3:** full month, final `observed_*` files and validation against the timetable. | `e81767a` |
| 5 | **Merged `origin/zayan`** (up to `3905772`). The only conflict was `config.py` (add/add). It was resolved by keeping Zayan's file plus the M2 block. | `f62fccc` |
| 6 | **Merged `origin/m3-network`** (up to `71bcccd`). No conflicts. Al's 12 tests pass and every module imports. | `16088af` |
| 7 | **Handover and slide draft.** | `f948a12` and this update |

**Branch rules followed:**
- Nothing M2-specific is on `main`. `m2-movement` is pushed, and merging it into `main` is the lead's call.
- Raw data (`data/raw/`) is never committed.
- Outputs carry no IMEI or full device ID: `git grep -i imei` finds only comments.

---

## 3. How M2's outputs connect to the others

### M1 (Zayan): taxi last mile and map

- **`lastmile.py` reads `avas_hourly.csv` as is.**
  - It looks up `(zone, hour)` for `expired_share` and `median_speed_kmh`.
  - Zone names `male`, `hulhumale` and `airport` match `config.TAXI_ZONE`, and all 24 hours exist for each zone.
- **Zayan needs to rerun `python -m kaafu.lastmile`.** The `last_mile.csv` currently on the branches still uses his taxi placeholder (20 km/h, 7% unserved). After his rerun, Al reruns `indicators` and `scenarios`.
- **Taxi wait formula** (his): `TAXI_BASE_WAIT_MIN + expired_share × TAXI_RETRY_MIN`.
- **`median_speed_kmh` is only his fallback**, for terminal–hospital pairs with fewer than 10 real Avas rides. That's why M2 gives a same-zone speed (§5.1).
- **His map** (`geo.observed_trips_layer`) reads `observed_pairs.csv`.
  - It draws pairs with `n_trips ≥ OBSERVED_MIN_TRIPS` (5), coloured by `slow`/`fast`, with width set by `trips_per_day`.
  - The columns and labels match.
- **M2 uses his `island_zones.geojson`:** 27 OSM outlines + 300 m. If he changes it, `followme.py --month` must be rerun and both `observed_*` files pushed again.

### M3 (Al): observed boat times

- **The observed switch** in `scenarios.run_scenario(params)` raises `NotImplementedError` until he wires up `observed_pairs.csv`. That file is now final.
- **What Al plans to do with it** (from `m3_claude.md`):
  1. replace scheduled leg durations with the `slow` median where `n_trips ≥ 5`;
  2. add synthetic speedboat departures for busy `fast` pairs (`trips_per_day ≥ 5`), to be agreed with Saroof;
  3. fill `observed_gap_min` in `island_summary.csv`.
- **Keys:** `island_key` at both ends, `K.Malé` / `K.Hulhumalé` / `K.Villimalé` / `K.Hulhulé` for Greater Malé (not terminal IDs), as he asked.
- **Pairs are legs between consecutive stops,** like his `connections.csv`.
  - A boat that calls somewhere for less than 10 minutes isn't seen as stopping, so its pair spans two timetable legs (e.g. `V.Keyodhoo → K.Malé`).
  - Those pairs don't match a timetable leg, so a replace-by-pair step simply skips them.
- **Caution 1: legs where "slow" is much slower than the timetable** (≥ 5 slow trips):

  | Leg | Observed slow (trips) | Scheduled |
  |---|---|---|
  | Malé → Himmafushi | 74 min (22) | 40 |
  | Gaafaru → Kaashidhoo | 149 (9) | 90 |
  | Malé → Gaafaru | 271 (8) | 200 |
  | Maafushi → Guraidhoo | 55 (7) | 20 |
  | Guraidhoo → Maafushi | 38 (8) | 20 |
  | Mahibadhoo → Malé | 297 (13) | 260 |

  Probable cause: cargo dhonis and other slow boats share the `slow` class with the public ferry. If every slow median is swapped in, those legs get slower than scheduled. Al might keep the scheduled time where the observed one is far longer, e.g. more than 1.5×. That's his call.
- **Caution 2:** `ADh.Mahibadhoo → K.Malé` slow trips mostly leave at night (01:00–02:00 in the first week). They are not the 11:00 ferry 305.
- **Fast pairs for synthetic speedboats** (origin → Greater Malé, `trips_per_day ≥ 5`, all to `K.Malé`):

  | From | Trips a day | Median min | Hours seen |
  |---|---|---|---|
  | K.Thulusdhoo | 14.6 | 32 | 06–23 |
  | K.Dhiffushi | 7.5 | 47 | 01–18 |
  | K.Himmafushi | 7.3 | 18 | 05–23 |
  | AA.Thoddoo | 5.4 | 73 | 05–23 |

### M4 (Saroof): dashboard, merge, slides

- **`m2-movement` contains all three workstreams** (M1, M2, M3), merged and tested. Merging it into `main` brings everything.
- **For the island panel:** `observed_pairs.csv` gives "scheduled against observed" and speedboat frequency. `avas_hourly.csv` gives the "Avas unserved share by hour" chart in BUILD_PLAN 6.8.
- **README:** please link this file next to `m3_claude.md` and copy the AI-assisted list (§12).

---

## 4. Data used

| File (not committed) | Rows | Notes |
|---|---|---|
| `data/raw/avas/avas_rides_aug_sep_2026.csv` | 371,788 | `date_started` (local), pickup/dropoff lat/lng, `distance_km`, `time_sec`, `status` (`payment_completed`, `ride_completed`, `ride_expired`). Only rides ≥ 2.025 km and ≥ 300 s are in the file. |
| `data/raw/followme_kaafu_aug2025.parquet` | 9,922,162 | Made during prep. Box lat 3.40–5.05, lon 72.70–73.80. `device_id` is the md5 of the IMEI; `ts` is UTC; `speed` is in knots. |
| `data/sheets/islands.csv` | 27 | Island points and roles (origin / greater_male / transfer). |
| `data/processed/island_zones.geojson` (M1) | 27 | Island outlines + 300 m, all from OSM. |
| `data/sheets/ferry_timetable.csv` | 794 | Used only for validation. |

---

## 5. Method and decisions

### 5.1 Avas → `avas_hourly.csv` (`avas.py`)

1. **Requests:** keep Sunday–Thursday (`AVAS_WEEKDAYS`), because the build day is Wednesday. That's 266,410 requests.
2. **Pickup zone:** the first matching box in `AVAS_ZONES`, in the order male → airport → hulhumale. Only 2 pickups fall outside every box and are dropped. Dropoffs get a zone the same way.
3. **Per zone and hour (0–23):**
   - `completed`, `expired`, `expired_share = expired / (completed + expired)`;
   - plus an `all` zone, for 96 rows.
4. **`median_speed_kmh`:** the median of `distance_km / time_sec`, from completed rides that **start and end in the same zone** (`AVAS_SPEED_SAME_ZONE`).
   - A zone-hour with fewer than 20 such rides (`AVAS_MIN_RIDES`) takes that zone's all-day median.
   - A zone with too few rides all day takes `all`.
5. **Checks:** the script stops unless there are 96 rows and no blanks. It prints the slide numbers.

**Decisions considered:**

| Question | Options considered | Chosen | Why |
|---|---|---|---|
| Speed from which rides? | All rides by pickup zone (the guide's literal reading), or same-zone rides only | **Same-zone** | All rides give ~39 km/h everywhere, because rides are almost all Malé↔Hulhumalé bridge trips (90,031 + 89,858; only 360 Malé→Malé). M1 uses this speed only for short single-island hops, where 39 km/h would make taxis look too fast. Same-zone: Malé 28.8, Hulhumalé 32.2. |
| Fallback for thin hours | The `all` speed, or the zone's own all-day median | **Zone's all-day median** | `all` is dominated by Hulhumalé, so Malé would get Hulhumalé's speed. Speeds barely change by hour anyway. |
| Airport box top edge | 4.207 (the guide) or 4.205 | **4.205** | A scatter plot showed a pickup cluster at lat 4.2055–4.207 that is Hulhumalé's southern tip. 360 pickups (4% of the airport box) move to Hulhumalé. |
| `dayofweek` | — | `day_of_week` | `dayofweek` is deprecated in pandas 3. |

### 5.2 FollowMe → `observed_trips.csv`, `observed_pairs.csv` (`followme.py`)

Pipeline:
1. **Load** with DuckDB:
   - days 1–31 (or the development week 4–10 with no `--month`);
   - `ts + 5 h` (`FOLLOWME_UTC_OFFSET_H`);
   - exact (device, ts) duplicates removed. There are 75,630, which gives 9,846,532 pings, the figure from prep.
2. **Speeds per ping:**
   - `kmh`: ping-to-ping, only for gaps ≤ 30 min (`PING_MAX_GAP_MIN`);
   - `seg_kmh`: the same with no gap limit;
   - `still_kmh`: displacement between the first and last ping within ±2.5 min, over that time (`SPEED_WINDOW_MIN = 5`).
3. **Island zone per ping:** point in polygon with Zayan's zones. In the Hulhumalé/Hulhulé overlap (98 ha, the only overlap), the nearer island point wins.
4. **Boats:** devices with ≥ 5% of pings more than 2.5 km from every island point and ≥ 2 islands visited. That's 997 of 1,372 devices, against 1,026 in prep with its 1.2 km rule.
5. **Still pings:** `seg_kmh < 2` **or** `still_kmh < 2` (`STOP_SPEED_KMH`).
   - **Island stop:** a visit (consecutive pings in one zone) with ≥ 10 min of still time (`STOP_MIN`), counting the time since the previous ping.
   - **Other stop:** the same outside every zone. It ends a trip and starts none.
6. **Trips:**
   - A trip runs between consecutive island stops of one device at two different islands.
   - **Depart** is the last ping in the first zone, **arrive** the first ping in the next zone, so times run zone edge to zone edge.
   - Dropped: trips over 6 h (`MAX_TRIP_HOURS`), or faster than 80 km/h straight-line between island points (`MAX_BOAT_KMH`).
7. **Speed class:**
   - The split is the dip in the histogram of origin → Greater Malé trip speeds (2 km/h bins, 3-bin smoothing, lowest point between the two humps). The month gives **26 km/h**.
   - The fallback, if there's no clear dip, is 28 (`SPEED_CLASS_SPLIT_KMH`).
   - `slow` < split ≤ `fast`.
8. **Outputs:**
   - **Trips:** `device` is the first 8 characters of the md5 (`DEVICE_HASH_LEN`); times are local `YYYY-MM-DD HH:MM`.
   - **Pairs:** per (`from_key`, `to_key`, `speed_class`), with `n_trips`, `n_devices`, `median_min`, `p90_min`, `trips_per_day = n_trips / 31` and `first_hour`/`last_hour` of departure.

**How the stop rule was developed** (development week, origin → Greater Malé trips per day):

| Version | Rule | Island stops | Trips per day (median) | Dropped over 6 h | What went wrong |
|---|---|---|---|---|---|
| v1 | Consecutive pings with ping-to-ping speed < 2 km/h for ≥ 10 min | 7,879 | 62 | 254 | **GPS jitter:** 39% of pings from boats moored 30+ min read over 2 km/h, so stops break up and are missed. |
| v2 | Smoothed speed (±2.5 min) only | 4,763 | 58 | 416 | **Tracker sleeps:** a moored boat's tracker often goes quiet for 30–60 min. The ping after the gap sits next to "leaving" pings, so the sleep counted as moving. |
| **v3 (used)** | Still = ping-to-ping (no gap limit) **or** smoothed, below 2 km/h; ≥ 10 still minutes per zone visit | 6,755 | **77** | **15** | — |

**Other decisions considered:**

| Question | Options | Chosen | Why |
|---|---|---|---|
| Island zones | 600 m / 1.5 km circles (fallback), the 1.2 km circles from prep, or Zayan's OSM outlines + 300 m | **OSM outlines** | Real shapes; all 27 islands are covered. The circles stay in the code as a fallback. |
| Do stops outside the zones break a trip? | Ignore them, or break the chain | **Break** | They're real places. The busiest spots are Thilafushi and Gulhifalhu (4.18 N, 73.44–73.46 E) and resort areas. Only 74 of the week's 4,108 were within 3 km of Malé, so they're not Malé's anchorage. |
| Trip times | Dock-to-dock (first and last still ping), or zone edge (last and first ping in the zone) | **Zone edge** | This is BUILD_PLAN's "last ping of the first stop / first ping of the next". It's robust to harbour manoeuvring. The cost: a few minutes shorter than dock-to-dock. |
| Split at a fixed 28 km/h or at the histogram dip | — | **Dip, with 28 as fallback** | The month has a clear dip at 26. The week gave 24, so it's stable. |
| Greater Malé internal hops faster than 80 km/h | Keep, or drop | **Drop (rule)** | 1,865 dropped in the month. They are Malé↔Hulhulé and Hulhumalé↔Hulhulé, where the zones touch so a "trip" lasts seconds. Only 15 involve an origin island. |
| Airport (Hulhulé) trips | Count as Greater Malé, or keep separate | **Separate key** | There's no hospital there and no ferry terminal (`T_AIRPORT` isn't used). 274 origin → Hulhulé trips are kept in the files under `K.Hulhulé`. |
| Prep's numbers (`followme_check.txt`) as the benchmark | — | **Not used as a benchmark near Malé** | Prep counted any boat within 1.2 km of an island point, so resort speedboats passing by were counted. Its Huraa → Malé 16 min means ~75 km/h over 20 km, with 24.5 trips a day; we get 23 min and 4.9 a day. Further out it agrees roughly. |

---

## 6. Results

### 6.1 Avas (Sun–Thu, Aug–Sep 2026)

- **Requests:** 266,410: Hulhumalé 133,250, Malé 125,318, airport 7,840.
- **Unserved:** 7.7% overall. The worst hours are 07:00 (17.9%), 18:00 (15.9%), 17:00 and 08:00 (15.2%).
- **Commuter pattern:** Hulhumalé is worst in the morning (22.9% at 07:00), Malé in the evening (24.0% at 18:00).
- **Worst zone-hour:** the airport at 23:00, 66.7% (496 of 744).
- **Same-zone speeds:** Malé 28.8 km/h, Hulhumalé 32.2, `all` 32.2. They're flat across the day.
  - Malé has only 360 same-zone rides, so 15 of its 24 hours use the all-day median.
  - The airport has 36 rides, so it uses its all-day median (36.9) for every hour.

### 6.2 FollowMe (all of August 2025)

- **Pings:** 9,846,532 after removing duplicates.
- **Devices:** 1,372, of which 997 are boats.
- **Speed column:** × 1.852 ÷ derived = 0.952, so it's knots.
- **Stops:** 30,801 island stops and 43,685 other stops.
- **Trips:** 10,975 kept, with 84 dropped as over 6 h and 1,865 as faster than 80 km/h.
- **Origin → Greater Malé:** 2,655 trips, 61–114 a day (median 85), plus 274 origin → airport.
- **Pairs:** 395, of which 194 have ≥ 5 trips (72 of them slow).

All 23 origin islands, into Greater Malé:

| Origin | Trips | Per day | Median min | Slow median | Fast share |
|---|---|---|---|---|---|
| K.Thulusdhoo | 538 | 17.4 | 33 | 99 | 87% |
| K.Himmafushi | 299 | 9.6 | 20 | 46 | 78% |
| K.Dhiffushi | 295 | 9.5 | 49 | 155 | 88% |
| K.Maafushi | 183 | 5.9 | 48 | 122 | 69% |
| AA.Thoddoo | 179 | 5.8 | 73 | 267 | 94% |
| K.Huraa | 151 | 4.9 | 23 | 65 | 86% |
| K.Guraidhoo | 147 | 4.7 | 56 | 147 | 71% |
| AA.Rasdhoo | 101 | 3.3 | 68 | 240 | 97% |
| ADh.Mahibadhoo | 99 | 3.2 | 111 | 287 | 77% |
| ADh.Dhangethi | 94 | 3.0 | 106 | 342 | 94% |
| V.Felidhoo | 78 | 2.5 | 111 | 351 | 96% |
| K.Kaashidhoo | 71 | 2.3 | 115 | 302 | 80% |
| ADh.Dhigurah | 70 | 2.3 | 106 | — | 100% |
| K.Gulhi | 68 | 2.2 | 30 | 123 | 74% |
| AA.Ukulhas | 66 | 2.1 | 97 | 287 | 85% |
| V.Keyodhoo | 63 | 2.0 | 108 | 331 | 94% |
| V.Fulidhoo | 59 | 1.9 | 72 | 306 | 92% |
| K.Gaafaru | 42 | 1.4 | 80 | 276 | 86% |
| AA.Mathiveri | 32 | 1.0 | 120 | — | 100% |
| V.Thinadhoo | 7 | 0.2 | 99 | 315 | 71% |
| ADh.Hangnaameedhoo | 7 | 0.2 | 289 | 315 | 29% |
| AA.Bodufolhudhoo | 4 | 0.1 | 115 | 257 | 75% |
| ADh.Omadhoo | 2 | 0.1 | 183 | 276 | 50% |

"Slow median" here is the origin's slow trips into Greater Malé, which can span several timetable legs. Use the leg table in §6.3 to compare with the schedule.

### 6.3 Scheduled against observed (validation)

CFN and Villimalé legs, scheduled minutes against observed medians, August 2025:

| Leg | Route | Scheduled | Observed slow (trips) | Observed fast (trips) |
|---|---|---|---|---|
| Malé → Villimalé | VILI | 8 | 7.7 (51) | 3.3 (29) |
| Villimalé → Malé | VILI | 8 | 8.5 (36) | 4.0 (45) |
| Hulhumalé → Malé | many | 25 | 23 (668) | 6 (992) |
| Malé → Hulhumalé | many | 28 | 24 (503) | 7 (410) |
| Maafushi → Malé | 306 | 90 | 84 (34) | 41 (119) |
| Malé → Maafushi | 306 | 90 | 89 (35) | 28 (251) |
| Himmafushi → Hulhumalé | 308 | 40 | 41 (48) | 13 (8) |
| Gulhi → Malé | 309 | 75 | 86 (10) | 26 (48) |
| Rasdhoo → Ukulhas | 301, 303 | 50 | 58 (12) | 17 (41) |
| Felidhoo → Thinadhoo | 306 | 10 | 10 (8) | 3 (33) |
| Malé → Mahibadhoo | 305 | 250 | 270 (23) | 111 (68) |
| Mahibadhoo → Malé | 305 | 260 | 297 (13) | 105 (73) |

- **Agreement:** 28 of the 52 CFN legs have ≥ 5 slow trips, and their median gap from the schedule is **5 min**.
- **Exceptions:** the six slower legs in §3 (M3).
- **Whole routes:** the guide's "Felidhoo → Malé 325 min" is the whole of route 306 (Keyodhoo → Felidhoo → Thinadhoo → Fulidhoo → Maafushi → Malé). The observed data splits it into legs. Two legs check out (Felidhoo → Thinadhoo 10 against 10, Maafushi → Malé 84 against 90); Thinadhoo → Fulidhoo and Fulidhoo → Maafushi have only 1–2 slow trips.

---

## 7. Doubts and open questions

1. **The `slow` class isn't purely the public ferry.** Cargo dhonis and other slow boats are in it (the six slow legs in §3, and Mahibadhoo's night boats). M2 has no way to tell a ferry from a dhoni in FollowMe. *Possible refinement:* keep only slow trips that depart within ±30 min of a scheduled departure. Not done yet.
2. **The 10-minute stop rule misses quick speedboat drop-offs.** A boat calling at Huraa for 5 minutes isn't seen stopping, and that trip merges into the next. A 5-minute rule was considered but not tested. It would raise counts near Malé and might create false stops, such as boats waiting at anchor. The guide says 10.
3. **Zone-edge timing** runs a few minutes shorter than dock-to-dock. It's larger for Malé, whose zone is big: the island plus 300 m. For the ferry match it doesn't seem to matter (median gap 5 min).
4. **Trip counts are lower than prep's** (85 a day against ~116). The main reason is prep counting resort boats near the island points. But our stricter rule also misses short stops (doubt 2). The truth is probably in between.
5. **Avas durations look modelled.** Ride time ≈ 70 s + 85 s per km (correlation 0.976, spread ~39 s), so taxi speed doesn't change with traffic. Only the unserved share is a real hourly signal. If the organisers say durations are real, nothing breaks, but "no rush hour" should then be reported as a finding instead of a limit.
6. **Malé same-zone speed** rests on only 360 rides. It's stable (28.3–29.1 km/h), but thin.
7. **The airport zone** has its own unserved share and speed. No ferry terminal is on Hulhulé, so M1's last mile doesn't use it.
8. **Different years:** FollowMe is Aug 2025, the ferry timetable is effective Aug 2026, and Avas is Aug–Sep 2026.
9. **Tracker coverage:** which boats have FollowMe trackers is unknown, so trips are boat movements, not passengers, and not all boats.
10. **The 375 non-boat devices** (land, moored or unclear) are excluded by the boat filter and weren't examined further.

---

## 8. Settings M2 added to `config.py` (on `m2-movement`)

| Setting | Value | Meaning |
|---|---|---|
| `PING_MAX_GAP_MIN` | 30 | Ping-to-ping `kmh` only for gaps up to this |
| `SPEED_WINDOW_MIN` | 5 | Width of the smoothing window for still detection (±2.5 min) |
| `BOAT_MIN_SEA_SHARE` | 0.05 | A boat has ≥ 5% of pings at sea… |
| `BOAT_SEA_DIST_M` | 2500 | …more than 2.5 km from every island point… |
| `BOAT_MIN_ISLANDS` | 2 | …and visits ≥ 2 islands |
| `SPEED_CLASS_SPLIT_KMH` | 28 | Fallback slow/fast split if there's no histogram dip |
| `DEVICE_HASH_LEN` | 8 | Characters of the md5 kept in outputs |
| `FOLLOWME_DAYS` | 31 | Days in August, for `trips_per_day` |
| `FOLLOWME_DEV_DAYS` | (4, 10) | Development week |
| `AVAS_WEEKDAYS` | [6, 0, 1, 2, 3] | Sun–Thu (pandas `day_of_week`) |
| `AVAS_ZONES` | 3 boxes | male, airport (top 4.205), hulhumale |
| `AVAS_MIN_RIDES` | 20 | Thin zone-hour → zone's all-day speed |
| `AVAS_SPEED_SAME_ZONE` | True | Speed from rides that start and end in the same zone |

M2 also uses these shared settings:
- **FollowMe:** `FOLLOWME_UTC_OFFSET_H`, `KNOTS_TO_KMH`, `STOP_SPEED_KMH`, `STOP_MIN`, `MAX_BOAT_KMH`, `MAX_TRIP_HOURS`, `OBSERVED_MIN_TRIPS`.
- **Fallback zone circles:** `ZONE_CIRCLE_M`, `ZONE_CIRCLE_LARGE_M`, `LARGE_ZONE_ISLANDS`.

---

## 9. How to run

From the repo root (Windows PowerShell). The raw files must be in `data/raw/`, which is never committed.

```powershell
$env:PYTHONPATH = "src"
python -m kaafu.avas                                    # avas_hourly.csv (~15 s)
python -m kaafu.avas --plot plans/review/avas_zones.png # plus a pickup scatter with the zone boxes
python -m kaafu.followme --month                        # observed_trips.csv, observed_pairs.csv (~25 s)
python -m kaafu.followme                                # development week only (~5 s)
python -m pytest tests -q                               # M3's routing tests (12 pass on m2-movement)
```

**Notes for whoever runs this next:**
- **Each `main()` takes an optional `cfg`** (default `kaafu.config`) and prints its checks.
- **`followme.py` falls back to circles** if `island_zones.geojson` is missing, and says so.
- **DuckDB 2.0:** `con.sql(...).fetchone()` no longer exists. Use `con.execute(...).fetchone()`.
- **Packages** were installed with `pip install --user` because `C:\Python312` isn't writable, so scripts like `streamlit` aren't on PATH. Use `python -m streamlit` and `python -m pytest`.

---

## 10. Slide content (draft)

Written for the judges. All numbers come from §6; edit freely.

### Slide 4 (Method): boat GPS → stops → trips

- **9.8 million GPS pings from 997 boats, August 2025** (FollowMe). Clock shifted from UTC to Malé time, duplicates removed.
- **A stop** is at least 10 minutes standing still inside an island's outline (+300 m). Speed is measured over 5 minutes, because ping-to-ping GPS noise makes moored boats look like they're moving.
- **A trip** runs from leaving one island stop to reaching the next: 10,975 trips, 2,655 of them into Greater Malé (85 a day).
- **Ferry or speedboat:** trips split at the dip in the speed histogram, 26 km/h.
- **Checked against the timetable:** for 28 ferry legs, observed slow boats are within a median of 5 minutes of the schedule. The Villimalé ferry takes 8 minutes on paper and 8 in the data.

*Speaker note:* "We don't guess boat times. We rebuilt them from GPS tracks and checked them against the published timetable."

### Slide 5 (Findings): what people actually ride

- **The public ferry is the slow option.** From the islands near Malé, 74–88% of boat trips are speedboats.
  - Maafushi → Malé: ferry 84–90 minutes, speedboat 41.
  - Himmafushi → Malé: speedboat 18 minutes, 7 a day.
- **Busiest links into Malé** (boats a day): Thulusdhoo 17, Himmafushi 10, Dhiffushi 10, Maafushi 6, Thoddoo 6.
- **Far atolls depend on the ferry schedule.** Mahibadhoo → Malé is 260 minutes scheduled; slow boats take a median 297 and speedboats 105.
- **The last mile:** 7.7% of taxi requests in Greater Malé go unserved.
  - That rises to 18% at 07:00 and 16% at 18:00.
  - Morning is worst in Hulhumalé (23%), evening in Malé (24%).
  - At the airport at 23:00, two in three requests go unserved.

*Chart ideas:*
- **Bars, scheduled against observed:** for five legs from §6.3 (Maafushi → Malé, Malé → Maafushi, Hulhumalé → Malé, Mahibadhoo → Malé, Villimalé → Malé), scheduled, observed slow and observed fast side by side.
- **Line, unserved share by hour:** `avas_hourly.csv` with one line per zone.

### Slide 7 (Limits): M2 items

- **Boat coverage:** boat tracks only cover boats with a FollowMe tracker. They count boat movements, not passengers, and are from August 2025 while the timetable is from 2026.
- **"Slow" boats** include cargo dhonis, not only the public ferry.
- **Stop rule:** stops under 10 minutes are missed. Times run from island edge to island edge, a few minutes shorter than dock-to-dock.
- **Raw FollowMe data:** timestamps are UTC (shifted +5 h) and the speed column is in knots. We derive speed from positions instead.
- **Taxi data:** Avas only includes rides of 2 km or more (Aug–Sep 2026). Ride times look modelled, so there's no rush-hour traffic in taxi speeds; only the unserved share changes through the day.

### Possible roadmap lines (slide 8)

- **Live boat feed:** a live FollowMe feed would let observed times update daily.
- **Ferry or dhoni:** matching slow trips to scheduled departures would separate the public ferry from cargo boats.
- **Full taxi data:** Avas rides under 2 km and real pickup waits would give a true taxi last mile inside Malé.

---

## 11. Things a Claude session should know before touching M2 files

- **Ownership:** M2 owns `src/kaafu/avas.py` and `src/kaafu/followme.py`, plus the three outputs in §1. Don't edit other members' files.
- **`config.py` is shared:**
  - M2's settings are the lines in §8;
  - change shared settings only with the team;
  - if `main`'s `config.py` changes, merge it in, don't copy it over.
- **Branches:**
  - push only `m2-movement`, never `main`;
  - before every commit, `git fetch` and look at the other branches;
  - merge `origin/zayan` and `origin/m3-network` into `m2-movement`, then run `pytest` and an import check.
- **Joins:** always on `island_key`, never on a plain island name.
- **Restricted data:**
  - never commit `data/raw/`;
  - never output more than 8 characters of `device_id`;
  - run `git grep -i imei` before committing.
- **Local-only folder:** `plans/` holds reference copies and review exports. It's ignored via `.git/info/exclude` and is not part of the repo.

---

## 12. AI-assisted (for the README)

- **`src/kaafu/avas.py` and M2's settings in `src/kaafu/config.py`** were written with Claude Code: zone assignment, the hourly table with fallbacks, checks, and the zone scatter.
- **`src/kaafu/followme.py`** was written with Claude Code: DuckDB loading with the +5 h shift, de-duplication, segment and smoothed speeds; island zone per ping; boat filter; stop and trip detection; the speed-class split; output tables and checks.
- **Data checks were run with Claude Code:**
  - **Avas:** speed against distance, pickup × dropoff zones, the airport-box edge.
  - **FollowMe:** GPS jitter, tracker sleeps, other-stop locations, too-fast trips, timetable legs against observed medians.
- **Writing and merging:** this handover file, the draft slide text, and the merges of `zayan` and `m3-network` into `m2-movement` were prepared with Claude Code.
- **Prep:** last night's queries (`data_pack/prep/followme_queries.sql`, DuckDB CLI) were AI-assisted.
