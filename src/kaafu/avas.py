"""Taxi speed and unserved share by pickup zone and hour (BUILD_PLAN 6.5)."""
from __future__ import annotations

import duckdb
import pandas as pd

from . import config as C

# Pickup boxes (lat_min, lat_max, lon_min, lon_max). Order matters: airport before Hulhumalé.
ZONES = {
    "male": (4.160, 4.185, 73.495, 73.525),
    "airport": (4.170, 4.205, 73.515, 73.535),
    "hulhumale": (4.200, 4.250, 73.525, 73.560),
}
TERMINAL_ZONE = {"K.Malé": "male", "K.Hulhulé": "airport", "K.Hulhumalé": "hulhumale"}


def raw_path():
    return next(iter(C.RAW.rglob("avas_rides_aug_sep_2026.csv")), None)


def _zone_sql(lat: str, lon: str) -> str:
    cases = " ".join(f"WHEN {lat} BETWEEN {a} AND {b} AND {lon} BETWEEN {c} AND {d} THEN '{z}'"
                     for z, (a, b, c, d) in ZONES.items())
    return f"CASE {cases} ELSE 'other' END"


def rides(path=None) -> pd.DataFrame:
    """Rides with hour, zone, completed flag and speed. Completed = not expired, with time and distance."""
    path = path or raw_path()
    q = f"""
        SELECT *, hour(CAST(date_started AS TIMESTAMP)) AS hour,
               {_zone_sql('pickup_lat', 'pickup_lng')} AS zone,
               status NOT ILIKE '%expired%' AND status NOT ILIKE '%cancel%'
                   AND time_sec > 0 AND distance_km > 0 AS completed,
               distance_km / (time_sec / 3600.0) AS speed_kmh
        FROM read_csv_auto('{path}', header=true)
    """
    return duckdb.sql(q).df()


def hourly(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """avas_hourly.csv: zone, hour, completed, expired, expired_share, median_speed_kmh."""
    df = rides() if df is None else df
    df = df.assign(expired=df["status"].str.contains("expired", case=False, na=False))
    both = pd.concat([df, df.assign(zone="all")])
    g = both.groupby(["zone", "hour"])
    out = pd.DataFrame({
        "completed": g["completed"].sum(),
        "expired": g["expired"].sum(),
        "median_speed_kmh": both[both["completed"] & both["speed_kmh"].between(1, 80)]
        .groupby(["zone", "hour"])["speed_kmh"].median(),
    }).reset_index()
    out["expired_share"] = out["expired"] / (out["completed"] + out["expired"]).clip(lower=1)
    out = out[out["zone"] != "other"]
    return out[["zone", "hour", "completed", "expired", "expired_share", "median_speed_kmh"]]


def od_median_minutes(df: pd.DataFrame, a: tuple[float, float], b: tuple[float, float]) -> pd.Series:
    """Median drive minutes per hour for completed rides from within TAXI_MATCH_M of a to b."""
    from .geo import haversine_m

    done = df[df["completed"]]
    near_a = haversine_m(done[["pickup_lat", "pickup_lng"]].to_numpy(), [a]) <= C.TAXI_MATCH_M
    near_b = haversine_m(done[["dropoff_lat", "dropoff_lng"]].to_numpy(), [b]) <= C.TAXI_MATCH_M
    sel = done[near_a & near_b]
    g = sel.groupby("hour")["time_sec"]
    med = g.median() / 60
    return med[g.size() >= C.TAXI_MIN_RIDES]
