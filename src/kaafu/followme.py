"""FollowMe boat pings to stops to trips (BUILD_PLAN 6.4).

Reads data/raw/followme_kaafu_aug2025.parquet (never committed) and writes
data/processed/observed_trips.csv (one row per boat trip between two project
islands) and data/processed/observed_pairs.csv (per island pair and speed
class). Island zones come from data/processed/island_zones.geojson (M1), or
circles around the islands.csv points if that file is missing.

Run `python -m kaafu.followme` for the development week (config.FOLLOWME_DEV_DAYS)
or `python -m kaafu.followme --month` for all of August 2025.
"""
import argparse
import time

import duckdb
import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

TRIP_COLUMNS = ["device", "from_key", "to_key", "depart", "arrive",
                "duration_min", "mean_speed_kmh", "speed_class"]
PAIR_COLUMNS = ["from_key", "to_key", "speed_class", "n_trips", "n_devices", "median_min",
                "p90_min", "trips_per_day", "first_hour", "last_hour"]
OTHER = -2      # a stop outside every island zone (resort, sandbank): ends a trip, starts none

# Last night's rough check (followme_check.txt: 1.2 km rule, full month), to compare against.
PREP_MEDIANS = {"K.Huraa": 16, "K.Maafushi": 29, "V.Felidhoo": 316, "ADh.Mahibadhoo": 233}


# ---------------------------------------------------------------------------
# Pings
# ---------------------------------------------------------------------------
def load_pings(path, days, utc_offset_h, max_gap_min, window_min):
    """Pings for days (first, last) of August, de-duplicated, clock shifted to local time.

    Each ping gets:
    - `kmh`: speed of the segment from the device's previous ping (straight
      line), null after a gap of more than `max_gap_min`;
    - `seg_kmh`: the same with no gap limit (60 m in a 50-minute tracker
      sleep is 0.07 km/h: the boat sat still);
    - `still_kmh`: displacement between the first and last ping within
      +-window_min/2 of it, over that time. Ping-to-ping speed is mostly GPS
      jitter for a moored boat; this isn't. Null if no other ping is that close;
    - `gap_s`: seconds since the previous ping.
    Devices are numbered (`dev`) to save memory; `devices` maps them back.
    """
    half_s = int(window_min * 30)
    con = duckdb.connect()
    con.execute(f"""
        CREATE TEMP TABLE raw AS
        SELECT device_id, ts + INTERVAL {int(utc_offset_h)} HOUR AS ts, lat, lon, speed
        FROM read_parquet('{path.as_posix()}')
        WHERE day BETWEEN {int(days[0])} AND {int(days[1])}""")
    n_raw = con.execute("SELECT count(*) FROM raw").fetchone()[0]
    con.execute(f"""
        CREATE TEMP TABLE pings AS
        WITH p AS (
            SELECT * FROM raw
            QUALIFY row_number() OVER (PARTITION BY device_id, ts ORDER BY lat, lon) = 1
        ), s AS (
            SELECT *, lag(lat) OVER w AS plat, lag(lon) OVER w AS plon,
                   epoch(ts - lag(ts) OVER w) AS gap_s,
                   first_value(lat) OVER c AS lat0, first_value(lon) OVER c AS lon0,
                   first_value(ts) OVER c AS t0,
                   last_value(lat) OVER c AS lat1, last_value(lon) OVER c AS lon1,
                   last_value(ts) OVER c AS t1
            FROM p
            WINDOW w AS (PARTITION BY device_id ORDER BY ts),
                   c AS (PARTITION BY device_id ORDER BY ts RANGE BETWEEN
                         INTERVAL {half_s} SECOND PRECEDING AND INTERVAL {half_s} SECOND FOLLOWING)
        )
        SELECT dense_rank() OVER (ORDER BY device_id) - 1 AS dev, device_id, ts, lat, lon,
               speed AS speed_kn, gap_s,
               CASE WHEN gap_s >= 1 THEN
                   2 * 6371 * asin(sqrt(pow(sin(radians(lat - plat) / 2), 2)
                       + cos(radians(plat)) * cos(radians(lat)) * pow(sin(radians(lon - plon) / 2), 2)))
                   / (gap_s / 3600) END AS seg_kmh,
               CASE WHEN t1 > t0 THEN
                   2 * 6371 * asin(sqrt(pow(sin(radians(lat1 - lat0) / 2), 2)
                       + cos(radians(lat0)) * cos(radians(lat1)) * pow(sin(radians(lon1 - lon0) / 2), 2)))
                   / (epoch(t1 - t0) / 3600) END AS still_kmh
        FROM s""")
    devices = con.execute("SELECT DISTINCT dev, device_id FROM pings ORDER BY dev").df()
    pings = con.execute(f"""
        SELECT dev, ts, lat, lon, speed_kn, seg_kmh, still_kmh, gap_s,
               CASE WHEN gap_s <= {int(max_gap_min) * 60} THEN seg_kmh END AS kmh
        FROM pings ORDER BY dev, ts""").df()
    pings["dev"] = pings["dev"].astype(np.int32)
    return pings, devices["device_id"].to_numpy(), n_raw


def knots_check(pings):
    """Median of (speed column x 1.852) / derived km/h over clearly moving segments."""
    moving = pings[pings["kmh"].between(5, 60) & (pings["speed_kn"] > 0)]
    return float((moving["speed_kn"] * 1.852 / moving["kmh"]).median())


# ---------------------------------------------------------------------------
# Island zones
# ---------------------------------------------------------------------------
def _metres(lat, lon, lat0, lon0):
    """Approximate distance in metres (equirectangular; fine over a few km)."""
    dy = (lat - lat0) * 110_574
    dx = (lon - lon0) * 111_320 * np.cos(np.radians(lat0))
    return np.hypot(dx, dy)


def _haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(a))


def load_zones(cfg, islands):
    """One zone polygon per islands.csv row, in the same order, and where it came from."""
    if cfg.ISLAND_ZONES_GEOJSON.exists():
        zones = gpd.read_file(cfg.ISLAND_ZONES_GEOJSON).to_crs(cfg.WGS84_CRS).set_index("island_key")
        source = cfg.ISLAND_ZONES_GEOJSON.name
    else:
        points = gpd.GeoSeries(gpd.points_from_xy(islands["harbour_lon"], islands["harbour_lat"]),
                               index=islands["island_key"], crs=cfg.WGS84_CRS).to_crs(cfg.UTM_CRS)
        radius = [cfg.ZONE_CIRCLE_LARGE_M if k in cfg.LARGE_ZONE_ISLANDS else cfg.ZONE_CIRCLE_M
                  for k in points.index]
        zones = gpd.GeoDataFrame(geometry=points.buffer(radius), crs=cfg.UTM_CRS).to_crs(cfg.WGS84_CRS)
        source = "circles (island_zones.geojson missing)"
    missing = sorted(set(islands["island_key"]) - set(zones.index))
    if missing:
        raise ValueError(f"no island zone for {missing}")
    return list(zones.geometry.reindex(islands["island_key"])), source


def zone_of(lat, lon, zones, ilat, ilon):
    """Index of the island zone containing each ping, -1 if none.

    Where zones overlap (Hulhumalé and Hulhulé share 98 ha), the nearer island
    point wins.
    """
    zone = np.full(len(lat), -1, dtype=np.int16)
    best = np.full(len(lat), np.inf)
    for k, geom in enumerate(zones):
        x0, y0, x1, y1 = geom.bounds
        cand = np.flatnonzero((lon >= x0) & (lon <= x1) & (lat >= y0) & (lat <= y1))
        inside = cand[shapely.contains_xy(geom, lon[cand], lat[cand])]
        d = _metres(lat[inside], lon[inside], ilat[k], ilon[k])
        nearer = d < best[inside]
        zone[inside[nearer]] = k
        best[inside[nearer]] = d[nearer]
    return zone


def nearest_island_m(lat, lon, ilat, ilon):
    near = np.full(len(lat), np.inf)
    for a, b in zip(ilat, ilon):
        np.minimum(near, _metres(lat, lon, a, b), out=near)
    return near


def boat_devices(pings, min_sea_share, sea_dist_m, min_islands):
    """Devices with enough pings far from every island and at least two islands visited."""
    sea_share = (pings["near_m"] > sea_dist_m).groupby(pings["dev"]).mean()
    n_islands = (pings[pings["zone"] >= 0].groupby("dev")["zone"].nunique()
                 .reindex(sea_share.index, fill_value=0))
    return sea_share.index[(sea_share >= min_sea_share) & (n_islands >= min_islands)].to_numpy()


# ---------------------------------------------------------------------------
# Stops and trips
# ---------------------------------------------------------------------------
def find_stops(pings, stop_kmh, stop_min):
    """Island stops and other stops, each with its first and last ping.

    A ping is still if the boat moved slower than `stop_kmh` since the
    previous ping (`seg_kmh`: catches tracker sleeps) or across the smoothing
    window (`still_kmh`: catches GPS jitter). Still time is the time since the
    previous ping, summed over still pings.

    Island stop: a visit (consecutive pings inside one island zone) with at
    least `stop_min` minutes of still time. Its first and last pings are where
    the boat entered and left the zone.

    Other stop: consecutive still pings outside every zone with at least
    `stop_min` minutes of still time: a resort, a sandbank, Thilafushi.

    `place` is the island index, or OTHER.
    """
    zone = pings["zone"].to_numpy()
    dev = pings["dev"].to_numpy()
    ts = pings["ts"].to_numpy()
    still = (pings["seg_kmh"].to_numpy() < stop_kmh) | (pings["still_kmh"].to_numpy() < stop_kmh)
    new_dev = np.r_[True, dev[1:] != dev[:-1]]
    seg_min = np.where(new_dev, 0.0, pings["gap_s"].to_numpy() / 60)

    new_visit = new_dev | np.r_[True, zone[1:] != zone[:-1]]
    visits = pd.DataFrame({"visit": np.cumsum(new_visit), "dev": dev, "place": zone, "ts": ts,
                           "still_min": np.where(new_visit, 0.0, seg_min) * still})
    visits = visits[visits["place"] >= 0].groupby("visit").agg(
        dev=("dev", "first"), place=("place", "first"),
        first_ts=("ts", "min"), last_ts=("ts", "max"), still_min=("still_min", "sum"))
    island = visits[visits["still_min"] >= stop_min]

    still_out = (zone < 0) & still
    new_run = new_dev | np.r_[True, still_out[1:] != still_out[:-1]]
    runs = pd.DataFrame({"run": np.cumsum(new_run), "dev": dev, "ts": ts, "still_min": seg_min})[still_out]
    other = runs.groupby("run").agg(dev=("dev", "first"), first_ts=("ts", "min"), last_ts=("ts", "max"),
                                    still_min=("still_min", "sum"))
    other = other[other["still_min"] >= stop_min].assign(place=OTHER)

    columns = ["dev", "place", "first_ts", "last_ts"]
    return pd.concat([island[columns], other[columns]], ignore_index=True)


def find_trips(stops, ilat, ilon, max_hours, max_kmh):
    """Trips between consecutive stops at two different islands of the same device.

    Departure is the last ping of the first stop (leaving its zone), arrival
    the first ping of the next (entering its zone), so times run zone edge to
    zone edge. A stop outside the zones (OTHER) breaks the chain. Trips
    over `max_hours` or faster than `max_kmh` in a straight line are dropped.
    """
    s = stops.sort_values(["dev", "first_ts"]).reset_index(drop=True)
    nxt = s.shift(-1)
    ok = (nxt["dev"] == s["dev"]) & (s["place"] >= 0) & (nxt["place"] >= 0) & (s["place"] != nxt["place"])
    trips = pd.DataFrame({"dev": s.loc[ok, "dev"].astype(np.int32),
                          "from_i": s.loc[ok, "place"].astype(int),
                          "to_i": nxt.loc[ok, "place"].astype(int),
                          "depart": s.loc[ok, "last_ts"],
                          "arrive": nxt.loc[ok, "first_ts"]})
    trips["duration_min"] = (trips["arrive"] - trips["depart"]).dt.total_seconds() / 60
    km = _haversine_km(ilat[trips["from_i"]], ilon[trips["from_i"]],
                       ilat[trips["to_i"]], ilon[trips["to_i"]])
    trips["mean_speed_kmh"] = km / (trips["duration_min"] / 60)
    too_long = trips["duration_min"] > max_hours * 60
    too_fast = ~too_long & (trips["mean_speed_kmh"] > max_kmh)
    dropped = {"over_max_hours": int(too_long.sum()), "over_max_kmh": int(too_fast.sum())}
    return trips[~too_long & ~too_fast].reset_index(drop=True), dropped


def speed_split(speeds, fallback, lo=10, hi=60, bin_kmh=2):
    """The dip between the ferry and speedboat humps of the trip-speed histogram.

    Takes the highest (3-bin smoothed) peak below `fallback` and the highest
    above it, and the lowest bin between them. The dip counts as clear if it
    is under 60% of the smaller peak; otherwise `fallback` is used.
    """
    counts, edges = np.histogram(speeds, bins=np.arange(lo, hi + bin_kmh, bin_kmh))
    smooth = np.convolve(counts, np.ones(3) / 3, mode="same")
    centres = (edges[:-1] + edges[1:]) / 2
    low = np.argmax(np.where(centres < fallback, smooth, -1))
    high = np.argmax(np.where(centres >= fallback, smooth, -1))
    dip = low + int(np.argmin(smooth[low:high + 1]))
    clear = low < dip < high and smooth[dip] < 0.6 * min(smooth[low], smooth[high])
    split = float(edges[dip + 1]) if clear else float(fallback)
    return split, clear, counts, edges


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
def trip_table(trips, keys, device_ids, hash_len):
    out = pd.DataFrame({
        "device": [d[:hash_len] for d in device_ids[trips["dev"]]],
        "from_key": keys[trips["from_i"]],
        "to_key": keys[trips["to_i"]],
        "depart": trips["depart"].dt.strftime("%Y-%m-%d %H:%M"),
        "arrive": trips["arrive"].dt.strftime("%Y-%m-%d %H:%M"),
        "duration_min": trips["duration_min"].round(1),
        "mean_speed_kmh": trips["mean_speed_kmh"].round(1),
        "speed_class": trips["speed_class"],
    })
    return out[TRIP_COLUMNS]


def pair_table(trips, keys, n_days):
    t = trips.assign(from_key=keys[trips["from_i"]], to_key=keys[trips["to_i"]],
                     hour=trips["depart"].dt.hour)
    pairs = t.groupby(["from_key", "to_key", "speed_class"]).agg(
        n_trips=("duration_min", "size"), n_devices=("dev", "nunique"),
        median_min=("duration_min", "median"), p90_min=("duration_min", lambda s: s.quantile(0.9)),
        first_hour=("hour", "min"), last_hour=("hour", "max")).reset_index()
    pairs["trips_per_day"] = pairs["n_trips"] / n_days
    pairs = pairs.round({"median_min": 1, "p90_min": 1, "trips_per_day": 2})
    return pairs.sort_values(["from_key", "to_key", "speed_class"])[PAIR_COLUMNS]


def summary(info, trips, keys, islands, days, split, clear, counts, edges):
    """The Step 2 'done when' checks, as text."""
    lines = [f"pings: {info['n_raw']:,} read, {info['n_pings']:,} after removing duplicates; "
             f"{info['n_devices']:,} devices, {info['n_boats']:,} boats ({info['boat_pings']:,} pings)",
             f"speed column x 1.852 / derived km/h (median, moving): {info['knots_ratio']:.3f} "
             f"(knots ~1 if the column is knots)",
             f"island zones: {info['zone_source']}",
             f"stops: {info['island_stops']:,} at islands, {info['other_stops']:,} elsewhere (break the chain)",
             f"trips between islands: {len(trips):,} kept; dropped {info['dropped']}"]

    gm = set(islands.loc[islands["role"] == "greater_male", "island_key"])
    origins = list(islands.loc[islands["role"] == "origin", "island_key"])
    t = trips.assign(from_key=keys[trips["from_i"]], to_key=keys[trips["to_i"]])
    in_gm = t[t["from_key"].isin(origins) & t["to_key"].isin(gm)]
    per_day = in_gm.groupby(in_gm["depart"].dt.day).size()
    per_day = per_day[per_day.index.to_series().between(*days)]
    lines.append(f"origin -> Greater Malé (Malé, Hulhumalé, Villimalé) trips: {len(in_gm):,}; per day "
                 f"min {per_day.min()} / median {per_day.median():.0f} / max {per_day.max()}")
    to_airport = t[t["from_key"].isin(origins) & (t["to_key"] == "K.Hulhulé")]
    lines.append(f"origin -> K.Hulhulé (airport) trips, not counted above: {len(to_airport):,}")

    n_days = days[1] - days[0] + 1
    by_origin = in_gm.groupby("from_key").agg(
        trips=("duration_min", "size"), median_min=("duration_min", "median"),
        fast_share=("speed_class", lambda s: (s == "fast").mean()))
    slow = in_gm[in_gm["speed_class"] == "slow"].groupby("from_key")["duration_min"].median()
    by_origin["per_day"] = by_origin["trips"] / n_days
    by_origin["slow_median"] = slow
    by_origin["prep_median"] = pd.Series(PREP_MEDIANS)
    by_origin = by_origin.sort_values("per_day", ascending=False)
    lines.append("origin -> Greater Malé by origin (prep = last night's month-wide median):")
    lines.append(f"  {'origin':<20}{'trips':>6}{'per day':>9}{'median':>8}{'slow med':>10}{'fast':>7}{'prep':>6}")
    for key, r in by_origin.iterrows():
        prep = "" if pd.isna(r["prep_median"]) else f"{r['prep_median']:.0f}"
        slow_med = "" if pd.isna(r["slow_median"]) else f"{r['slow_median']:.0f}"
        lines.append(f"  {key:<20}{r['trips']:>6.0f}{r['per_day']:>9.1f}{r['median_min']:>8.0f}"
                     f"{slow_med:>10}{r['fast_share']:>7.0%}{prep:>6}")
    missing = [k for k in origins if k not in by_origin.index]
    lines.append(f"origins with no trip to Greater Malé: {missing or 'none'}")

    lines.append(f"speed split: {split:.0f} km/h ({'dip in the histogram' if clear else 'no clear dip: config fallback'})")
    lines.append("trip speed histogram, origin -> Greater Malé (km/h: trips):")
    lines.append("  " + "  ".join(f"{edges[i]:.0f}-{edges[i + 1]:.0f}:{c}" for i, c in enumerate(counts)))
    return "\n".join(lines)


def main(cfg=None, month=False):
    """FollowMe pings -> observed_trips.csv and observed_pairs.csv.

    Steps: load pings (+5 h to local time, de-duplicated, smoothed speeds),
    tag each ping with its island zone, keep devices that behave like boats,
    find stops inside zones, join consecutive stops into trips, split trips
    into slow/fast at the speed-histogram dip, aggregate per island pair.
    month=False runs the development week only.
    """
    if cfg is None:
        from kaafu import config as cfg
    start = time.time()
    days = (1, cfg.FOLLOWME_DAYS) if month else cfg.FOLLOWME_DEV_DAYS
    n_days = cfg.FOLLOWME_DAYS if month else days[1] - days[0] + 1
    print(f"FollowMe days {days[0]}-{days[1]} Aug 2025 ({'month' if month else 'development week'})")

    islands = pd.read_csv(cfg.ISLANDS_CSV, encoding=cfg.READ_ENCODING)
    keys = islands["island_key"].to_numpy()
    ilat, ilon = islands["harbour_lat"].to_numpy(), islands["harbour_lon"].to_numpy()
    zones, zone_source = load_zones(cfg, islands)

    pings, device_ids, n_raw = load_pings(cfg.FOLLOWME_PARQUET, days, cfg.FOLLOWME_UTC_OFFSET_H,
                                          cfg.PING_MAX_GAP_MIN, cfg.SPEED_WINDOW_MIN)
    info = {"n_raw": n_raw, "n_pings": len(pings), "n_devices": len(device_ids),
            "knots_ratio": knots_check(pings), "zone_source": zone_source}
    pings = pings.drop(columns="speed_kn")
    print(f"  loaded in {time.time() - start:.0f} s")

    lat, lon = pings["lat"].to_numpy(), pings["lon"].to_numpy()
    pings["zone"] = zone_of(lat, lon, zones, ilat, ilon)
    pings["near_m"] = nearest_island_m(lat, lon, ilat, ilon)
    boats = boat_devices(pings, cfg.BOAT_MIN_SEA_SHARE, cfg.BOAT_SEA_DIST_M, cfg.BOAT_MIN_ISLANDS)
    pings = pings[pings["dev"].isin(boats)].reset_index(drop=True)
    info.update(n_boats=len(boats), boat_pings=len(pings))
    print(f"  zones and boats in {time.time() - start:.0f} s")

    stops = find_stops(pings, cfg.STOP_SPEED_KMH, cfg.STOP_MIN)
    info.update(island_stops=int((stops["place"] >= 0).sum()), other_stops=int((stops["place"] == OTHER).sum()))
    trips, info["dropped"] = find_trips(stops, ilat, ilon, cfg.MAX_TRIP_HOURS, cfg.MAX_BOAT_KMH)

    gm = islands.loc[islands["role"] == "greater_male", "island_key"]
    origins = islands.loc[islands["role"] == "origin", "island_key"]
    in_gm = np.isin(keys[trips["from_i"]], origins) & np.isin(keys[trips["to_i"]], gm)
    split, clear, counts, edges = speed_split(trips.loc[in_gm, "mean_speed_kmh"], cfg.SPEED_CLASS_SPLIT_KMH)
    trips["speed_class"] = np.where(trips["mean_speed_kmh"] < split, "slow", "fast")

    out_trips = trip_table(trips, keys, device_ids, cfg.DEVICE_HASH_LEN)
    pairs = pair_table(trips, keys, n_days)
    cfg.OBSERVED_TRIPS_CSV.parent.mkdir(parents=True, exist_ok=True)
    out_trips.to_csv(cfg.OBSERVED_TRIPS_CSV, index=False, encoding=cfg.WRITE_ENCODING)
    pairs.to_csv(cfg.OBSERVED_PAIRS_CSV, index=False, encoding=cfg.WRITE_ENCODING)

    print(summary(info, trips, keys, islands, days, split, clear, counts, edges))
    print(f"wrote {cfg.OBSERVED_TRIPS_CSV.relative_to(cfg.ROOT)} ({len(out_trips):,} trips) and "
          f"{cfg.OBSERVED_PAIRS_CSV.relative_to(cfg.ROOT)} ({len(pairs):,} pairs) "
          f"in {time.time() - start:.0f} s")
    return out_trips, pairs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--month", action="store_true",
                        help="all of August 2025 (default: the development week)")
    main(month=parser.parse_args().month)
