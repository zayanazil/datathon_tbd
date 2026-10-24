# M2 movement data (FollowMe and Avas): status

**Owner:** Eish (M2) · **Branch:** `m2-movement` · **Last updated:** 24 Oct 2026, after Step 1 (`avas_hourly.csv`)

This file says what M2 has built, what it gives the rest of the team, and what comes next. It's updated after each major step. Team: M1 Zayan (GIS), M2 Eish (movement), M3 Al (network), M4 Saroof (lead, dashboard).

## Status at a glance

| Step | Status |
|---|---|
| 1. `avas.py` → `avas_hourly.csv` | Done |
| 2. `followme.py` on one week (4–10 Aug 2025) | Next |
| 3. Full month → `observed_trips.csv`, `observed_pairs.csv` | Not started |
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

- **`observed_pairs.csv` comes in Steps 2–3.** A rough one-week version will be pushed as soon as Step 2 works, so you can wire up the `observed` switch early; the full month replaces it.
- It will use `island_key`s at both ends, with `K.Malé` / `K.Hulhumalé` (not terminal IDs) for Greater Malé, as you asked. Columns exactly as BUILD_PLAN §4.

### Saroof (M4): config and merge

- **`config.py` on `main`** is Zayan's latest, unchanged (commit `b6efe25`).
- **`m2-movement` adds M2 settings to `config.py`**, as new lines only, so it merges cleanly:
  - FollowMe: `PING_MAX_GAP_MIN`, `BOAT_MIN_SEA_SHARE`, `BOAT_SEA_DIST_M`, `BOAT_MIN_ISLANDS`, `SPEED_CLASS_SPLIT_KMH`, `DEVICE_HASH_LEN`, `FOLLOWME_DAYS`, `FOLLOWME_DEV_DAYS`.
  - Avas: `AVAS_WEEKDAYS`, `AVAS_ZONES`, `AVAS_MIN_RIDES`, `AVAS_SPEED_SAME_ZONE`.
- **README:** please link this file next to `m3_claude.md`. The AI-assisted list is at the bottom.

## How to run

From the repo root, with `data/raw/avas/avas_rides_aug_sep_2026.csv` in place (not committed):

```powershell
$env:PYTHONPATH = "src"
python -m kaafu.avas                                   # data/processed/avas_hourly.csv
python -m kaafu.avas --plot plans/review/avas_zones.png   # also a pickup scatter with the zone boxes
```

`main()` takes an optional `cfg` argument, which defaults to `kaafu.config`. It prints the checks below every run and stops with an error unless the table has 96 rows and no blanks.

## Files (M2 owns these)

| File | What it does |
|---|---|
| `src/kaafu/avas.py` | Avas requests to the hourly table: Sun–Thu filter, pickup and dropoff zones from `config.AVAS_ZONES`, counts and unserved share by zone × hour, same-zone median speed with fallbacks, checks. |
| `src/kaafu/followme.py` | Step 2 (not written yet). |

## Outputs in `data/processed/`

| File | Rows | Notes |
|---|---|---|
| `avas_hourly.csv` | 96 | 4 zones × 24 hours. Counts use every request; speed uses completed same-zone rides. |

## Step 1 numbers (Avas, Sun–Thu, Aug–Sep 2026)

- **Requests:** 266,410 Sun–Thu requests, with only 2 pickups outside the zone boxes (dropped). By zone: Hulhumalé 133,250, Malé 125,318, airport 7,840.
- **Unserved share overall:** 7.7%. Worst hours: 07:00 (17.9%), 18:00 (15.9%), 17:00 and 08:00 (15.2%).
- **Worst zone-hour:** airport at 23:00, 66.7% unserved.
- **Commuter pattern:** taxis are hardest to get in Hulhumalé in the morning (22.9% unserved at 07:00) and in Malé in the evening (24.0% at 18:00).

## Decisions and assumptions (for the limits slide)

- **Day group:** Sunday–Thursday only (`AVAS_WEEKDAYS`), because the build day is Wednesday.
- **Zones:** pickup boxes from M2_movement.md, checked on a scatter plot. The airport box's top edge is 4.205 instead of 4.207, so 360 pickups on Hulhumalé's southern tip count as Hulhumalé. Boxes are checked in order male → airport → hulhumale.
- **Same-zone speed:** explained under Zayan's section above.
- **Fallbacks:** a zone-hour with fewer than 20 same-zone rides (`AVAS_MIN_RIDES`) takes the zone's all-day median. None of the 96 zone-hours had zero requests, so no unserved share was filled.

## Limits found in the Avas data

- **Only rides of 2 km or more and 5 minutes or more** are in the file (minimum `distance_km` 2.025, minimum `time_sec` 300). Short hops inside Malé are missing.
- **Ride times look modelled, not measured.** Ride time is almost exactly 70 s + 85 s per km of `distance_km`: correlation 0.976, with a spread of about 39 s. Hourly speeds barely change (Malé 28.3–29.1 km/h), so the data shows no rush-hour traffic. Only the unserved share varies through the day.
- **Avas covers Aug–Sep 2026; FollowMe is Aug 2025.**

## Next

1. **Step 2:** `followme.py` on 4–10 Aug 2025. It will use Zayan's `island_zones.geojson`, which has 27 OSM outlines buffered 300 m. Hulhumalé and Hulhulé overlap by 98 ha; a stop in the overlap goes to the nearer island point. Push a rough `observed_pairs.csv` for Al.
2. **Step 3:** full month, speed classes, then the final `observed_trips.csv` and `observed_pairs.csv`.
3. **Step 4:** scheduled against observed for Felidhoo and Mahibadhoo, the speedboat story, busiest links, and the limits.

## AI-assisted (for the README)

- `src/kaafu/avas.py` and the M2 settings in `src/kaafu/config.py` were written with Claude Code: zone assignment, the hourly table with fallbacks, checks, and the zone scatter.
- The Avas data checks behind the same-zone speed decision were also run with Claude Code: speed against distance, pickup × dropoff zone counts, and the airport-box edge.
