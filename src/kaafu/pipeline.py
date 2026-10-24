"""Build every processed output in order: python -m kaafu.pipeline [--skip-followme]."""
from __future__ import annotations

import argparse
import json

from . import avas, config as C, followme, geo, indicators, lastmile
from .load import check_all, load_hdx, load_origins, load_processed
from .scenarios import run_scenario
from .timetable import ASSUMPTIONS, build_connections


def _write(df, name):
    path = C.PROCESSED / name
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"  wrote {path.relative_to(C.ROOT)} ({len(df):,} rows)")


def main(skip_followme: bool = False):
    C.PROCESSED.mkdir(parents=True, exist_ok=True)
    print("Data checks:", "; ".join(check_all()) or "ok")

    print("M1 terminals and zones")
    _write(geo.terminals()[["terminal_id", "name", "island_key", "lat", "lon", "bus_stop_code",
                            "walk_to_stop_min"]], "terminals.csv")
    (C.PROCESSED / "island_zones.geojson").write_text(geo.island_zones().to_json(), encoding="utf-8")

    print("M2 Avas")
    rides = None
    if avas.raw_path():
        rides = avas.rides()
        _write(avas.hourly(rides), "avas_hourly.csv")
    elif load_processed("avas_hourly.csv") is not None:
        print("  no Avas raw file in data/raw/: using the committed avas_hourly.csv")
    else:
        print("  no Avas raw file in data/raw/: taxi uses the flagged placeholder speed")

    print("M1 last mile")
    _write(lastmile.build(load_processed("avas_hourly.csv"), rides), "last_mile.csv")

    print("M3 connections")
    conns = build_connections(C.DAY)
    _write(conns, "connections.csv")
    for a in ASSUMPTIONS:
        print("  assumption:", a)

    print("M2 FollowMe")
    if skip_followme:
        print("  skipped")
    else:
        try:
            trips, pairs = followme.run()
            _write(trips, "observed_trips.csv")
            _write(pairs, "observed_pairs.csv")
        except Exception as e:  # raw data missing or unreadable: timetable-only demo
            print(f"  skipped ({type(e).__name__}: {e})")

    print("M3 access results (base scenario)")
    from . import scenarios
    scenarios.base_last_mile.cache_clear()
    access, summary = run_scenario({"day": C.DAY})
    _write(access, "access_results.csv")
    _write(summary, "island_summary.csv")

    origins = load_origins()
    ours = indicators.share_within(indicators.daytime_median(access, "gm_hospital"), origins)
    _write(indicators.hdx_table(ours, load_hdx()), "hdx_comparison.csv")
    nsds = indicators.nsds(access, origins, conns)
    (C.PROCESSED / "nsds_indicators.json").write_text(json.dumps(nsds, indent=2), encoding="utf-8")
    print("  NSDS:", {k: round(v, 1) for k, v in nsds.items()})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-followme", action="store_true")
    main(ap.parse_args().skip_followme)
