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


def _per_island_minutes(results, target, dep_min=None):
    """{origin: minutes} at one departure, or the daytime median when dep_min is None.
    Unreachable is infinite."""
    res = results[results["target"] == target]
    if dep_min is None:
        day = res[res["dep_min"].between(DAY_START, DAY_END)]
        return day.groupby("origin_key")["total_min"].apply(
            lambda s: np.median(s.astype(float).fillna(np.inf)))
    at = res[res["dep_min"] == dep_min].set_index("origin_key")["total_min"]
    return at.astype(float).fillna(np.inf)


def _areas(islands):
    origins = islands[islands["role"] == "origin"].set_index("island_key")
    return origins, {"Kaafu": origins["atoll"] == "K", "All 23": origins["atoll"].notna()}


def population_within(results, islands, cfg, target="gm_hospital", dep_min=None):
    """Share of population within each of THRESHOLDS_MIN, for Kaafu and all 23 islands.

    At one departure time, or for each island's daytime median when dep_min is None.
    """
    minutes = _per_island_minutes(results, target, dep_min)
    origins, areas = _areas(islands)
    rows = []
    for area, mask in areas.items():
        pop = origins.loc[mask, "population_2022"]
        island_minutes = minutes.reindex(pop.index).fillna(np.inf)
        for threshold in cfg.THRESHOLDS_MIN:
            within = int(pop[island_minutes <= threshold].sum())
            rows.append(dict(area=area, target=target,
                             departure="day_median" if dep_min is None else hhmm(dep_min),
                             threshold_min=threshold, population_within=within,
                             population=int(pop.sum()), share_pct=round(100 * within / pop.sum(), 1)))
    return pd.DataFrame(rows)


def hdx_comparison(within, hdx):
    """Our shares next to HDX's car-only ones. Percentages only: HDX uses its own population.

    Kaafu is compared with HDX Kaafu, all 23 islands with HDX Maldives. HDX has no 240-min value.
    """
    ours = within.pivot_table(index=["target", "departure", "threshold_min"], columns="area",
                              values="share_pct").reset_index()
    theirs = hdx.pivot_table(index="threshold_min", columns="area", values="share_pct")
    out = ours.rename(columns={"Kaafu": "kaafu_pct", "All 23": "all23_pct"})
    out["hdx_kaafu_pct"] = out["threshold_min"].map(theirs["Kaafu"])
    out["hdx_maldives_pct"] = out["threshold_min"].map(theirs["Maldives"])
    return out[["target", "departure", "threshold_min", "kaafu_pct", "hdx_kaafu_pct",
                "all23_pct", "hdx_maldives_pct"]]


def _direct_boat_islands(conns):
    """Islands where a boat leaving on DAY reaches a Greater Malé terminal on the same trip."""
    day = conns[conns["dep_min"] < 1440].sort_values("dep_min")
    found = set()
    for _, trip in day.groupby("trip_id"):
        stops = trip["from_stop"].tolist() + [trip["to_stop"].iloc[-1]]
        last_gm = max((i for i, s in enumerate(stops) if s.startswith("T_")), default=0)
        found.update(s for s in stops[:last_gm] if not s.startswith("T_"))
    return found


def nsds_figures(results, islands, facilities, conns, cfg):
    """NSDS-style figures (BUILD_PLAN 6.6) for all 23 islands and for Kaafu."""
    origins, areas = _areas(islands)
    reach_same_day = {}
    for origin in origins.index:
        reach, _ = routing.earliest_arrival(conns, origin, 0, cfg)
        reach_same_day[origin] = any(s.startswith("T_") and at < 1440 for s, at in reach.items())
    walk = facilities.set_index("facility_id")["walk_minutes"]
    nearest_facility = origins["health_facility_ids"].map(
        lambda ids: cfg.ACCESS_MIN + min(walk[f] for f in str(ids).split()))
    direct = _direct_boat_islands(conns)
    gm_median = _per_island_minutes(results, "gm_hospital")
    any_median = _per_island_minutes(results, "any_hospital")

    tests = {
        "scheduled_boat_to_greater_male_direct":
            (origins.index.isin(direct), f"a boat on {cfg.DAY} reaches Greater Malé without changing"),
        "scheduled_boat_to_greater_male_same_day":
            (origins.index.map(reach_same_day).astype(bool),
             f"Greater Malé reachable by boat before 24:00 on {cfg.DAY}, changes allowed"),
        "health_facility_within_30":
            (nearest_facility <= 30, "ACCESS_MIN + walk from the harbour to the on-island facility"),
        "gm_hospital_within_120_day_median":
            (gm_median.reindex(origins.index) <= 120, "daytime median, Greater Malé hospital"),
        "any_hospital_within_120_day_median":
            (any_median.reindex(origins.index) <= 120, "daytime median, any hospital incl. atoll"),
    }
    rows = []
    for indicator, (passes, definition) in tests.items():
        passes = pd.Series(np.asarray(passes), index=origins.index)
        for area, mask in areas.items():
            pop = origins.loc[mask, "population_2022"]
            within = int(pop[passes[mask]].sum())
            rows.append(dict(indicator=indicator, area=area, population_within=within,
                             population=int(pop.sum()), share_pct=round(100 * within / pop.sum(), 1),
                             definition=definition))
    return pd.DataFrame(rows)


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

    # Extra tables for the dashboard and slides 5-6 (not in the section 4 contracts).
    within = pd.concat([population_within(results, islands, cfg, target, dep)
                        for target in routing.TARGET_FACILITIES
                        for dep in [None, *range(0, 1440, cfg.STEP_MIN)]])
    hdx = pd.read_csv(sheets / "hdx_benchmark.csv", encoding="utf-8-sig")
    within.to_csv(processed / "population_within.csv", index=False)
    hdx_comparison(within[within["departure"] == "day_median"], hdx).to_csv(
        processed / "hdx_comparison.csv", index=False)
    nsds_figures(results, islands, facilities, conns, cfg).to_csv(processed / "nsds_figures.csv", index=False)
    return results, summary


if __name__ == "__main__":
    main()
