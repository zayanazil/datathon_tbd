"""Places and map layers: terminals, island zones, pydeck layers (M1).

Run `python -m kaafu.geo` to write data/processed/terminals.csv.
"""

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


if __name__ == "__main__":
    print(write_terminals().to_string(index=False))
    print(f"wrote {config.TERMINALS_CSV.relative_to(config.ROOT)}")
