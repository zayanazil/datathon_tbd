"""Places and map layers: terminals, island zones, pydeck layers (M1).

Run `python -m kaafu.geo` to write data/processed/terminals.csv and
data/processed/island_zones.geojson.
"""

import geopandas as gpd
import pandas as pd

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


def write_zones(zones: gpd.GeoDataFrame) -> None:
    check_zones(zones)
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    zones[["island_key", "source", "geometry"]].to_file(
        config.ISLAND_ZONES_GEOJSON, driver="GeoJSON", encoding=config.WRITE_ENCODING)


if __name__ == "__main__":
    print(write_terminals().to_string(index=False))
    print(f"wrote {config.TERMINALS_CSV.relative_to(config.ROOT)}\n")

    zones = build_circle_zones()
    write_zones(zones)
    print(zones.groupby(["source", "radius_m"]).size().to_string())
    print(f"wrote {config.ISLAND_ZONES_GEOJSON.relative_to(config.ROOT)} ({len(zones)} zones)\n")
    overlaps = zone_overlaps(zones)
    print("overlapping zones:" if len(overlaps) else "no overlapping zones")
    if len(overlaps):
        print(overlaps.to_string(index=False))
