# M2 movement data (FollowMe and Avas): status

**Owner:** Eish (M2) · **Branch:** `m2-movement` · **Last updated:** 24 Oct 2026, after Step 2 (one-week `observed_trips.csv` and `observed_pairs.csv`)

This file says what M2 has built, what it gives the rest of the team, and what comes next. It's updated after each major step. Team: M1 Zayan (GIS), M2 Eish (movement), M3 Al (network), M4 Saroof (lead, dashboard).

## Status at a glance

| Step | Status |
|---|---|
| 1. `avas.py` → `avas_hourly.csv` | Done |
| 2. `followme.py` on one week (4–10 Aug 2025) | Done. **Rough** `observed_trips.csv` and `observed_pairs.csv` (one week) pushed for Al |
| 3. Full month → `observed_trips.csv`, `observed_pairs.csv` | Next (replaces the one-week files, same columns) |
| 4. Validation numbers and limits for slides 4–5 | Not started |

## What each member needs to know

### Zayan (M1): taxi last mile

- **`data/processed/avas_hourly.csv` is ready** (`config.AVAS_HOURLY_CSV`), 96 rows: zones `male`, `airport`, `hulhumale` and `all`, each with all 24 hours. Columns as in BUILD_PLAN §4: `zone, hour, completed, expired, expired_share, median_speed_kmh`. Your `lastmile.py` reads it as is; **rerun `python -m kaafu.lastmile`** to replace the taxi placeholder.
- **`median_speed_kmh` comes from same-zone rides only** (pickup and dropoff in the same zone, `config.AVAS_SPEED_SAME_ZONE`):
  - Using all rides gives ~39 km/h everywhere. That's because nearly all rides cross the Malé–Hulhumalé bridge: 90,031 Malé→Hulhumalé, 89,858 Hulhumalé→Malé, and only 360 Malé→Malé.
  - Your code uses this speed only as the fallback for terminal–hospital pairs with fewer than 10 real Avas rides. Those are mostly short hops inside one island, so same-zone speed fits them better.
- **Speeds:** `male` 28.8 km/h, `hulhumale` 32.2, `all` 32.2. They are almost flat across the day (see limits).
  - `male` has only 360 same-zone rides. 15 of its 24 hours have fewer than 20, so those take Malé's all-day median.
  - `airport` speed (36.9) is based on 36 rides and is the same every hour. No ferry terminal is on Hulhulé, so the last mile shouldn't use it.
- **`expired_share` varies a lot** and is the main hourly signal:
  - Hulhumalé peaks in the morning (22.9% at 07:00), Malé in the evening (24.0% at 18:00).
  - The airport at 23:00 is 66.7% (496 of 744 requests).

### Al (M3): observed boat times

- **`data/processed/observed_pairs.csv` is in (rough, one week: 4–10 Aug 2025).**
  - 249 rows, of which 91 have `n_trips ≥ 5`. Columns exactly as BUILD_PLAN §4; `trips_per_day` = `n_trips / 7` for now.
  - The full month (Step 3) replaces it with the same columns, so you can wire up the `observed` switch now.
- **Keys:** `island_key`s at both ends, with `K.Malé` / `K.Hulhumalé` / `K.Villimalé` / `K.Hulhulé` for Greater Malé (not terminal IDs).
- **`speed_class`:** `slow` (ferry-like) is below 24 km/h straight-line average, `fast` (speedboat-like) is at or above it. The split is the dip in this week's trip-speed histogram: ferries peak at 12–16 km/h, speedboats at 40–56.
- **Pairs are legs between consecutive stops**, which matches how `connections.csv` is built.
  - A ferry calling at an island for less than 10 minutes isn't seen as stopping there, so that pair spans two timetable legs (e.g. `V.Keyodhoo → K.Malé`, slow 309 min).
  - Such pairs won't match a timetable leg, so your replace-by-pair step will just skip them.
- **Times run from zone edge to zone edge** (island outline + 300 m), so they are a few minutes shorter than dock-to-dock.
- **First check against the timetable:** `K.Maafushi → K.Malé` slow 92 min (8 trips) against 90 (route 306) and 100 (route 309, via Gulhi); fast 46 min (25 trips).
- **Watch:** `ADh.Mahibadhoo → K.Malé` slow (314 min, 4 trips) leaves at 01:00–02:00. These are night boats, not the 11:00 ferry 305 (260 min), so don't read them as the ferry.
- **`observed_trips.csv`** (2,433 trips) has `device` as an 8-character hash only, for map lines.

### Saroof (M4): config and merge

- **`config.py` on `main`** is Zayan's latest, unchanged (commit `b6efe25`).
- **`m2-movement` adds M2 settings to `config.py`**, as new lines only, so it merges cleanly:
  - FollowMe: `PING_MAX_GAP_MIN`, `SPEED_WINDOW_MIN`, `BOAT_MIN_SEA_SHARE`, `BOAT_SEA_DIST_M`, `BOAT_MIN_ISLANDS`, `SPEED_CLASS_SPLIT_KMH`, `DEVICE_HASH_LEN`, `FOLLOWME_DAYS`, `FOLLOWME_DEV_DAYS`.
  - Avas: `AVAS_WEEKDAYS`, `AVAS_ZONES`, `AVAS_MIN_RIDES`, `AVAS_SPEED_SAME_ZONE`.
- **README:** please link this file next to `m3_claude.md`. The AI-assisted list is at the bottom.

## How to run

From the repo root, with `data/raw/avas/avas_rides_aug_sep_2026.csv` in place (not committed):

```powershell
$env:PYTHONPATH = "src"
python -m kaafu.avas                                   # data/processed/avas_hourly.csv
python -m kaafu.avas --plot plans/review/avas_zones.png   # also a pickup scatter with the zone boxes
```

`avas.main()` takes an optional `cfg` argument, which defaults to `kaafu.config`. It prints the checks below every run and stops with an error unless the table has 96 rows and no blanks.

FollowMe needs `data/raw/followme_kaafu_aug2025.parquet` (not committed) and uses `data/processed/island_zones.geojson` (Zayan's), falling back to circles if it's missing:

```powershell
$env:PYTHONPATH = "src"
python -m kaafu.followme            # development week, 4-10 Aug 2025 (~5 s)
python -m kaafu.followme --month    # all of August 2025
```

## Files (M2 owns these)

| File | What it does |
|---|---|
| `src/kaafu/avas.py` | Avas requests to the hourly table: Sun–Thu filter, pickup and dropoff zones from `config.AVAS_ZONES`, counts and unserved share by zone × hour, same-zone median speed with fallbacks, checks. |
| `src/kaafu/followme.py` | FollowMe pings to stops to trips. **DuckDB:** load, +5 h, de-duplicate, segment and smoothed speeds. **numpy:** island zone per ping, boat filter. **pandas:** stops, trips, speed classes, both output files, checks. |

## Outputs in `data/processed/`

| File | Rows | Notes |
|---|---|---|
| `avas_hourly.csv` | 96 | 4 zones × 24 hours. Counts use every request; speed uses completed same-zone rides. |
| `observed_trips.csv` | 2,433 | **One week (rough).** One row per boat trip between two project islands; `device` is 8 characters of the md5 hash. |
| `observed_pairs.csv` | 249 | **One week (rough).** Per `from_key`, `to_key`, `speed_class`. |

## Step 1 numbers (Avas, Sun–Thu, Aug–Sep 2026)

- **Requests:** 266,410 Sun–Thu requests, with only 2 pickups outside the zone boxes (dropped). By zone: Hulhumalé 133,250, Malé 125,318, airport 7,840.
- **Unserved share overall:** 7.7%. Worst hours: 07:00 (17.9%), 18:00 (15.9%), 17:00 and 08:00 (15.2%).
- **Worst zone-hour:** airport at 23:00, 66.7% unserved.
- **Commuter pattern:** taxis are hardest to get in Hulhumalé in the morning (22.9% unserved at 07:00) and in Malé in the evening (24.0% at 18:00).

## Step 2 numbers (FollowMe, one week: 4–10 Aug 2025)

- **Pings:**
  - 2,247,898 read, 2,230,421 after removing exact duplicates. Over the whole month that's 75,630 duplicates, which explains the gap between 9.92 M rows and the 9.85 M in `followme_check.txt`.
  - 1,226 devices, of which 710 are boats.
- **Speed column:** × 1.852 ÷ derived km/h = 0.955, so it's knots.
- **Trips:**
  - 2,433 trips between project islands.
  - **Origin → Greater Malé** (Malé, Hulhumalé, Villimalé): 572 trips, 64–103 a day (median 77). Another 66 go to the airport (Hulhulé).
- **Busiest origins** (trips a day to Greater Malé, median minutes, share fast):

  | Origin | Trips a day | Median min | Fast |
  |---|---|---|---|
  | K.Thulusdhoo | 16.7 | 34 | 90% |
  | K.Himmafushi | 9.7 | 21 | 78% |
  | K.Dhiffushi | 9.1 | 49 | 88% |
  | K.Maafushi | 5.6 | 52 | 64% |
  | AA.Thoddoo | 5.4 | 75 | 95% |

- **Speedboats dominate near Malé:** 78–93% of trips from Huraa, Himmafushi, Thulusdhoo and Gulhi are fast.
- **No trips to Greater Malé** this week from ADh.Hangnaameedhoo or ADh.Omadhoo. Mathiveri, Bodufolhudhoo and V.Thinadhoo have one to four.
- **Last night's rough check (`followme_check.txt`) isn't a benchmark for the islands near Malé.**
  - It counted any boat within 1.2 km of an island point, so resort speedboats passing Huraa or Himmafushi were included.
  - Its Huraa → Malé median of 16 min means about 75 km/h over 20 km. We get 25 min (fast) and 4.9 trips a day, against its 24.5.

## Decisions and assumptions (for the limits slide)

- **FollowMe clock:** UTC, shifted +5 h. **Duplicates:** exact (device, time) repeats are removed.
- **Boats:** at least 5% of pings more than 2.5 km from every island point, and at least 2 islands visited.
- **Island zones:** Zayan's OSM outlines + 300 m. A ping in the Hulhumalé/Hulhulé overlap (98 ha) goes to the nearer island point.
- **Stops** (BUILD_PLAN 6.4: "slower than 2 km/h for at least 10 minutes"):
  - **Still pings:** a ping counts as still if the boat moved slower than 2 km/h since the previous ping, or across a ±2.5 min window (`SPEED_WINDOW_MIN`). Raw ping-to-ping speed is mostly GPS jitter: 39% of pings from boats moored 30+ min read over 2 km/h. Trackers also often sleep while moored, which the first test catches.
  - **Island stop:** a visit to a zone with at least 10 minutes of still time.
  - **Other stop:** the same outside every zone, e.g. Thilafushi, Gulhifalhu, resorts or sandbanks. It ends a trip without starting one.
- **Trips:**
  - A trip runs between consecutive island stops at different islands, from leaving the first zone to entering the next.
  - Dropped: over 6 h, or faster than 80 km/h straight-line. That's 422 trips this week, all but 2 of them Greater Malé hops between touching zones (Malé↔Hulhulé, Hulhumalé↔Hulhulé).
- **Speed class:** the split is the histogram dip (24 km/h this week); 28 km/h (`SPEED_CLASS_SPLIT_KMH`) is the fallback if there's no clear dip.
- **Avas:**
  - **Day group:** Sunday–Thursday only (`AVAS_WEEKDAYS`), because the build day is Wednesday.
  - **Zones:** pickup boxes from M2_movement.md, checked on a scatter plot. The airport box's top edge is 4.205 instead of 4.207, so 360 pickups on Hulhumalé's southern tip count as Hulhumalé. Boxes are checked in order male → airport → hulhumale.
  - **Same-zone speed:** explained under Zayan's section above.
  - **Fallbacks:** a zone-hour with fewer than 20 same-zone rides (`AVAS_MIN_RIDES`) takes the zone's all-day median. None of the 96 zone-hours had zero requests, so no unserved share was filled.

## Limits found in the FollowMe data

- **Trips are boat movements, not passengers.** Only boats with a FollowMe tracker are seen, and boat data is from Aug 2025 while the timetable is 2026.
- **Short stops are missed:** stops shorter than 10 minutes don't count, so quick speedboat drop-offs are merged into a longer trip or lost.
- **Times are zone edge to zone edge**, a few minutes shorter than dock-to-dock.

## Limits found in the Avas data

- **Only rides of 2 km or more and 5 minutes or more** are in the file (minimum `distance_km` 2.025, minimum `time_sec` 300). Short hops inside Malé are missing.
- **Ride times look modelled, not measured.** Ride time is almost exactly 70 s + 85 s per km of `distance_km`: correlation 0.976, with a spread of about 39 s. Hourly speeds barely change (Malé 28.3–29.1 km/h), so the data shows no rush-hour traffic. Only the unserved share varies through the day.
- **Avas covers Aug–Sep 2026; FollowMe is Aug 2025.**

## Next

1. **Step 3:** run `--month`, check the speed split on the full histogram, and push the final `observed_trips.csv` and `observed_pairs.csv`. `trips_per_day` will be `n_trips / 31`.
2. **Step 4:** scheduled against observed per leg (routes 305, 306 and 309), the speedboat story, busiest links, and the limits.

## AI-assisted (for the README)

- `src/kaafu/avas.py` and the M2 settings in `src/kaafu/config.py` were written with Claude Code: zone assignment, the hourly table with fallbacks, checks, and the zone scatter.
- The Avas data checks behind the same-zone speed decision were also run with Claude Code: speed against distance, pickup × dropoff zone counts, and the airport-box edge.
- `src/kaafu/followme.py` was written with Claude Code: DuckDB loading with the +5 h shift, de-duplication, segment and smoothed speeds; island zone per ping; boat filter; stop and trip detection; speed-class split; output tables and checks.
- The FollowMe checks behind the stop rule were also run with Claude Code: GPS jitter in harbour, tracker sleeps, where the other stops are, which trips are too fast, and ferry legs against the timetable.
- Last night's prep queries (`data_pack/prep/followme_queries.sql`, DuckDB CLI) were AI-assisted too.
