"""Places and map layers: terminals, island zones, pydeck layers (M1).

Run `python -m kaafu.geo` to write data/processed/terminals.csv,
island_zones.geojson and bus_routes.csv. Building them needs data/raw/; the map
layers only read the committed files, so the dashboard runs from a fresh clone.
"""

import json
import time

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import linemerge, polygonize

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


def load_terminals() -> pd.DataFrame:
    """terminals.csv as committed (no raw data needed)."""
    return pd.read_csv(config.TERMINALS_CSV, encoding=config.READ_ENCODING)


BUS_ROUTES_CSV = config.PROCESSED / "bus_routes.csv"
BUS_ROUTE_COLUMNS = ["route_number", "route", "order", "stop", "code", "lat", "lon"]


def write_bus_routes() -> pd.DataFrame:
    """Greater Malé bus stops in route order (with lastmile's added stops), for the map."""
    from kaafu import lastmile    # lastmile imports geo

    stops = lastmile.BusNetwork().stops[BUS_ROUTE_COLUMNS]
    stops.to_csv(BUS_ROUTES_CSV, index=False, encoding=config.WRITE_ENCODING)
    return stops


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
    terminals = load_terminals().rename(columns={"terminal_id": "stop_id"})
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
    t = load_terminals()
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
    stops = pd.read_csv(BUS_ROUTES_CSV, encoding=config.READ_ENCODING)
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
        f"{pos.name.get(r.from_key, r.from_key)} to {pos.name.get(r.to_key, r.to_key)} "
        f"({r.speed_class} boats): median {fmt_minutes(r.median_min)}, "
        f"{r.trips_per_day:.1f} trips a day"
        for r in pairs.itertuples()
    ]
    return pairs[["from_key", "to_key", "speed_class", "from_lat", "from_lon", "to_lat", "to_lon",
                  "trips_per_day", "median_min", "width_px", "colour", "tooltip"]]


def example_deck(access_results: pd.DataFrame, connections: pd.DataFrame, dep_min: int,
                 target: str = "gm_hospital", scenario: str = "base",
                 show_bus: bool = False, show_observed: bool = False):
    """A ready-made pydeck map of all layers, for the dashboard or a preview.

    In Streamlit: st.pydeck_chart(geo.example_deck(access, conns, dep_min, target)).
    Uses pydeck's default Carto basemap (no Mapbox token needed).
    """
    import pydeck as pdk

    layers = []
    if show_bus:
        layers.append(pdk.Layer("PathLayer", bus_routes_layer(), get_path="path",
                                get_color="colour", width_min_pixels=1, pickable=True))
    layers.append(pdk.Layer("LineLayer", boat_links_layer(connections),
                            get_source_position=["from_lon", "from_lat"],
                            get_target_position=["to_lon", "to_lat"],
                            get_color="colour", get_width="width_px", pickable=True))
    if show_observed:
        layers.append(pdk.Layer("LineLayer", observed_trips_layer(),
                                get_source_position=["from_lon", "from_lat"],
                                get_target_position=["to_lon", "to_lat"],
                                get_color="colour", get_width="width_px", pickable=True))
    layers += [
        # 2px white ring keeps overlapping island circles apart
        pdk.Layer("ScatterplotLayer", islands_layer(access_results, dep_min, target, scenario),
                  get_position=["lon", "lat"], get_radius="radius_m", get_fill_color="colour",
                  stroked=True, get_line_color=[255, 255, 255], line_width_min_pixels=2,
                  pickable=True),
        pdk.Layer("ScatterplotLayer", hospitals_layer(), get_position=["lon", "lat"],
                  get_radius=150, radius_min_pixels=5, get_fill_color="colour",
                  stroked=True, get_line_color=[208, 59, 59], line_width_min_pixels=2,
                  pickable=True),
        pdk.Layer("ScatterplotLayer", terminals_layer(), get_position=["lon", "lat"],
                  get_radius=100, radius_min_pixels=4, get_fill_color="colour", pickable=True),
    ]
    return pdk.Deck(layers=layers, tooltip={"text": "{tooltip}"},
                    initial_view_state=pdk.ViewState(latitude=4.1, longitude=73.25, zoom=8))


# ---------------------------------------------------------------------------
# Static maps for the slides and the demo backup (Step 5)
# ---------------------------------------------------------------------------
INK = "#0b0b0b"          # text primary
INK_2 = "#52514e"        # text secondary
INK_3 = "#8a8985"        # muted (source lines)
SURFACE = "#fcfcfb"
LAND = "#e9e8e4"
LAND_EDGE = "#cfcec8"
LINK = "#9db3c8"
WEEK = ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri"]
# Ordinal blue ramp (dataviz reference steps 250/400/550/700; validated --ordinal)
DAYS_COLOURS = {0: "#86b6ef", 2: "#3987e5", 3: "#1c5cab", 6: "#0d366b"}
SOURCE_NOTE = ("Sources: MTCC/RTL ferry and bus timetables; Census 2022 (MBS) via Team Kandu; "
               "Avas; © OpenStreetMap contributors (ODbL)")

# Label placement for islands that sit close together: (dx, dy) in points, ha
LABEL_OFFSETS = {
    "K.Himmafushi": (-8, -6, "right"), "K.Huraa": (8, -2, "left"),
    "K.Thulusdhoo": (8, 2, "left"), "AA.Mathiveri": (-8, 6, "right"),
    "AA.Bodufolhudhoo": (6, -10, "left"), "V.Thinadhoo": (-8, 4, "right"),
    "V.Felidhoo": (9, 3, "left"), "V.Keyodhoo": (9, -8, "left"),
    "ADh.Dhigurah": (8, -4, "left"),
}
ATOLL_EXTENT = (72.52, 73.93, 3.40, 5.02)
# Greater Malé map: (dx, dy, ha) per terminal and hospital label
TERMINAL_LABEL = {"T_MALE_NORTH": (-6, 8, "right"), "T_MALE_WEST": (-8, -16, "right"),
                  "T_HULHUMALE": (-8, 7, "right"), "T_VILLIMALE": (-8, -14, "right")}
HOSPITAL_LABEL = {"H01": (-8, 8, "right"), "H02": (8, -9, "left"), "H03": (8, -9, "left"),
                  "H04": (8, -9, "left"), "H05": (8, -9, "left"), "H06": (-8, 8, "right")}
HOSPITAL_SHORT = {"H01": "IGMH", "H02": "ADK", "H03": "Senahiya", "H04": "Hulhumalé Hospital",
                  "H05": "Tree Top", "H06": "Villimalé Hospital"}


def male_bound_days() -> pd.DataFrame:
    """Days a week each origin island has a direct scheduled boat that reaches Greater Malé.

    A departure counts only if the same trip arrives at a Greater Malé terminal
    later on (outbound runs from Malé don't count). Columns: island_key,
    days_per_week, days, departures.
    """
    ft = pd.read_csv(config.FERRY_TIMETABLE_CSV, encoding=config.READ_ENCODING)
    ft = ft[ft.route_id != "VILI"].rename(columns={"from": "frm"})
    islands = pd.read_csv(config.ISLANDS_CSV, encoding=config.READ_ENCODING)
    origins = list(islands.island_key[islands.role == "origin"])

    found = {}
    for _, legs in ft.groupby("trip_id"):
        gm_arrivals = legs.arr_min[legs.arrival_terminal.notna()]
        for leg in legs.itertuples():
            if leg.frm in origins and (gm_arrivals > leg.dep_min).any():
                for day in leg.days.split():
                    found.setdefault(leg.frm, {}).setdefault(day, set()).add(leg.depart)

    rows = []
    for key in origins:
        by_day = found.get(key, {})
        days = [d for d in WEEK if d in by_day]
        times = sorted({t for d in days for t in by_day[d]})
        rows.append({"island_key": key, "days_per_week": len(days),
                     "days": " ".join(days), "departures": " ".join(times)})
    return pd.DataFrame(rows)


def _map_axes(fig, rect, extent):
    ax = fig.add_axes(rect)
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.set_aspect("equal")
    ax.set_facecolor(SURFACE)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    return ax


def _land(ax):
    """Island outlines: raw OSM outlines when cached, else the buffered zones."""
    zones = gpd.read_file(config.ISLAND_ZONES_GEOJSON)
    shapes = []
    for key in zones.island_key:
        cache = config.OSM_CACHE / f"{key}.json"
        if cache.exists():
            polys = osm_polygons(json.loads(cache.read_text(encoding="utf-8")))
            shapes.extend(polys)
    land = gpd.GeoSeries(shapes, crs=config.WGS84_CRS) if shapes else zones.geometry
    land.plot(ax=ax, color=LAND, edgecolor=LAND_EDGE, linewidth=0.6, zorder=0)
    ax.set_xlabel("")    # geopandas adds geodetic axis titles
    ax.set_ylabel("")


def _boat_links(ax, connections):
    links = boat_links_layer(connections)
    links = links[links.routes != "VILI"]
    for r in links.itertuples():
        ax.plot([r.from_lon, r.to_lon], [r.from_lat, r.to_lat], color=LINK,
                linewidth=0.6 + 0.4 * r.boats_per_day ** 0.5, zorder=1, solid_capstyle="round")


def _island_dots(ax, layer, colours, labels):
    """Circles sized by population with a 2px surface ring, plus direct labels."""
    ax.scatter(layer.lon, layer.lat, s=layer.population / 12, c=colours,
               edgecolors=SURFACE, linewidths=1.5, zorder=3)
    for r, text in zip(layer.itertuples(), labels):
        dx, dy, ha = LABEL_OFFSETS.get(r.island_key, (8, 0, "left"))
        ax.annotate(text, (r.lon, r.lat), xytext=(dx, dy), textcoords="offset points",
                    ha=ha, va="center", fontsize=7.5, color=INK, zorder=4)


def _greater_male_marker(ax):
    ax.annotate("Greater Malé\n(hospitals)", (73.51, 4.19), xytext=(10, -14),
                textcoords="offset points", fontsize=8, color=INK, fontweight="bold", zorder=4)
    ax.scatter([73.51], [4.19], marker="P", s=70, color=INK, edgecolors=SURFACE, zorder=4)


def _titles(fig, title, subtitle, wrap=96):
    import textwrap

    fig.text(0.04, 0.965, title, fontsize=14, fontweight="bold", color=INK, va="top")
    fig.text(0.04, 0.932, textwrap.fill(subtitle, wrap), fontsize=9.5, color=INK_2, va="top")
    fig.text(0.04, 0.015, SOURCE_NOTE, fontsize=6.5, color=INK_3)


def map_access(access_results, connections, dep_min=9 * 60, target="gm_hospital"):
    """Map 1: door-to-door time to a hospital for one departure, by island."""
    from matplotlib.figure import Figure
    from matplotlib.lines import Line2D

    layer = islands_layer(access_results, dep_min, target)
    fig = Figure(figsize=(8, 10), facecolor=SURFACE)
    ax = _map_axes(fig, [0.04, 0.06, 0.92, 0.84], ATOLL_EXTENT)
    _land(ax)
    _boat_links(ax, connections)
    labels = [f"{r.name}  {fmt_minutes(r.total_min) if pd.notna(r.total_min) else 'none'}"
              for r in layer.itertuples()]
    _island_dots(ax, layer, [[c / 255 for c in col[:3]] for col in layer.colour], labels)
    _greater_male_marker(ax)

    total = layer.population.sum()
    handles = []
    for label, colour in [(b[0], b[2]) for b in ACCESS_BANDS] + [UNREACHABLE]:
        sel = layer[layer.band == label]
        handles.append(Line2D([], [], marker="o", linestyle="", markersize=9,
                              markerfacecolor=[c / 255 for c in colour[:3]], markeredgecolor=SURFACE,
                              label=f"{label}: {len(sel)} islands, {sel.population.sum():,} people"))
    ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=8, labelcolor=INK,
              title="Door-to-door, leaving home", title_fontsize=8.5, alignment="left")

    none = layer[layer.band == UNREACHABLE[0]]
    h, m = divmod(dep_min, 60)
    what = "nearest Greater Malé hospital" if target == "gm_hospital" else "nearest hospital"
    _titles(fig, f"Leaving home on a Wednesday at {h:02d}:{m:02d}",
            f"Travel time by scheduled boat to the {what}. "
            f"{len(none)} islands ({none.population.sum():,} people, {none.population.sum() / total:.0%}) "
            f"have no scheduled boat that gets them there by Thursday night.")
    return fig


def map_boat_days(connections):
    """Map 2: days a week with a direct scheduled boat to Greater Malé."""
    from matplotlib.figure import Figure
    from matplotlib.lines import Line2D

    access = pd.read_csv(config.ACCESS_RESULTS_CSV, encoding=config.READ_ENCODING)
    layer = islands_layer(access, 9 * 60).merge(male_bound_days(), on="island_key")
    fig = Figure(figsize=(8, 10), facecolor=SURFACE)
    ax = _map_axes(fig, [0.04, 0.06, 0.92, 0.84], ATOLL_EXTENT)
    _land(ax)
    _boat_links(ax, connections)
    labels = [f"{r.name}  {r.days_per_week}" + ("  (change boats)" if r.days_per_week == 0 else "")
              for r in layer.itertuples()]
    _island_dots(ax, layer, [DAYS_COLOURS.get(d, DAYS_COLOURS[0]) for d in layer.days_per_week], labels)
    _greater_male_marker(ax)

    handles = []
    for days in sorted(DAYS_COLOURS, reverse=True):
        sel = layer[layer.days_per_week == days]
        if sel.empty:
            continue
        what = "no direct boat" if days == 0 else f"{days} days a week"
        handles.append(Line2D([], [], marker="o", linestyle="", markersize=9,
                              markerfacecolor=DAYS_COLOURS[days], markeredgecolor=SURFACE,
                              label=f"{what}: {len(sel)} islands, {sel.population.sum():,} people"))
    ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=8, labelcolor=INK,
              title="Direct boats to Greater Malé", title_fontsize=8.5, alignment="left")

    few = layer[layer.days_per_week <= 3]
    _titles(fig, "How often a boat leaves for Malé",
            f"Days a week with a direct scheduled boat to Greater Malé, usually one early-morning run. "
            f"{len(few)} of 23 islands ({few.population.sum():,} people) have 3 days or fewer. "
            f"No public ferry runs on Fridays.")
    return fig


def map_greater_male():
    """Map 3: ferry terminals, hospitals and the walks between them."""
    from matplotlib.figure import Figure

    terminals = load_terminals().set_index("terminal_id")
    hospitals = hospitals_layer().set_index("facility_id")
    hospitals = hospitals[hospitals.index.isin(config.GM_HOSPITALS)]
    last_mile = pd.read_csv(config.LAST_MILE_CSV, encoding=config.READ_ENCODING)
    walks = last_mile[(last_mile["mode"] == "walk") & (last_mile.available == "yes")
                      & (last_mile.hour == 9) & last_mile.stop_id.isin(terminals.index)]

    fig = Figure(figsize=(9, 8), facecolor=SURFACE)
    ax = _map_axes(fig, [0.03, 0.06, 0.94, 0.82], (73.474, 73.552, 4.160, 4.226))
    _land(ax)

    # Villimalé ferry (the only link to Villimalé) and walks
    a, b = terminals.loc["T_MALE_WEST"], terminals.loc["T_VILLIMALE"]
    ax.plot([a.lon, b.lon], [a.lat, b.lat], color=LINK, linewidth=2, zorder=1)
    ax.annotate("ferry, 8 min", ((a.lon + b.lon) / 2, (a.lat + b.lat) / 2), xytext=(0, -9),
                textcoords="offset points", ha="center", fontsize=7.5, color=INK_2)
    for w in walks.itertuples():
        t, h = terminals.loc[w.stop_id], hospitals.loc[w.facility_id]
        ax.plot([t.lon, h.lon], [t.lat, h.lat], color=INK_2, linewidth=1, linestyle=(0, (3, 2)), zorder=2)
        ax.annotate(f"{w.minutes:.0f} min", ((t.lon + h.lon) / 2, (t.lat + h.lat) / 2), xytext=(3, 3),
                    textcoords="offset points", fontsize=7, color=INK_2, zorder=4)

    ax.scatter(terminals.lon, terminals.lat, marker="^", s=70, color=INK, edgecolors=SURFACE, zorder=3)
    for tid, t in terminals.iterrows():
        dx, dy, ha = TERMINAL_LABEL.get(tid, (-6, 7, "right"))
        ax.annotate(t["name"], (t.lon, t.lat), xytext=(dx, dy), textcoords="offset points",
                    ha=ha, fontsize=8, color=INK, fontweight="bold", zorder=4)
    ax.scatter(hospitals.lon, hospitals.lat, marker="P", s=90, color="#d03b3b", edgecolors=SURFACE,
               linewidths=1, zorder=3)
    for fid, h in hospitals.iterrows():
        dx, dy, ha = HOSPITAL_LABEL.get(fid, (6, -9, "left"))
        ax.annotate(HOSPITAL_SHORT.get(fid, h["name"]), (h.lon, h.lat), xytext=(dx, dy),
                    textcoords="offset points", ha=ha, fontsize=8, color=INK, zorder=4)

    _titles(fig, "The last mile in Greater Malé",
            "Ferry terminals (triangles), hospitals (crosses) and walking times: 5 min to leave "
            "the boat plus a straight-line walk at 80 m/min. Villimalé has no road link; "
            "its hospital is reached by the 8-minute ferry.", wrap=110)
    return fig


def write_static_maps(dep_min: int = 9 * 60) -> list:
    """Save the three slide maps to docs/figures/ as PNG."""
    access = pd.read_csv(config.ACCESS_RESULTS_CSV, encoding=config.READ_ENCODING)
    connections = pd.read_csv(config.CONNECTIONS_CSV, encoding=config.READ_ENCODING)
    config.FIGURES.mkdir(parents=True, exist_ok=True)
    h, m = divmod(dep_min, 60)
    outputs = {
        f"map_access_wed_{h:02d}{m:02d}.png": map_access(access, connections, dep_min),
        "map_male_boat_days.png": map_boat_days(connections),
        "map_greater_male.png": map_greater_male(),
    }
    paths = []
    for name, fig in outputs.items():
        path = config.FIGURES / name
        fig.savefig(path, dpi=200, facecolor=SURFACE)
        paths.append(path)
    return paths


def write_zones(zones: gpd.GeoDataFrame) -> None:
    check_zones(zones)
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    zones[["island_key", "source", "geometry"]].to_file(
        config.ISLAND_ZONES_GEOJSON, driver="GeoJSON", encoding=config.WRITE_ENCODING)


if __name__ == "__main__":
    print(write_terminals().to_string(index=False))
    print(f"wrote {config.TERMINALS_CSV.relative_to(config.ROOT)}\n")

    routes = write_bus_routes()
    print(f"wrote {BUS_ROUTES_CSV.relative_to(config.ROOT)} "
          f"({routes.route_number.nunique()} routes, {len(routes)} stops)\n")

    for path in write_static_maps():
        print(f"wrote {path.relative_to(config.ROOT)}")
    print()

    zones = build_osm_zones()
    write_zones(zones)
    print(zones.groupby("source").size().to_string())
    print("circle fallback:", list(zones.island_key[zones.source == "circle"]) or "none")
    print(f"wrote {config.ISLAND_ZONES_GEOJSON.relative_to(config.ROOT)} ({len(zones)} zones)\n")
    overlaps = zone_overlaps(zones)
    print("overlapping zones:" if len(overlaps) else "no overlapping zones")
    if len(overlaps):
        print(overlaps.to_string(index=False))
