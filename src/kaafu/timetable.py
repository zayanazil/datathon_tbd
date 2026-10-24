"""Ferry timetable sheet to boat connections (BUILD_PLAN 6.1).

Reads data/sheets/ferry_timetable.csv and writes data/processed/connections.csv:
one row per boat leg on the service day, plus the next day's legs at +1440.
"""
from pathlib import Path

import pandas as pd

CONNECTION_COLUMNS = [
    "conn_id", "trip_id", "route_id", "from_stop", "to_stop", "dep_min", "arr_min",
    "mode", "operator", "day_type", "estimated", "source",
]


def load_timetable(path):
    return pd.read_csv(path, encoding="utf-8-sig", dtype={"route_id": str})


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


def build_connections(timetable, day, next_day):
    """Rows running on `day`, plus `next_day`'s rows shifted by +1440.

    The next day uses its own rows, not a copy of `day`: routes 303, 305, 306
    and 307 alternate by day, so the next morning's boats differ.
    """
    conns = pd.concat([
        _legs(timetable, day, 0, ""),
        _legs(timetable, next_day, 1440, "_d2"),
    ])
    conns["day_type"] = day
    conns = conns.sort_values(["dep_min", "arr_min"], kind="stable").reset_index(drop=True)
    conns["conn_id"] = range(1, len(conns) + 1)
    return conns[CONNECTION_COLUMNS]


def main(cfg=None):
    if cfg is None:
        from kaafu import config as cfg
    sheets, processed = Path(cfg.SHEETS_DIR), Path(cfg.PROCESSED_DIR)
    timetable = load_timetable(sheets / "ferry_timetable.csv")
    check_names(timetable, pd.read_csv(sheets / "island_names.csv", encoding="utf-8-sig"))
    conns = build_connections(timetable, cfg.DAY, cfg.NEXT_DAY)
    processed.mkdir(parents=True, exist_ok=True)
    conns.to_csv(processed / "connections.csv", index=False)
    return conns


if __name__ == "__main__":
    main()
