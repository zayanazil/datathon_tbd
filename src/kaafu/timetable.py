"""Ferry timetable sheet to boat connections (BUILD_PLAN 6.1).

Reads data/sheets/ferry_timetable.csv and writes data/processed/connections.csv:
one row per boat leg on the service day, plus the next day's legs at +1440.
"""
import pandas as pd

CONNECTION_COLUMNS = [
    "conn_id", "trip_id", "route_id", "from_stop", "to_stop", "dep_min", "arr_min",
    "mode", "operator", "day_type", "estimated", "source",
]


def load_timetable(path, encoding="utf-8-sig"):
    return pd.read_csv(path, encoding=encoding, dtype={"route_id": str})


def check_names(timetable, island_names):
    """Stop with a clear error if any from/to is not a known island_key."""
    known = set(island_names["island_key"])
    unknown = sorted((set(timetable["from"]) | set(timetable["to"])) - known)
    if unknown:
        raise ValueError(f"ferry_timetable.csv has names not in island_names.csv: {unknown}")


def _runs_on(days, day):
    return day in str(days).split()


def _legs(timetable, day, offset, suffix):
    legs = timetable[timetable["days"].map(lambda d: _runs_on(d, day))].copy()
    # Greater Malé stops are terminals; everywhere else the stop is the island.
    legs["from_stop"] = legs["departure_terminal"].fillna(legs["from"])
    legs["to_stop"] = legs["arrival_terminal"].fillna(legs["to"])
    legs["dep_min"] = legs["dep_min"] + offset
    legs["arr_min"] = legs["arr_min"] + offset
    legs["trip_id"] = legs["trip_id"] + suffix
    return legs


def build_connections(timetable, day, next_day, minutes_per_day=1440):
    """Rows running on `day`, plus `next_day`'s rows shifted by a day (+1440).

    The next day uses its own rows, not a copy of `day`: routes 303, 305, 306
    and 307 alternate by day, so the next morning's boats differ.
    """
    conns = pd.concat([
        _legs(timetable, day, 0, ""),
        _legs(timetable, next_day, minutes_per_day, "_d2"),
    ])
    conns["day_type"] = day
    conns = conns.sort_values(["dep_min", "arr_min"], kind="stable").reset_index(drop=True)
    conns["conn_id"] = range(1, len(conns) + 1)
    return conns[CONNECTION_COLUMNS]


def main(cfg=None):
    """Ferry timetable -> data/processed/connections.csv.

    Checks every stop name, keeps the service day's legs (config.DAY) and adds
    the next day's legs shifted by 1440 min, so late starts find tomorrow's boat.
    """
    if cfg is None:
        from kaafu import config as cfg
    timetable = load_timetable(cfg.FERRY_TIMETABLE_CSV, cfg.READ_ENCODING)
    check_names(timetable, pd.read_csv(cfg.ISLAND_NAMES_CSV, encoding=cfg.READ_ENCODING))
    conns = build_connections(timetable, cfg.DAY, cfg.NEXT_DAY, cfg.MINUTES_PER_DAY)
    cfg.CONNECTIONS_CSV.parent.mkdir(parents=True, exist_ok=True)
    conns.to_csv(cfg.CONNECTIONS_CSV, index=False, encoding=cfg.WRITE_ENCODING)
    return conns


if __name__ == "__main__":
    main()
