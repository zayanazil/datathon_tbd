"""FollowMe GPS pings -> stops -> trips -> observed boat times (BUILD_PLAN 6.4).

IMEIs are replaced by a short hash as soon as the data is loaded and never written out.
"""
from __future__ import annotations

import hashlib

import duckdb
import numpy as np
import pandas as pd

from . import config as C
from .geo import haversine_m, island_zones
from .load import load_islands

CACHE = C.RAW / "followme_area.parquet"


def extract(src=None) -> pd.DataFrame:
    """Pings inside FOLLOWME_BBOX from the Kaafu subset parquet or the 31 daily CSVs, cached as Parquet."""
    if CACHE.exists():
        return pd.read_parquet(CACHE)
    if src is None:
        src = next(iter(C.RAW.rglob("followme_kaafu*.parquet")), None) or C.RAW / "FollowMe_august_2025" / "*.csv"
    reader = f"read_parquet('{src}')" if str(src).endswith(".parquet") else \
        f"read_csv_auto('{src}', header=true, union_by_name=true)"
    lat0, lat1, lon0, lon1 = C.FOLLOWME_BBOX
    df = duckdb.sql(f"""
        SELECT DISTINCT imei, CAST(device_date AS TIMESTAMP) AS device_date, latitude, longitude, speed
        FROM {reader}
        WHERE latitude BETWEEN {lat0} AND {lat1} AND longitude BETWEEN {lon0} AND {lon1}
    """).df()
    df = clean(df)
    df.to_parquet(CACHE, index=False)
    return df


def device_hash(imei) -> str:
    return hashlib.sha256(str(imei).encode()).hexdigest()[:10]


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Hash IMEIs, local clock, drop zero coordinates and duplicates, derive speed from positions."""
    df = df.assign(device=df["imei"].map(device_hash)).drop(columns="imei")
    df["time"] = pd.to_datetime(df["device_date"]) + pd.Timedelta(hours=C.FOLLOWME_UTC_OFFSET_H)
    df = df[(df["latitude"] != 0) & (df["longitude"] != 0)]
    df = df.drop_duplicates(["device", "time"]).sort_values(["device", "time"]).reset_index(drop=True)
    same = df["device"].eq(df["device"].shift())
    prev = df[["latitude", "longitude"]].shift().to_numpy()
    dist = np.where(same, haversine_m(df[["latitude", "longitude"]].to_numpy(),
                                      np.nan_to_num(prev)), np.nan)
    gap_h = df["time"].diff().dt.total_seconds().where(same) / 3600
    df["speed_kmh"] = (dist / 1000) / gap_h.where(gap_h > 0)
    return df.drop(columns="device_date")


def tag_zones(df: pd.DataFrame) -> pd.DataFrame:
    import geopandas as gpd

    zones = island_zones()
    pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["longitude"], df["latitude"]), crs="EPSG:4326")
    hit = gpd.sjoin(pts, zones[["island_key", "geometry"]], predicate="within", how="left")
    hit = hit[~hit.index.duplicated()]
    return df.assign(zone=hit["island_key"].to_numpy())


def keep_boats(df: pd.DataFrame, min_water_share: float = 0.6) -> pd.DataFrame:
    """Devices whose moving pings are mostly on water (outside every island zone)."""
    moving = df[df["speed_kmh"] > 5]
    share = moving["zone"].isna().groupby(moving["device"]).mean()
    return df[df["device"].isin(share[share >= min_water_share].index)]


def stops(df: pd.DataFrame) -> pd.DataFrame:
    """Runs of slow pings lasting STOP_MIN, labelled by island zone ('other' if outside the project)."""
    slow = df["speed_kmh"].fillna(0) < C.STOP_SPEED_KMH
    label = np.where(slow, df["zone"].fillna("other"), None)
    run = (pd.Series(label).ne(pd.Series(label).shift()) | df["device"].ne(df["device"].shift())).cumsum()
    g = df.assign(label=label, run=run.to_numpy())[slow].groupby("run")
    s = g.agg(device=("device", "first"), place=("label", "first"), start=("time", "min"), end=("time", "max"))
    s = s[(s["end"] - s["start"]).dt.total_seconds() >= C.STOP_MIN * 60]
    return s.sort_values(["device", "start"]).reset_index(drop=True)


def trips(st: pd.DataFrame) -> pd.DataFrame:
    """Consecutive stops at two different project islands. A stop elsewhere ends a trip."""
    project = set(load_islands()["island_key"])
    nxt = st.shift(-1)
    ok = (st["device"] == nxt["device"]) & st["place"].isin(project) & nxt["place"].isin(project) \
        & (st["place"] != nxt["place"])
    t = pd.DataFrame({"device": st["device"], "from_key": st["place"], "to_key": nxt["place"],
                      "depart": st["end"], "arrive": nxt["start"]})[ok]
    t["duration_min"] = (t["arrive"] - t["depart"]).dt.total_seconds() / 60
    pts = load_islands().set_index("island_key")[["harbour_lat", "harbour_lon"]]
    km = haversine_m(pts.loc[t["from_key"]].to_numpy(), pts.loc[t["to_key"]].to_numpy()) / 1000
    t["mean_speed_kmh"] = km / (t["duration_min"] / 60)
    t = t[(t["mean_speed_kmh"] <= C.MAX_BOAT_KMH) & (t["duration_min"] <= C.MAX_TRIP_HOURS * 60)
          & (t["duration_min"] > 0)]
    split = speed_split(t["mean_speed_kmh"])
    t["speed_class"] = np.where(t["mean_speed_kmh"] < split, "slow", "fast")
    return t.reset_index(drop=True)


def speed_split(speeds: pd.Series, lo: float = 15, hi: float = 45, default: float = 30) -> float:
    """The dip in the trip-speed histogram between ferry-like and speedboat-like trips."""
    if len(speeds) < 30:
        return default
    counts, edges = np.histogram(speeds, bins=np.arange(0, 82, 2))
    smooth = np.convolve(counts, np.ones(3) / 3, mode="same")
    centres = (edges[:-1] + edges[1:]) / 2
    window = (centres >= lo) & (centres <= hi)
    return float(centres[window][np.argmin(smooth[window])])


def pairs(t: pd.DataFrame) -> pd.DataFrame:
    n_days = max(t["depart"].dt.normalize().nunique(), 1)
    g = t.groupby(["from_key", "to_key", "speed_class"])
    out = g.agg(n_trips=("duration_min", "size"), n_devices=("device", "nunique"),
                median_min=("duration_min", "median"), p90_min=("duration_min", lambda s: s.quantile(0.9)),
                first_hour=("depart", lambda s: int(s.dt.hour.quantile(0.05))),
                last_hour=("depart", lambda s: int(s.dt.hour.quantile(0.95)))).reset_index()
    out["trips_per_day"] = out["n_trips"] / n_days
    return out[["from_key", "to_key", "speed_class", "n_trips", "n_devices", "median_min", "p90_min",
                "trips_per_day", "first_hour", "last_hour"]]


def run(src=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """observed_trips.csv and observed_pairs.csv."""
    pings = keep_boats(tag_zones(extract(src)))
    t = trips(stops(pings))
    return t, pairs(t)
