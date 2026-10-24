"""Places and map layers: terminals, island zones, pydeck layers (M1).

Run `python -m kaafu.geo` to write data/processed/terminals.csv and
data/processed/island_zones.geojson.
"""

import json
import time

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import linemerge, polygonize, unary_union

from kaafu import config

TERMINAL_COLUMNS = ["terminal_id", "name", "island_key", "lat", "lon",
                    "bus_stop_code", "walk_to_stop_min"]

# Coordinates are the RTL bus stop at each terminal (rtl_bus_stops.csv).
# No T_AIRPORT: the ferry timetable never uses the airport.
TERMINALS = [
    ("T_MALE_NORTH", "Jetty NO5", "K.Malé", 4.178784, 73.513422, 1008, 0),
    ("T_MALE_WEST", "Maafannu Ferry Terminal", "K.Malé", 4.172281, 73.502060, 1101, 0),
    ("T_HULHUMALE", "Hulhumalé Ferry Terminal", "K.Hulhumalé", 4.216739, 73.537853, 507, 0),
    ("T_VILLIMALE", "Villimale Ferry Terminal", "K.Villimalé", 4.175107, 73.486942, 1301, 0),
]


def build_terminals() -> pd.DataFrame:
    """The Greater Malé arrival points, checked against islands and bus stops."""
    terminals = pd.DataFrame(TERMINALS, columns=TERMINAL_COLUMNS)

    islands = pd.read_csv(config.ISLANDS_CSV, encoding=config.READ_ENCODING)
    unknown = set(terminals.island_key) - set(islands.island_key)
    if unknown:
        raise ValueError(f"terminal island_key not in islands.csv: {unknown}")

    stops = pd.read_csv(config.RTL_BUS_STOPS_CSV, encoding=config.READ_ENCODING)
    stops = stops.drop_duplicates("code").set_index("code")
    for t in terminals.itertuples():
        if t.bus_stop_code not in stops.index:
            raise ValueError(f"{t.terminal_id}: bus stop {t.bus_stop_code} not in rtl_bus_stops.csv")
        stop = stops.loc[t.bus_stop_code]
        if abs(stop.lat - t.lat) > 1e-5 or abs(stop.lon - t.lon) > 1e-5:
            raise ValueError(f"{t.terminal_id}: coordinates differ from bus stop {t.bus_stop_code}")

    return terminals


def write_terminals() -> pd.DataFrame:
    terminals = build_terminals()
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    terminals.to_csv(config.TERMINALS_CSV, index=False, encoding=config.WRITE_ENCODING)
    return terminals


def island_points() -> gpd.GeoDataFrame:
    """One point per islands.csv row (harbour or island centre), in WGS84."""
    islands = pd.read_csv(config.ISLANDS_CSV, encoding=config.READ_ENCODING)
    return gpd.GeoDataFrame(
        islands,
        geometry=gpd.points_from_xy(islands.harbour_lon, islands.harbour_lat),
        crs=config.WGS84_CRS,
    )


def build_circle_zones() -> gpd.GeoDataFrame:
    """Fallback zones: a circle around each island point, built in UTM 43N.

    600 m for ordinary islands, 1,500 m for the long ones (Malé, Hulhumalé,
    Hulhulé) and for ADh.Dhigurah, whose point is 1.4 km from OSM's.
    """
    points = island_points().to_crs(config.UTM_CRS)
    radius = points.island_key.map(
        lambda key: config.ZONE_CIRCLE_LARGE_M if key in config.LARGE_ZONE_ISLANDS
        else config.ZONE_CIRCLE_M
    )
    zones = gpd.GeoDataFrame(
        {"island_key": points.island_key, "source": "circle", "radius_m": radius},
        geometry=points.buffer(radius),
        crs=config.UTM_CRS,
    )
    return zones.to_crs(config.WGS84_CRS)


_SESSION = None


def _session() -> requests.Session:
    """One kept-alive connection for all Overpass calls (fresh sockets per call
    exhaust Windows' local ports: WinError 10048)."""
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers["User-Agent"] = config.OVERPASS_USER_AGENT   # else 406
    return _SESSION


def overpass_islands(island_key: str, lat: float, lon: float) -> dict:
    """OSM island and islet outlines near a point, cached in data/raw/osm/."""
    cache = config.OSM_CACHE / f"{island_key}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))

    r = config.OVERPASS_SEARCH_M
    query = f"""[out:json][timeout:25];
(way["place"~"^(island|islet)$"](around:{r},{lat},{lon});
 relation["place"~"^(island|islet)$"](around:{r},{lat},{lon}););
out geom;"""
    for attempt in range(4):
        try:
            resp = _session().post(config.OVERPASS_URL, data={"data": query}, timeout=60)
            if resp.status_code == 200:
                break
        except requests.ConnectionError:
            if attempt == 3:
                raise
        time.sleep(5 * (attempt + 1))   # 429/502/504 or dropped connection: wait, retry
    resp.raise_for_status()

    data = resp.json()
    config.OSM_CACHE.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data), encoding="utf-8")
    time.sleep(1)                       # be polite between uncached calls
    return data


def osm_polygons(data: dict) -> list:
    """Polygons from Overpass `out geom` ways (closed rings) and relations (outer members)."""
    polygons = []
    for el in data.get("elements", []):
        if el["type"] == "way" and len(el.get("geometry", [])) >= 4:
            coords = [(p["lon"], p["lat"]) for p in el["geometry"]]
            if coords[0] == coords[-1]:
                polygons.append(Polygon(coords))
        elif el["type"] == "relation":
            lines = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
                     for m in el.get("members", [])
                     if m.get("role") == "outer" and len(m.get("geometry", [])) >= 2]
            if lines:
                polygons.extend(polygonize(linemerge(lines)))
    return [p.buffer(0) if not p.is_valid else p for p in polygons if not p.is_empty]


def build_osm_zones() -> gpd.GeoDataFrame:
    """Island outline buffered by ZONE_BUFFER_M, or the circle where OSM fails.

    The outline used is the one containing the island point, else the nearest
    one; if even the buffered outline doesn't contain the point, the circle is
    kept, so every zone still covers its harbour.
    """
    circles = build_circle_zones().set_index("island_key")
    zones = []
    for island in island_points().itertuples():
        key = island.island_key
        try:
            polygons = osm_polygons(overpass_islands(key, island.harbour_lat, island.harbour_lon))
        except (requests.RequestException, ValueError) as err:
            print(f"  {key}: Overpass failed ({err}); circle kept")
            polygons = []

        zone = None
        if polygons:
            point = Point(island.harbour_lon, island.harbour_lat)
            outlines = gpd.GeoSeries(polygons, crs=config.WGS84_CRS).to_crs(config.UTM_CRS)
            p_utm = gpd.GeoSeries([point], crs=config.WGS84_CRS).to_crs(config.UTM_CRS).iloc[0]
            outline = outlines.iloc[outlines.distance(p_utm).argmin()]
            buffered = outline.buffer(config.ZONE_BUFFER_M)
            if buffered.contains(p_utm):
                zone = gpd.GeoSeries([buffered], crs=config.UTM_CRS).to_crs(config.WGS84_CRS).iloc[0]

        if zone is None:
            zones.append({"island_key": key, "source": "circle", "geometry": circles.loc[key, "geometry"]})
        else:
            zones.append({"island_key": key, "source": "osm", "geometry": zone})
    return gpd.GeoDataFrame(zones, geometry="geometry", crs=config.WGS84_CRS)


def check_zones(zones: gpd.GeoDataFrame) -> None:
    """One valid zone per island, each containing its own island point."""
    points = island_points()
    if len(zones) != len(points) or set(zones.island_key) != set(points.island_key):
        raise ValueError("zones don't match islands.csv one-to-one")
    if zones.island_key.duplicated().any():
        raise ValueError("duplicate island_key in zones")
    if not zones.geometry.is_valid.all():
        raise ValueError(f"invalid zones: {list(zones.island_key[~zones.geometry.is_valid])}")
    merged = points.set_index("island_key").geometry.to_frame("point").join(
        zones.set_index("island_key").geometry.rename("zone"))
    outside = [key for key, row in merged.iterrows() if not row.zone.contains(row.point)]
    if outside:
        raise ValueError(f"zones don't contain their island point: {outside}")


def zone_overlaps(zones: gpd.GeoDataFrame) -> pd.DataFrame:
    """Pairs of zones that overlap, with the shared area in hectares."""
    utm = zones.to_crs(config.UTM_CRS).reset_index(drop=True)
    rows = []
    for i, a in utm.iterrows():
        for j in range(i + 1, len(utm)):
            b = utm.iloc[j]
            if a.geometry.intersects(b.geometry):
                shared = a.geometry.intersection(b.geometry).area / 10_000
                rows.append((a.island_key, b.island_key, round(shared, 1)))
    return pd.DataFrame(rows, columns=["zone_a", "zone_b", "overlap_ha"])


# ---------------------------------------------------------------------------
# Map layers for the dashboard (Step 4)
#
# Each function returns a plain DataFrame ready for a pydeck layer: positions
# as lat/lon columns, colours as [r, g, b, a] lists, widths/radii as numbers,
# and a `tooltip` text column. pydeck usage, e.g. for islands:
#   pdk.Layer("ScatterplotLayer", df, get_position=["lon", "lat"],
#             get_radius="radius_m", get_fill_color="colour", pickable=True)
# ---------------------------------------------------------------------------

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
    islands = pd.read_csv(config.ISLANDS_CSV, encoding=config.READ_ENCODING)
    islands = islands.rename(columns={"island_key": "stop_id", "harbour_lat": "lat",
                                      "harbour_lon": "lon", "island": "name"})
    terminals = build_terminals().rename(columns={"terminal_id": "stop_id"})
    return pd.concat([islands[["stop_id", "name", "lat", "lon"]],
                      terminals[["stop_id", "name", "lat", "lon"]]]).set_index("stop_id")


def islands_layer(access_results: pd.DataFrame, dep_min: int,
                  target: str = "gm_hospital", scenario: str = "base") -> pd.DataFrame:
    """One circle per origin island for a departure time and target.

    Columns: island_key, name, lat, lon, population, total_min, band, colour,
    radius_m, tooltip. `dep_min` is rounded down to the STEP_MIN grid.
    Circle area is proportional to population; colour is the access band.
    """
    step = (int(dep_min) // config.STEP_MIN) * config.STEP_MIN
    rows = access_results[(access_results.dep_min == step) & (access_results.target == target)
                          & (access_results.scenario == scenario)]
    islands = pd.read_csv(config.ISLANDS_CSV, encoding=config.READ_ENCODING)
    origins = islands[islands.role == "origin"][["island_key", "island", "harbour_lat",
                                                  "harbour_lon", "population_2022"]]
    origins.columns = ["island_key", "name", "lat", "lon", "population"]
    hospitals = pd.read_csv(config.FACILITIES_CSV, encoding=config.READ_ENCODING).set_index("facility_id").name

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
    day = connections[connections.dep_min < config.MINUTES_PER_DAY].copy()
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
    from kaafu import lastmile    # lastmile imports geo

    h = lastmile.load_hospitals().reset_index()
    h["colour"] = [HOSPITAL_COLOUR] * len(h)
    h["tooltip"] = h.name + " (" + h.level + ")"
    return h[["facility_id", "name", "level", "island_key", "lat", "lon", "colour", "tooltip"]]


def terminals_layer() -> pd.DataFrame:
    t = build_terminals()
    t["colour"] = [TERMINAL_COLOUR] * len(t)
    t["tooltip"] = t.name + " ferry terminal"
    return t[["terminal_id", "name", "island_key", "lat", "lon", "colour", "tooltip"]]


def bus_routes_layer() -> pd.DataFrame:
    """One path per Greater Malé bus route, stops in route order (PathLayer).

    Columns: route_number, route, path ([[lon, lat], ...]), colour, tooltip.
    """
    from kaafu import lastmile

    stops = lastmile.BusNetwork().stops
    paths = (stops.sort_values(["route_number", "order"])
             .groupby("route_number")
             .agg(route=("route", "first"),
                  path=("lat", lambda s: stops.loc[s.index, ["lon", "lat"]].values.tolist()))
             .reset_index())
    paths["colour"] = [BUS_ROUTE_COLOUR] * len(paths)
    paths["tooltip"] = paths.route_number + " " + paths.route
    return paths


OBSERVED_PAIR_COLUMNS = ["from_key", "to_key", "speed_class", "n_trips", "n_devices",
                         "median_min", "p90_min", "trips_per_day", "first_hour", "last_hour"]


def observed_trips_layer(observed_pairs: pd.DataFrame | None = None) -> pd.DataFrame:
    """Lines for M2's observed boat trips (empty until observed_pairs.csv exists).

    Columns: from_key, to_key, speed_class, from_lat, from_lon, to_lat, to_lon,
    trips_per_day, median_min, width_px, colour, tooltip. Only pairs with at
    least OBSERVED_MIN_TRIPS trips are drawn.
    """
    if observed_pairs is None:
        if not config.OBSERVED_PAIRS_CSV.exists():
            observed_pairs = pd.DataFrame(columns=OBSERVED_PAIR_COLUMNS)
        else:
            observed_pairs = pd.read_csv(config.OBSERVED_PAIRS_CSV, encoding=config.READ_ENCODING)
    pairs = observed_pairs[observed_pairs.n_trips >= config.OBSERVED_MIN_TRIPS].copy()
    pos = stop_positions()
    pairs["from_lat"] = pairs.from_key.map(pos.lat)
    pairs["from_lon"] = pairs.from_key.map(pos.lon)
    pairs["to_lat"] = pairs.to_key.map(pos.lat)
    pairs["to_lon"] = pairs.to_key.map(pos.lon)
    pairs["width_px"] = (1 + pairs.trips_per_day.astype(float) ** 0.5).clip(upper=10)
    pairs["colour"] = pairs.speed_class.map(OBSERVED_COLOURS)
    pairs["tooltip"] = [
        f"{r.from_key} to {r.to_key} ({r.speed_class}): median {fmt_minutes(r.median_min)}, "
        f"{r.trips_per_day:.1f} trips a day"
        for r in pairs.itertuples()
    ]
    return pairs[["from_key", "to_key", "speed_class", "from_lat", "from_lon", "to_lat", "to_lon",
                  "trips_per_day", "median_min", "width_px", "colour", "tooltip"]]


def write_zones(zones: gpd.GeoDataFrame) -> None:
    check_zones(zones)
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    zones[["island_key", "source", "geometry"]].to_file(
        config.ISLAND_ZONES_GEOJSON, driver="GeoJSON", encoding=config.WRITE_ENCODING)


if __name__ == "__main__":
    print(write_terminals().to_string(index=False))
    print(f"wrote {config.TERMINALS_CSV.relative_to(config.ROOT)}\n")

    zones = build_osm_zones()
    write_zones(zones)
    print(zones.groupby("source").size().to_string())
    print("circle fallback:", list(zones.island_key[zones.source == "circle"]) or "none")
    print(f"wrote {config.ISLAND_ZONES_GEOJSON.relative_to(config.ROOT)} ({len(zones)} zones)\n")
    overlaps = zone_overlaps(zones)
    print("overlapping zones:" if len(overlaps) else "no overlapping zones")
    if len(overlaps):
        print(overlaps.to_string(index=False))
