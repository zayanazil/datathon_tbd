"""Terminals, island zones and map layers (M1)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import config as C
from .load import load_islands, load_raw_csv

R_EARTH_M = 6_371_000

# Start set from BUILD_PLAN section 4. Jetty NO5 and Maafannu coordinates are estimates
# until rtl_bus_stops.csv is in data/raw/; terminals() then replaces them by stop code.
_TERMINALS = [
    # terminal_id, name, island_key, lat, lon, bus_stop_code, location_quality
    # The four ferry terminals: M1's coordinates from the RTL bus stops (data/processed/terminals.csv on main).
    ("T_MALE_NORTH", "Jetty NO5", "K.Malé", 4.178784, 73.513422, "1008", "bus_stop"),
    ("T_MALE_WEST", "Maafannu Ferry Terminal", "K.Malé", 4.172281, 73.502060, "1101", "bus_stop"),
    ("T_HULHUMALE", "Hulhumalé Ferry Terminal", "K.Hulhumalé", 4.216739, 73.537853, "507", "bus_stop"),
    ("T_VILLIMALE", "Villimale Ferry Terminal", "K.Villimalé", 4.175107, 73.486942, "1301", "bus_stop"),
    ("T_AIRPORT", "Velana Airport jetty", "K.Hulhulé", 4.19183, 73.52910, "", "estimated"),
]


def haversine_m(a, b) -> np.ndarray:
    """Great-circle metres between arrays of (lat, lon) pairs."""
    a, b = np.radians(np.atleast_2d(a)), np.radians(np.atleast_2d(b))
    dlat, dlon = b[:, 0] - a[:, 0], b[:, 1] - a[:, 1]
    h = np.sin(dlat / 2) ** 2 + np.cos(a[:, 0]) * np.cos(b[:, 0]) * np.sin(dlon / 2) ** 2
    return 2 * R_EARTH_M * np.arcsin(np.sqrt(h))


def terminals() -> pd.DataFrame:
    df = pd.DataFrame(_TERMINALS, columns=["terminal_id", "name", "island_key", "lat", "lon",
                                           "bus_stop_code", "location_quality"])
    df["walk_to_stop_min"] = 0.0
    stops = load_raw_csv("rtl_bus_stops.csv")
    if stops is not None:
        code_col = next(c for c in stops.columns if c.lower() in ("stop_code", "code", "stop_id"))
        lat_col = next(c for c in stops.columns if c.lower() in ("lat", "latitude", "stop_lat"))
        lon_col = next(c for c in stops.columns if c.lower() in ("lon", "lng", "longitude", "stop_lon"))
        by_code = stops.assign(_code=stops[code_col].astype(str)).drop_duplicates("_code").set_index("_code")
        for i, row in df.iterrows():
            if row["bus_stop_code"] in by_code.index and row["location_quality"] == "estimated":
                df.loc[i, ["lat", "lon"]] = by_code.loc[row["bus_stop_code"], [lat_col, lon_col]].to_numpy(float)
                df.loc[i, "location_quality"] = "bus_stop"
    return df


def stop_points() -> pd.DataFrame:
    """lat/lon for every stop_id: island harbour points plus terminals."""
    isl = load_islands().rename(columns={"island_key": "stop_id", "harbour_lat": "lat", "harbour_lon": "lon"})
    t = terminals().rename(columns={"terminal_id": "stop_id"})
    return pd.concat([isl[["stop_id", "lat", "lon"]], t[["stop_id", "lat", "lon"]]]).set_index("stop_id")


def stop_island() -> dict[str, str]:
    """stop_id -> island_key (terminals map to their island)."""
    m = {k: k for k in load_islands()["island_key"]}
    m.update(dict(zip(terminals()["terminal_id"], terminals()["island_key"])))
    return m


def footpaths() -> dict[str, list[tuple[str, float]]]:
    """Walks between terminals on the same island, e.g. Jetty NO5 to the Villimalé ferry."""
    t = terminals()
    out: dict[str, list[tuple[str, float]]] = {}
    for _, a in t.iterrows():
        for _, b in t.iterrows():
            if a["terminal_id"] != b["terminal_id"] and a["island_key"] == b["island_key"]:
                m = haversine_m([a["lat"], a["lon"]], [b["lat"], b["lon"]])[0]
                out.setdefault(a["terminal_id"], []).append(
                    (b["terminal_id"], C.TERMINAL_EXIT_MIN + m / C.WALK_M_PER_MIN))
    return out


def island_zones():
    """Island outlines buffered by ZONE_BUFFER_M, or a 600 m circle where no outline exists."""
    import geopandas as gpd

    isl = load_islands()
    pts = gpd.GeoDataFrame(isl[["island_key"]], geometry=gpd.points_from_xy(isl["harbour_lon"], isl["harbour_lat"]),
                           crs="EPSG:4326").to_crs(C.UTM_CRS)
    zones = pts.copy()
    zones["geometry"] = pts.buffer(C.ZONE_FALLBACK_RADIUS_M)
    zones["zone_source"] = "circle_600m"

    outlines = next(iter(C.RAW.rglob("gis_osm_places_a_free_1.shp")), None)
    if outlines is not None:
        poly = gpd.read_file(outlines).to_crs(C.UTM_CRS)
        poly = poly[poly["fclass"].isin(["island", "islet"])] if "fclass" in poly else poly
        hit = gpd.sjoin(pts, poly[["geometry"]], predicate="within", how="inner")
        for idx, pidx in hit["index_right"].items():
            zones.loc[idx, "geometry"] = poly.loc[pidx, "geometry"].buffer(C.ZONE_BUFFER_M)
            zones.loc[idx, "zone_source"] = "osm_outline_300m"
    return zones.to_crs("EPSG:4326")


def boat_links(conns: pd.DataFrame) -> pd.DataFrame:
    """One row per island pair served by boat, with boats per day (first service day only)."""
    pts, isl = stop_points(), stop_island()
    day = conns[conns["dep_min"] < 1440]
    pairs = day.assign(a=day["from_stop"].map(isl), b=day["to_stop"].map(isl))
    pairs = pairs[pairs["a"] != pairs["b"]]
    key = pairs[["a", "b"]].apply(lambda r: tuple(sorted(r)), axis=1)
    agg = pairs.assign(key=key).groupby("key").agg(boats_per_day=("trip_id", "nunique"),
                                                    modes=("mode", lambda m: ", ".join(sorted(set(m)))))
    agg = agg.reset_index()
    agg[["a", "b"]] = pd.DataFrame(agg["key"].tolist(), index=agg.index)
    agg[["a_lat", "a_lon"]] = pts.loc[agg["a"], ["lat", "lon"]].to_numpy()
    agg[["b_lat", "b_lon"]] = pts.loc[agg["b"], ["lat", "lon"]].to_numpy()
    return agg.drop(columns="key")


# --- Map layers for the dashboard ------------------------------------------------
# Each returns a DataFrame for pydeck with lon/lat (or from_/to_ or path) and a `tooltip` column.

# Blue, not green, for the fastest band: green and red look alike to colourblind viewers.
ACCESS_BANDS = [("Up to 1 hour", 60, [42, 120, 214]), ("1 to 2 hours", 120, [250, 178, 25]),
                ("Over 2 hours", math.inf, [208, 59, 59])]
UNREACHABLE = ("No scheduled boat (Wed-Thu)", [138, 137, 132])
FERRY_TERMINALS = ["T_MALE_NORTH", "T_MALE_WEST", "T_HULHUMALE", "T_VILLIMALE"]


def access_band(minutes) -> tuple[str, list[int]]:
    if minutes is None or pd.isna(minutes):
        return UNREACHABLE
    return next((label, rgb) for label, top, rgb in ACCESS_BANDS if minutes <= top)


def islands_layer(access_results: pd.DataFrame, dep_min: int, target: str) -> pd.DataFrame:
    """ScatterplotLayer: 23 origin islands, circle area by population, colour by minutes to hospital."""
    dep_min = int(dep_min) // C.STEP_MIN * C.STEP_MIN
    a = access_results[(access_results["dep_min"] == dep_min) & (access_results["target"] == target)]
    minutes = a.set_index("origin_key")["total_min"].astype(float)
    isl = load_islands()
    df = isl[isl["role"] == "origin"][["island_key", "island", "harbour_lat", "harbour_lon", "population_2022"]]
    df = df.rename(columns={"harbour_lat": "lat", "harbour_lon": "lon", "population_2022": "population"})
    df["minutes"] = df["island_key"].map(minutes)
    df["band"], df["colour"] = zip(*df["minutes"].map(access_band))
    df["radius_m"] = 40 * np.sqrt(df["population"])  # area proportional to population
    df["tooltip"] = [f"{k}: {b if pd.isna(m) else f'{m:.0f} min'} · {p:,} people"
                     for k, m, b, p in zip(df["island_key"], df["minutes"], df["band"], df["population"])]
    return df.reset_index(drop=True)


def boat_links_layer(connections: pd.DataFrame) -> pd.DataFrame:
    """LineLayer: island pairs served by boat, wider for more boats a day."""
    df = boat_links(connections).rename(columns={"a_lat": "from_lat", "a_lon": "from_lon",
                                                 "b_lat": "to_lat", "b_lon": "to_lon"})
    df["width_px"] = 1 + 1.5 * np.sqrt(df["boats_per_day"])
    df["tooltip"] = df["a"] + " – " + df["b"] + ": " + df["boats_per_day"].astype(str) + " boats a day"
    return df


def hospitals_layer() -> pd.DataFrame:
    """ScatterplotLayer: the 9 hospitals."""
    from .load import load_facilities

    f = load_facilities()
    df = f[f["type"] == "hospital"][["facility_id", "name", "island_key", "lat", "lon", "level"]].copy()
    df["tooltip"] = df["name"] + " (" + df["level"] + " hospital)"
    return df.reset_index(drop=True)


def terminals_layer() -> pd.DataFrame:
    """ScatterplotLayer: the 4 Greater Malé ferry terminals."""
    t = terminals()
    df = t[t["terminal_id"].isin(FERRY_TERMINALS)].copy()
    df["tooltip"] = df["name"] + " (ferry terminal)"
    return df.reset_index(drop=True)


def bus_routes_layer() -> pd.DataFrame:
    """PathLayer: Greater Malé bus routes in stop order. Empty until the Team Kandu RTL files are in data/raw/."""
    stops, deps = load_raw_csv("rtl_bus_stops.csv"), load_raw_csv("rtl_bus_departures.csv")
    empty = pd.DataFrame(columns=["route_id", "path", "tooltip"])
    if stops is None or deps is None:
        return empty
    from .load import hhmm_to_min

    def col(df, *names):
        return next(c for c in df.columns if c.lower() in names)

    try:
        code, lat, lon = col(stops, "stop_code", "code", "stop_id"), col(stops, "lat", "latitude", "stop_lat"), \
            col(stops, "lon", "lng", "longitude", "stop_lon")
        xy = stops.assign(code=stops[code].astype(str)).drop_duplicates("code").set_index("code")[[lon, lat]]
        route, trip, dcode, time = col(deps, "route_id", "route"), col(deps, "trip_id", "trip"), \
            col(deps, "stop_code", "code", "stop_id"), col(deps, "time", "departure", "departure_time")
    except StopIteration:
        return empty
    d = deps.assign(code=deps[dcode].astype(str), m=deps[time].map(hhmm_to_min))
    rows = []
    for rid, g in d.groupby(route):
        g = g.assign(rel=g["m"] - g.groupby(trip)["m"].transform("min"))
        order = g.groupby("code")["rel"].median().sort_values().index
        path = xy.reindex(order).dropna().to_numpy().tolist()
        if len(path) >= 2:
            rows.append({"route_id": str(rid), "path": path, "tooltip": f"Bus {rid}"})
    return pd.DataFrame(rows) if rows else empty


def observed_trips_layer() -> pd.DataFrame:
    """LineLayer: FollowMe island-to-island trips, one line per pair. Empty until observed_trips.csv exists."""
    path = C.PROCESSED / "observed_trips.csv"
    cols = ["from_key", "to_key", "n_trips", "median_min", "from_lat", "from_lon", "to_lat", "to_lon", "tooltip"]
    if not path.exists():
        return pd.DataFrame(columns=cols)
    t = pd.read_csv(path)
    g = t.groupby(["from_key", "to_key"]).agg(n_trips=("duration_min", "size"),
                                              median_min=("duration_min", "median")).reset_index()
    pts = load_islands().set_index("island_key")[["harbour_lat", "harbour_lon"]]
    g[["from_lat", "from_lon"]] = pts.loc[g["from_key"]].to_numpy()
    g[["to_lat", "to_lon"]] = pts.loc[g["to_key"]].to_numpy()
    g["tooltip"] = (g["from_key"] + " → " + g["to_key"] + ": " + g["n_trips"].astype(str) + " observed trips, median "
                    + g["median_min"].round().astype(int).astype(str) + " min")
    return g[cols]
