"""Per-island summary and population indicators (BUILD_PLAN 6.6).

main() writes the base scenario's access_results.csv and island_summary.csv.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from kaafu import routing

DAY_START, DAY_END = 6 * 60, 18 * 60  # "day" = departures 06:00-18:00
SUMMARY_COLUMNS = [
    "origin_key", "population", "day_median_min", "best_min", "worst_day_min",
    "last_practical_departure", "boats_per_day", "observed_gap_min",
]


def hhmm(minutes):
    return f"{int(minutes) // 60:02d}:{int(minutes) % 60:02d}"


def _blank_if_inf(x):
    return None if np.isinf(x) else round(float(x), 1)


def island_summary(results, islands, conns, target="gm_hospital"):
    """island_summary.csv from access_results rows for one scenario and target.

    Unreachable departures count as infinite, so a median or worst value that
    is unreachable is left blank.
    """
    res = results[results["target"] == target]
    population = islands.set_index("island_key")["population_2022"]
    rows = []
    for origin, g in res.groupby("origin_key", sort=False):
        total = g["total_min"].astype(float).fillna(np.inf)
        day = total[g["dep_min"].between(DAY_START, DAY_END)]
        same_day = g[(g["dep_min"] + total) < 1440]
        leaving = conns[(conns["from_stop"] == origin) & (conns["dep_min"] < 1440)]
        rows.append(dict(
            origin_key=origin,
            population=int(population[origin]),
            day_median_min=_blank_if_inf(np.median(day)),
            best_min=_blank_if_inf(day.min()),
            worst_day_min=_blank_if_inf(day.max()),
            last_practical_departure=hhmm(same_day["dep_min"].max()) if len(same_day) else "none",
            boats_per_day=leaving["trip_id"].nunique(),
            observed_gap_min=None,  # filled in Step 4 from M2's observed_pairs.csv
        ))
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def load_last_mile(processed, facilities, cfg):
    """M1's last_mile.csv if it has landed, else the walk-only placeholder."""
    path = processed / "last_mile.csv"
    if path.exists():
        return pd.read_csv(path, encoding="utf-8-sig")
    return routing.placeholder_last_mile(facilities, cfg)


def main(cfg=None):
    if cfg is None:
        from kaafu import config as cfg
    sheets, processed = Path(cfg.SHEETS_DIR), Path(cfg.PROCESSED_DIR)
    conns = pd.read_csv(processed / "connections.csv", dtype={"route_id": str})
    islands = pd.read_csv(sheets / "islands.csv", encoding="utf-8-sig")
    facilities = pd.read_csv(sheets / "facilities.csv", encoding="utf-8-sig")
    origins = islands.loc[islands["role"] == "origin", "island_key"].tolist()

    results = routing.access_results(conns, origins, facilities,
                                     load_last_mile(processed, facilities, cfg), cfg)
    summary = island_summary(results, islands, conns)
    results.to_csv(processed / "access_results.csv", index=False)
    summary.to_csv(processed / "island_summary.csv", index=False)
    return results, summary


if __name__ == "__main__":
    main()
