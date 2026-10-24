"""Terminals, island zones and map layers (M1)."""
from __future__ import annotations

import json
import time

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
    df["walk_to_stop_min"] = 0
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


# ---------------------------------------------------------------------------
# Map layers for the dashboard: M1's code from the zayan branch (6ef0cb2, e4cb7be).
# Each returns a DataFrame for pydeck with a `tooltip` column. Adapted only to
# this branch's config and loaders (marked "adapted").
# ---------------------------------------------------------------------------

BUS_ROUTES_CSV = C.PROCESSED / "bus_routes.csv"
OBSERVED_PAIRS_CSV = C.PROCESSED / "observed_pairs.csv"

# Access bands. Status colours from the dataviz reference palette, with
# "good" as blue rather than green: green vs red measured dE 4.1 for
# deuteranopes; blue/amber/red/grey all clear dE 10 (validate_palette.js,
# all pairs). Each band also has a text label, so colour is never the only cue.
ACCESS_BANDS = [
    # (label, upper bound in minutes, RGBA)
    ("up to 1 hour", 60, [31, 111, 209, 220]),
    ("1 to 2 hours", 120, [250, 178, 25, 220]),
    ("over 2 hours", float("inf"), [208, 59, 59, 220]),
]
# Blank total_min in access_results: no scheduled boat gets there within the
# Wed + next-day (Thu) timetable that routing searches.
UNREACHABLE = ("no scheduled boat (Wed-Thu)", [140, 140, 136, 200])
RADIUS_M_PER_SQRT_PERSON = 20     # 4,471 people (Maafushi) -> ~1.3 km circle
HOSPITAL_COLOUR = [255, 255, 255, 255]
TERMINAL_COLOUR = [40, 40, 40, 255]
BOAT_LINK_COLOUR = [70, 110, 150, 160]
BUS_ROUTE_COLOUR = [120, 120, 120, 140]
OBSERVED_COLOURS = {"slow": [70, 110, 150, 200], "fast": [150, 90, 170, 200]}


def access_band(minutes) -> tuple[str, list]:
    """Band label and colour for a door-to-door time (blank = unreachable)."""
    if pd.isna(minutes):
        return UNREACHABLE
    for label, upper, colour in ACCESS_BANDS:
        if minutes <= upper:
            return label, colour
    return ACCESS_BANDS[-1][0], ACCESS_BANDS[-1][2]


def fmt_minutes(minutes: float) -> str:
    h, m = divmod(int(round(minutes)), 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"


def stop_positions() -> pd.DataFrame:
    """lat/lon and display name for every island_key and terminal_id."""
    islands = load_islands().rename(columns={"island_key": "stop_id", "harbour_lat": "lat",  # adapted
                                             "harbour_lon": "lon", "island": "name"})
    t = terminals().rename(columns={"terminal_id": "stop_id"})  # adapted
    return pd.concat([islands[["stop_id", "name", "lat", "lon"]],
                      t[["stop_id", "name", "lat", "lon"]]]).set_index("stop_id")


def islands_layer(access_results: pd.DataFrame, dep_min: int,
                  target: str = "gm_hospital", scenario: str = "base") -> pd.DataFrame:
    """One circle per origin island for a departure time and target.

    Columns: island_key, name, lat, lon, population, total_min, band, colour,
    radius_m, tooltip. `dep_min` is rounded down to the STEP_MIN grid.
    Circle area is proportional to population; colour is the access band.
    """
    step = (int(dep_min) // C.STEP_MIN) * C.STEP_MIN
    rows = access_results[(access_results.dep_min == step) & (access_results.target == target)
                          & (access_results.scenario == scenario)]
    islands = load_islands()  # adapted
    origins = islands[islands.role == "origin"][["island_key", "island", "harbour_lat",
                                                  "harbour_lon", "population_2022"]]
    origins.columns = ["island_key", "name", "lat", "lon", "population"]
    from .load import load_facilities  # adapted
    hospitals = load_facilities().set_index("facility_id").name

    layer = origins.merge(rows[["origin_key", "total_min", "facility_id"]],
                          left_on="island_key", right_on="origin_key", how="left")
    bands = layer.total_min.map(access_band)
    layer["band"] = bands.str[0]
    layer["colour"] = bands.str[1]
    layer["radius_m"] = layer.population ** 0.5 * RADIUS_M_PER_SQRT_PERSON
    layer["tooltip"] = [
        f"{r.name} ({r.population:,} people): "
        + (f"{fmt_minutes(r.total_min)} to {hospitals.get(r.facility_id, r.facility_id)}"
           if pd.notna(r.total_min) else UNREACHABLE[0])
        for r in layer.itertuples()
    ]
    return layer.drop(columns=["origin_key", "facility_id"])


def boat_links_layer(connections: pd.DataFrame) -> pd.DataFrame:
    """One line per island/terminal pair, both directions combined.

    Columns: stop_a, stop_b, from_lat, from_lon, to_lat, to_lon, boats_per_day,
    routes, width_px, colour, tooltip. Counts first-day legs only (the
    contract repeats every leg at +1440 for the next day).
    """
    day = connections[connections.dep_min < 1440].copy()
    pair = day[["from_stop", "to_stop"]].apply(sorted, axis=1, result_type="expand")
    day["stop_a"], day["stop_b"] = pair[0], pair[1]
    links = day.groupby(["stop_a", "stop_b"]).agg(
        boats_per_day=("conn_id", "size"),
        routes=("route_id", lambda r: ", ".join(sorted(set(map(str, r))))),
    ).reset_index()

    pos = stop_positions()
    links["from_lat"] = links.stop_a.map(pos.lat)
    links["from_lon"] = links.stop_a.map(pos.lon)
    links["to_lat"] = links.stop_b.map(pos.lat)
    links["to_lon"] = links.stop_b.map(pos.lon)
    # sqrt keeps the Villimalé shuttle (hundreds a day) from drowning the rest
    links["width_px"] = (1 + links.boats_per_day ** 0.5).clip(upper=12).round(1)
    links["colour"] = [BOAT_LINK_COLOUR] * len(links)
    links["tooltip"] = [
        f"{pos.name.get(r.stop_a, r.stop_a)} - {pos.name.get(r.stop_b, r.stop_b)}: "
        f"{r.boats_per_day} boats a day (route {r.routes})"
        for r in links.itertuples()
    ]
    return links


def hospitals_layer() -> pd.DataFrame:
    """Hospitals that count as destinations (Senahiya per INCLUDE_SENAHIYA)."""
    from .load import load_facilities  # adapted: this branch has no lastmile.load_hospitals

    h = load_facilities()
    h = h[(h["type"] == "hospital") & ((h["facility_id"] != "H03") | C.INCLUDE_SENAHIYA)].copy()
    h["colour"] = [HOSPITAL_COLOUR] * len(h)
    h["tooltip"] = h.name + " (" + h.level + ")"
    return h[["facility_id", "name", "level", "island_key", "lat", "lon", "colour", "tooltip"]]


def terminals_layer() -> pd.DataFrame:
    t = terminals()  # adapted
    t["colour"] = [TERMINAL_COLOUR] * len(t)
    t["tooltip"] = t.name + " ferry terminal"
    return t[["terminal_id", "name", "island_key", "lat", "lon", "colour", "tooltip"]]


def bus_routes_layer() -> pd.DataFrame:
    """One path per Greater Malé bus route, stops in route order (PathLayer).

    Columns: route_number, route, path ([[lon, lat], ...]), colour, tooltip.
    Reads data/processed/bus_routes.csv; empty if it hasn't been built.
    """
    if not BUS_ROUTES_CSV.exists():
        return pd.DataFrame(columns=["route_number", "route", "path", "colour", "tooltip"])
    stops = pd.read_csv(BUS_ROUTES_CSV, encoding="utf-8-sig")
    paths = (stops.sort_values(["route_number", "order"])
             .groupby("route_number")
             .agg(route=("route", "first"),
                  path=("lat", lambda s: stops.loc[s.index, ["lon", "lat"]].values.tolist()))
             .reset_index())
    # Road geometry where it has been snapped (write_bus_road_paths); straight stop-to-stop lines otherwise.
    roads = load_bus_road_paths()
    on_road = paths.route_number.isin(roads.get("routes", {}))
    paths.loc[on_road, "path"] = paths.loc[on_road, "route_number"].map(roads.get("routes", {}))
    partly = paths.route_number.isin(roads.get("straight_legs", {}))
    paths["colour"] = [BUS_ROUTE_COLOUR] * len(paths)
    paths["tooltip"] = paths.route_number + " " + paths.route + np.select(
        [~on_road, partly], [" (stops joined by straight lines)", " (some stops joined by straight lines)"], "")
    return paths


BUS_ROAD_PATHS_JSON = C.PROCESSED / "bus_road_paths.json"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving/"


def load_bus_road_paths() -> dict:
    """{"routes": route_number -> [[lon, lat], ...] along the roads, "straight_legs": ...}; {} if not built."""
    if not BUS_ROAD_PATHS_JSON.exists():
        return {}
    return json.loads(BUS_ROAD_PATHS_JSON.read_text(encoding="utf-8"))


def _reverse_leg(a: list, b: list) -> tuple[list, float] | None:
    """Road path from b to a, flipped to run a to b, with its length in metres; None if OSRM has none."""
    import requests

    r = requests.get(OSRM_URL + f"{b[0]:.6f},{b[1]:.6f};{a[0]:.6f},{a[1]:.6f}",
                     params={"overview": "full", "geometries": "geojson"},
                     headers={"User-Agent": "kaafu-connect (Maldives Datathon 2026)"}, timeout=30)
    if not r.ok or not r.json().get("routes"):
        return None
    best = r.json()["routes"][0]
    return [a, *best["geometry"]["coordinates"][::-1], b], best["distance"]


def write_bus_road_paths(pause_s: float = 1.0) -> dict[str, list]:
    """Snap each bus route onto OSM roads through its stops in order, via the public OSRM server.

    Only public bus-stop coordinates are sent. Run once (needs internet); the app reads the saved file.
    Each stop-to-stop leg follows the roads, except a leg whose road path is implausibly long (OSM's
    one-way airport roads send Velana Domestic Terminal legs on an 11 km loop via Hulhumalé): that
    leg alone is drawn straight and listed in `straight_legs`. A route OSRM can't place stays straight.
    """
    import requests

    stops = pd.read_csv(BUS_ROUTES_CSV, encoding="utf-8-sig").sort_values(["route_number", "order"])
    out, notes, straight_legs = {}, {}, {}
    for route, g in stops.groupby("route_number"):
        coords = ";".join(f"{lon:.6f},{lat:.6f}" for lon, lat in zip(g.lon, g.lat))
        try:
            r = requests.get(OSRM_URL + coords, params={"overview": "false", "steps": "true",
                                                        "geometries": "geojson"},
                             headers={"User-Agent": "kaafu-connect (Maldives Datathon 2026)"}, timeout=30)
            r.raise_for_status()
            legs = r.json()["routes"][0]["legs"]
        except (requests.RequestException, KeyError, IndexError, ValueError) as e:
            notes[route] = f"not snapped: {type(e).__name__}"
            continue
        pts = g[["lon", "lat"]].to_numpy().tolist()
        path, bad = [], []
        for i, leg in enumerate(legs):
            straight = haversine_m([pts[i][::-1]], [pts[i + 1][::-1]])[0]
            piece = [c for step in leg["steps"] for c in step["geometry"]["coordinates"]]
            if leg["distance"] > 2 * straight + 500:
                # Long detour: OSM's one-way tags may forbid this direction (Velana airport roads loop
                # via Hulhumalé). Draw whichever is shorter, this way or the reverse trip flipped.
                rev = _reverse_leg(pts[i], pts[i + 1])
                if rev is not None and rev[1] < leg["distance"]:
                    piece = rev[0]
            if not piece:
                piece = [pts[i], pts[i + 1]]
                bad.append(f"{g.stop.iloc[i]} → {g.stop.iloc[i + 1]} (no road path)")
            path.extend(piece if not path else piece[1:])
        out[route] = [[round(x, 6), round(y, 6)] for x, y in path]
        if bad:
            straight_legs[route] = bad
        notes[route] = f"{len(legs) - len(bad)}/{len(legs)} legs on roads"
        time.sleep(pause_s)
    BUS_ROAD_PATHS_JSON.write_text(json.dumps(
        {"source": "OSRM (router.project-osrm.org) on OpenStreetMap roads, © OpenStreetMap contributors (ODbL)",
         "notes": notes, "straight_legs": straight_legs, "routes": out}, ensure_ascii=False), encoding="utf-8")
    return notes


OBSERVED_PAIR_COLUMNS = ["from_key", "to_key", "speed_class", "n_trips", "n_devices",
                         "median_min", "p90_min", "trips_per_day", "first_hour", "last_hour"]


def observed_trips_layer(observed_pairs: pd.DataFrame | None = None) -> pd.DataFrame:
    """Lines for M2's observed boat trips (empty until observed_pairs.csv exists).

    Columns: from_key, to_key, speed_class, from_lat, from_lon, to_lat, to_lon,
    trips_per_day, median_min, width_px, colour, tooltip. Only pairs with at
    least OBSERVED_MIN_TRIPS trips are drawn.
    """
    if observed_pairs is None:
        if not OBSERVED_PAIRS_CSV.exists():
            observed_pairs = pd.DataFrame(columns=OBSERVED_PAIR_COLUMNS)
        else:
            observed_pairs = pd.read_csv(OBSERVED_PAIRS_CSV, encoding="utf-8-sig")
    pairs = observed_pairs[observed_pairs.n_trips >= C.OBSERVED_MIN_TRIPS].copy()
    pos = stop_positions()
    pairs["from_lat"] = pairs.from_key.map(pos.lat)
    pairs["from_lon"] = pairs.from_key.map(pos.lon)
    pairs["to_lat"] = pairs.to_key.map(pos.lat)
    pairs["to_lon"] = pairs.to_key.map(pos.lon)
    pairs["width_px"] = (1 + pairs.trips_per_day.astype(float) ** 0.5).clip(upper=10)
    pairs["colour"] = pairs.speed_class.map(OBSERVED_COLOURS)
    pairs["tooltip"] = [
        f"{pos.name.get(r.from_key, r.from_key)} to {pos.name.get(r.to_key, r.to_key)} "
        f"({r.speed_class} boats): median {fmt_minutes(r.median_min)}, "
        f"{r.trips_per_day:.1f} trips a day"
        for r in pairs.itertuples()
    ]
    return pairs[["from_key", "to_key", "speed_class", "from_lat", "from_lon", "to_lat", "to_lon",
                  "trips_per_day", "median_min", "width_px", "colour", "tooltip"]]
