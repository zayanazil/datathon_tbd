"""Fill in any missing processed outputs: python -m kaafu.pipeline [--rebuild] [--skip-followme].

data/processed/ holds the team's real outputs (M1 zayan, M2 m2-movement, M3 m3-network), and the
dashboard reads those. This only builds a file that is missing, so it never overwrites a
teammate's output; --rebuild regenerates everything it can from data/sheets and data/raw.
"""
from __future__ import annotations

import argparse

from . import avas, config as C, followme, geo, lastmile
from .load import check_all, load_processed
from .scenarios import run_scenario
from .timetable import ASSUMPTIONS, build_connections


def _write(df, name):
    path = C.PROCESSED / name
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"  wrote {path.relative_to(C.ROOT)} ({len(df):,} rows)")


def main(rebuild: bool = False, skip_followme: bool = False):
    C.PROCESSED.mkdir(parents=True, exist_ok=True)
    print("Data checks:", "; ".join(check_all()) or "ok")

    def needed(*names) -> bool:
        if rebuild or not all((C.PROCESSED / n).exists() for n in names):
            return True
        print(f"  keeping the team's {', '.join(names)}")
        return False

    print("M1 terminals, zones, bus routes")
    if needed("terminals.csv"):
        _write(geo.terminals()[["terminal_id", "name", "island_key", "lat", "lon", "bus_stop_code",
                                "walk_to_stop_min"]], "terminals.csv")
    if needed("island_zones.geojson"):
        (C.PROCESSED / "island_zones.geojson").write_text(geo.island_zones().to_json(), encoding="utf-8")
    if geo.BUS_ROUTES_CSV.exists() and needed("bus_road_paths.json"):
        try:  # needs internet once; the committed file is used after that
            print("  bus routes snapped to roads:", geo.write_bus_road_paths())
        except Exception as e:
            print(f"  bus routes not snapped ({type(e).__name__}): map draws straight stop-to-stop lines")

    print("M2 Avas")
    rides = None
    if needed("avas_hourly.csv"):
        if avas.raw_path():
            rides = avas.rides()
            _write(avas.hourly(rides), "avas_hourly.csv")
        else:
            print("  no Avas raw file in data/raw/ and no avas_hourly.csv: the last mile has no taxi option")

    print("M1 last mile")
    if needed("last_mile.csv"):
        _write(lastmile.build(load_processed("avas_hourly.csv"), rides), "last_mile.csv")

    print("M3 connections")
    if needed("connections.csv"):
        _write(build_connections(C.DAY), "connections.csv")
        for a in ASSUMPTIONS:
            print("  assumption:", a)

    print("M2 FollowMe")
    if skip_followme:
        print("  skipped")
    elif needed("observed_trips.csv", "observed_pairs.csv"):
        try:
            trips, pairs = followme.run()
            _write(trips, "observed_trips.csv")
            _write(pairs, "observed_pairs.csv")
        except Exception as e:  # raw data missing or unreadable: timetable-only demo
            print(f"  skipped ({type(e).__name__}: {e})")

    print("M3 access results (base scenario)")
    if needed("access_results.csv", "island_summary.csv"):
        from . import scenarios
        scenarios.base_last_mile.cache_clear()
        access, summary = run_scenario({"day": C.DAY})
        _write(access, "access_results.csv")
        _write(summary, "island_summary.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="regenerate files that already exist")
    ap.add_argument("--skip-followme", action="store_true")
    args = ap.parse_args()
    main(args.rebuild, args.skip_followme)
