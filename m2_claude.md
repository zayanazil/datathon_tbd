# M2 movement data (FollowMe and Avas): status

**Owner:** Eish (M2) · **Branch:** `m2-movement` · **Last updated:** 24 Oct 2026, after Step 3 (full-month `observed_trips.csv` and `observed_pairs.csv`)

This file says what M2 has built, what it gives the rest of the team, and what comes next. It's updated after each major step. Team: M1 Zayan (GIS), M2 Eish (movement), M3 Al (network), M4 Saroof (lead, dashboard).

## Status at a glance

| Step | Status |
|---|---|
| 1. `avas.py` → `avas_hourly.csv` | Done |
| 2. `followme.py` on one week (4–10 Aug 2025) | Done |
| 3. Full month → `observed_trips.csv`, `observed_pairs.csv` | Done. These replace the one-week files, with the same columns. |
| 4. Validation numbers and limits for slides 4–5 | Mostly done (below); slide wording next |

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
- **Map:** your `observed_trips_layer` reads `observed_pairs.csv` as is. The columns, the `slow`/`fast` labels and the `n_trips ≥ 5` filter all match.

### Al (M3): observed boat times

- **`data/processed/observed_pairs.csv` is final (all of August 2025).**
  - 395 rows: 194 have `n_trips ≥ 5`, 72 of them `slow`. Columns exactly as BUILD_PLAN §4.
  - `trips_per_day` = `n_trips / 31`.
- **Keys:** `island_key`s at both ends, with `K.Malé` / `K.Hulhumalé` / `K.Villimalé` / `K.Hulhulé` for Greater Malé (not terminal IDs).
- **`speed_class`:** `slow` (ferry-like) is below **26 km/h** straight-line average, `fast` (speedboat-like) is at or above it. The split is the dip in the month's trip-speed histogram: ferries peak at 12–16 km/h, speedboats at 44–54.
- **Pairs are legs between consecutive stops**, which matches how `connections.csv` is built.
  - A ferry calling at an island for less than 10 minutes isn't seen as stopping there, so that pair spans two timetable legs (e.g. `V.Keyodhoo → K.Malé`).
  - Such pairs won't match a timetable leg, so your replace-by-pair step will just skip them.
- **Times run from zone edge to zone edge** (island outline + 300 m), so they are a few minutes shorter than dock-to-dock.
- **How well slow medians match the timetable:** see "Scheduled against observed" below. For the 28 CFN legs with at least 5 slow trips, the median gap is 5 min.
- **Careful with a few legs.** `slow` also catches cargo dhonis and other slow boats, not only the public ferry. Some legs with ≥ 5 slow trips are much slower than scheduled:

  | Leg | Observed slow | Scheduled |
  |---|---|---|
  | Malé → Himmafushi | 74 min (22 trips) | 40 |
  | Gaafaru → Kaashidhoo | 149 (9) | 90 |
  | Malé → Gaafaru | 271 (8) | 200 |
  | Maafushi → Guraidhoo | 55 (7) | 20 |
  | Guraidhoo → Maafushi | 38 (8) | 20 |
  | Mahibadhoo → Malé | 297 (13) | 260 |

  If you replace every slow median with `n_trips ≥ 5`, those legs get slower than the timetable. You might keep the scheduled time where the observed one is much longer, e.g. more than 1.5×. Your call.
- **Fast pairs, for synthetic speedboat departures:** four origin pairs into Greater Malé have `fast` `trips_per_day ≥ 5`, all to `K.Malé`:

  | From | Trips a day | Median min | Hours seen |
  |---|---|---|---|
  | K.Thulusdhoo | 14.6 | 32 | 06–23 |
  | K.Dhiffushi | 7.5 | 47 | 01–18 |
  | K.Himmafushi | 7.3 | 18 | 05–23 |
  | AA.Thoddoo | 5.4 | 73 | 05–23 |
- **`observed_trips.csv`** (10,975 trips) has `device` as an 8-character hash only, for map lines.

### Saroof (M4): config and merge

- **`config.py` on `main`** is Zayan's latest, unchanged (commit `b6efe25`). It's identical on `zayan` and `m3-network`.
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
python -m kaafu.followme --month    # all of August 2025 (~25 s): the committed outputs
python -m kaafu.followme            # development week, 4-10 Aug 2025 (~5 s)
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
| `observed_trips.csv` | 10,975 | All of August 2025. One row per boat trip between two project islands; `device` is 8 characters of the md5 hash. |
| `observed_pairs.csv` | 395 | All of August 2025. Per `from_key`, `to_key`, `speed_class`. |

## Step 1 numbers (Avas, Sun–Thu, Aug–Sep 2026)

- **Requests:** 266,410 Sun–Thu requests, with only 2 pickups outside the zone boxes (dropped). By zone: Hulhumalé 133,250, Malé 125,318, airport 7,840.
- **Unserved share overall:** 7.7%. Worst hours: 07:00 (17.9%), 18:00 (15.9%), 17:00 and 08:00 (15.2%).
- **Worst zone-hour:** airport at 23:00, 66.7% unserved.
- **Commuter pattern:** taxis are hardest to get in Hulhumalé in the morning (22.9% unserved at 07:00) and in Malé in the evening (24.0% at 18:00).

## Step 3 numbers (FollowMe, all of August 2025)

- **Pings:**
  - 9,922,162 read, 9,846,532 after removing 75,630 exact duplicates. That matches `followme_check.txt`.
  - 1,372 devices, of which 997 are boats (8.16 M pings).
- **Speed column:** × 1.852 ÷ derived km/h = 0.952, so it's knots.
- **Trips:**
  - 10,975 trips between project islands.
  - **Origin → Greater Malé** (Malé, Hulhumalé, Villimalé): 2,655 trips, 61–114 a day (median 85). Another 274 go to the airport (Hulhulé).
  - Every one of the 23 origin islands has at least one trip; Omadhoo has the fewest (2) and Bodufolhudhoo 4.
- **Busiest origins into Greater Malé:**

  | Origin | Trips a day | Median min | Fast | Slow median |
  |---|---|---|---|---|
  | K.Thulusdhoo | 17.4 | 33 | 87% | 99 |
  | K.Himmafushi | 9.6 | 20 | 78% | 46 |
  | K.Dhiffushi | 9.5 | 49 | 88% | 155 |
  | K.Maafushi | 5.9 | 48 | 69% | 122 |
  | AA.Thoddoo | 5.8 | 73 | 94% | 267 |
  | K.Huraa | 4.9 | 23 | 86% | 65 |

- **The speedboat story (findings slide):** most boats from the islands near Malé are speedboats. 74–88% of trips from Thulusdhoo, Himmafushi, Dhiffushi, Huraa and Gulhi are fast. From Maafushi, the public ferry takes 84–90 min to Malé, but the median observed trip (mostly fast) is 48 min, and the fast trips alone take 41.
- **Last night's rough check (`followme_check.txt`) isn't a benchmark for the islands near Malé.**
  - It counted any boat within 1.2 km of an island point, so resort speedboats passing Huraa or Himmafushi were included.
  - Its Huraa → Malé median of 16 min means about 75 km/h over 20 km; it had 24.5 trips a day, against our 4.9.

## Scheduled against observed (Step 4 validation)

CFN timetable legs (`ferry_timetable.csv`, scheduled minutes) against the observed `slow` median for the same pair, August 2025:

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
| Malé → Mahibadhoo | 305 | 250 | 270 (23) | 111 (68) |
| Mahibadhoo → Malé | 305 | 260 | 297 (13) | 105 (73) |

- **Agreement:** of the 52 CFN legs, 28 have at least 5 slow trips, and their median gap from the schedule is **5 min**. The Villimalé ferry (8 min) matches almost exactly.
- **Slower than scheduled:** the legs listed in Al's section above, where slow cargo boats are mixed into the `slow` class.
- **Whole routes, for the slides:** the guide's "Felidhoo → Malé 325 min" is the whole of route 306, through Thinadhoo, Fulidhoo and Maafushi. Observed it splits into legs:
  - Felidhoo → Thinadhoo: 10 min observed against 10 scheduled.
  - Maafushi → Malé: 84 against 90.
  - Fulidhoo → Maafushi and Thinadhoo → Fulidhoo have too few slow trips (1–2) to check.

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
  - Dropped: 84 trips over 6 h, and 1,865 faster than 80 km/h straight-line. Only 15 of the fast ones involve an origin island; the rest are Greater Malé hops between touching zones (Malé↔Hulhulé, Hulhumalé↔Hulhulé).
- **Speed class:** the split is the histogram dip, 26 km/h for the month. 28 km/h (`SPEED_CLASS_SPLIT_KMH`) is the fallback if there's no clear dip.
- **Avas:**
  - **Day group:** Sunday–Thursday only (`AVAS_WEEKDAYS`), because the build day is Wednesday.
  - **Zones:** pickup boxes from M2_movement.md, checked on a scatter plot. The airport box's top edge is 4.205 instead of 4.207, so 360 pickups on Hulhumalé's southern tip count as Hulhumalé. Boxes are checked in order male → airport → hulhumale.
  - **Same-zone speed:** explained under Zayan's section above.
  - **Fallbacks:** a zone-hour with fewer than 20 same-zone rides (`AVAS_MIN_RIDES`) takes the zone's all-day median. None of the 96 zone-hours had zero requests, so no unserved share was filled.

## Limits found in the FollowMe data

- **Trips are boat movements, not passengers.** Only boats with a FollowMe tracker are seen, and boat data is from Aug 2025 while the timetable is 2026.
- **"Slow" isn't only the public ferry:** cargo dhonis and other slow boats are in the same class.
- **Short stops are missed:** stops shorter than 10 minutes don't count, so quick speedboat drop-offs are merged into a longer trip or lost.
- **Times are zone edge to zone edge**, a few minutes shorter than dock-to-dock.

## Limits found in the Avas data

- **Only rides of 2 km or more and 5 minutes or more** are in the file (minimum `distance_km` 2.025, minimum `time_sec` 300). Short hops inside Malé are missing.
- **Ride times look modelled, not measured.** Ride time is almost exactly 70 s + 85 s per km of `distance_km`: correlation 0.976, with a spread of about 39 s. Hourly speeds barely change (Malé 28.3–29.1 km/h), so the data shows no rush-hour traffic. Only the unserved share varies through the day.
- **Avas covers Aug–Sep 2026; FollowMe is Aug 2025.**

## Next

1. **Slides 4–5 with Al:**
   - the method line "pings → stops → trips";
   - the speedboat story;
   - the scheduled-against-observed table above;
   - the limits.
2. **Rerun if needed:** if Zayan changes `island_zones.geojson`, run `python -m kaafu.followme --month` again and push both files.

## AI-assisted (for the README)

- `src/kaafu/avas.py` and the M2 settings in `src/kaafu/config.py` were written with Claude Code: zone assignment, the hourly table with fallbacks, checks, and the zone scatter.
- The Avas data checks behind the same-zone speed decision were also run with Claude Code: speed against distance, pickup × dropoff zone counts, and the airport-box edge.
- `src/kaafu/followme.py` was written with Claude Code: DuckDB loading with the +5 h shift, de-duplication, segment and smoothed speeds; island zone per ping; boat filter; stop and trip detection; speed-class split; output tables and checks.
- The FollowMe checks behind the stop rule and the validation table were also run with Claude Code: GPS jitter in harbour, tracker sleeps, where the other stops are, which trips are too fast, and timetable legs against observed medians.
- Last night's prep queries (`data_pack/prep/followme_queries.sql`, DuckDB CLI) were AI-assisted too.
