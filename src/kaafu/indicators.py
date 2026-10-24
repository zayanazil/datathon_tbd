"""Per-island summary and population indicators (BUILD_PLAN 6.6).

main() writes the base scenario's access_results.csv and island_summary.csv.
"""
import numpy as np
import pandas as pd

from kaafu import routing

SUMMARY_COLUMNS = [
    "origin_key", "population", "day_median_min", "best_min", "worst_day_min",
    "last_practical_departure", "boats_per_day", "observed_gap_min",
]

# Extra tables for the dashboard and slides 5-6 (not in the section 4 contracts).
POPULATION_WITHIN_CSV = "population_within.csv"
HDX_COMPARISON_CSV = "hdx_comparison.csv"
NSDS_FIGURES_CSV = "nsds_figures.csv"


def hhmm(minutes):
    return f"{int(minutes) // 60:02d}:{int(minutes) % 60:02d}"


def minutes_of(hh_mm):
    hours, minutes = hh_mm.split(":")
    return int(hours) * 60 + int(minutes)


def _blank_if_inf(x):
    return None if np.isinf(x) else round(float(x), 1)


def _daytime(dep_min, cfg):
    """Departures in the "day" window, DAYTIME_START_MIN to DAYTIME_END_MIN."""
    return dep_min.between(cfg.DAYTIME_START_MIN, cfg.DAYTIME_END_MIN)


def island_summary(results, islands, conns, cfg, target="gm_hospital", observed_gap=None):
    """island_summary.csv from access_results rows for one scenario and target.

    Unreachable departures count as infinite, so a median or worst value that
    is unreachable is left blank. `observed_gap` is observed_gap() by origin, if M2's data is in.
    """
    observed_gap = observed_gap if observed_gap is not None else pd.Series(dtype=float)
    res = results[results["target"] == target]
    population = islands.set_index("island_key")["population_2022"]
    rows = []
    for origin, g in res.groupby("origin_key", sort=False):
        total = g["total_min"].astype(float).fillna(np.inf)
        day = total[_daytime(g["dep_min"], cfg)]
        same_day = g[(g["dep_min"] + total) < cfg.MINUTES_PER_DAY]
        leaving = conns[(conns["from_stop"] == origin) & (conns["dep_min"] < cfg.MINUTES_PER_DAY)]
        rows.append(dict(
            origin_key=origin,
            population=int(population[origin]),
            day_median_min=_blank_if_inf(np.median(day)),
            best_min=_blank_if_inf(day.min()),
            worst_day_min=_blank_if_inf(day.max()),
            last_practical_departure=hhmm(same_day["dep_min"].max()) if len(same_day) else "none",
            boats_per_day=leaving["trip_id"].nunique(),
            observed_gap_min=observed_gap.get(origin),
        ))
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def scheduled_vs_observed(conns, observed_trips, stop_island, cfg):
    """Boat minutes from each island to Greater Malé: scheduled_min, observed_min, observed_trips.

    Scheduled: the quickest timetabled ride from the island to a Greater Malé terminal on
    one trip (DAY or NEXT_DAY). Observed: M2's median of all tracked trips from the island
    to Malé, Hulhumalé or Villimalé, if there are at least OBSERVED_MIN_TRIPS.
    """
    scheduled = {}
    for _, trip in conns.sort_values("dep_min").groupby("trip_id"):
        legs = list(trip.itertuples())
        for i, leg in enumerate(legs):
            if leg.from_stop.startswith("T_"):
                continue
            at_gm = next((later.arr_min for later in legs[i:] if later.to_stop.startswith("T_")), None)
            if at_gm is not None:
                ride = at_gm - leg.dep_min
                scheduled[leg.from_stop] = min(scheduled.get(leg.from_stop, ride), ride)
    gm_islands = set(stop_island.values())
    to_gm = observed_trips[observed_trips["to_key"].isin(gm_islands)].groupby("from_key")["duration_min"]
    enough = to_gm.size() >= cfg.OBSERVED_MIN_TRIPS
    return pd.DataFrame({"scheduled_min": pd.Series(scheduled, dtype=float),
                         "observed_min": to_gm.median()[enough],
                         "observed_trips": to_gm.size()[enough]})


def observed_gap(conns, observed_trips, stop_island, cfg):
    """Scheduled minus observed boat minutes to Greater Malé (see scheduled_vs_observed).
    Positive means the boats people actually take are faster than the timetable."""
    both = scheduled_vs_observed(conns, observed_trips, stop_island, cfg)
    return (both["scheduled_min"] - both["observed_min"]).dropna().round(1)


def _per_island_share(results, target, cfg, threshold, dep_min=None):
    """{origin: share of departures within threshold} at one departure (0 or 1), or over
    every daytime departure when dep_min is None: the chance that someone who needs a
    hospital at a random daytime moment gets there in time. Unreachable never counts."""
    res = results[results["target"] == target]
    res = res[_daytime(res["dep_min"], cfg)] if dep_min is None else res[res["dep_min"] == dep_min]
    within = res["total_min"].astype(float).fillna(np.inf) <= threshold
    return within.groupby(res["origin_key"]).mean()


def _areas(islands):
    origins = islands[islands["role"] == "origin"].set_index("island_key")
    return origins, {"Kaafu": origins["atoll"] == "K", "All 23": origins["atoll"].notna()}


def population_within(results, islands, cfg, target="gm_hospital", dep_min=None):
    """Share of population within each of THRESHOLDS_MIN, for Kaafu and all 23 islands.

    At one departure time, or averaged over every daytime departure when dep_min is None
    (each island's population times its share of daytime departures that make it).
    """
    origins, areas = _areas(islands)
    rows = []
    for area, mask in areas.items():
        pop = origins.loc[mask, "population_2022"]
        for threshold in cfg.THRESHOLDS_MIN:
            share = _per_island_share(results, target, cfg, threshold, dep_min).reindex(pop.index).fillna(0)
            within = int(round((pop * share).sum()))
            rows.append(dict(area=area, target=target,
                             departure="daytime" if dep_min is None else hhmm(dep_min),
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


def _direct_boat_islands(conns, cfg):
    """Islands where a boat leaving on DAY reaches a Greater Malé terminal on the same trip."""
    day = conns[conns["dep_min"] < cfg.MINUTES_PER_DAY].sort_values("dep_min")
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
        reach_same_day[origin] = any(s.startswith("T_") and at < cfg.MINUTES_PER_DAY
                                     for s, at in reach.items())
    walk = facilities.set_index("facility_id")["walk_minutes"]
    nearest_facility = origins["health_facility_ids"].map(
        lambda ids: cfg.ACCESS_MIN + min(walk[f] for f in str(ids).split()))
    direct = _direct_boat_islands(conns, cfg)
    gm_share = _per_island_share(results, "gm_hospital", cfg, 120)
    any_share = _per_island_share(results, "any_hospital", cfg, 120)

    tests = {
        "scheduled_boat_to_greater_male_direct":
            (origins.index.isin(direct), f"a boat on {cfg.DAY} reaches Greater Malé without changing"),
        "scheduled_boat_to_greater_male_same_day":
            (origins.index.map(reach_same_day).astype(bool),
             f"Greater Malé reachable by boat before 24:00 on {cfg.DAY}, changes allowed"),
        "health_facility_within_30":
            (nearest_facility <= 30, "ACCESS_MIN + walk from the harbour to the on-island facility"),
        "gm_hospital_within_120_daytime":
            (gm_share.reindex(origins.index).fillna(0),
             "averaged over daytime departures, Greater Malé hospital"),
        "any_hospital_within_120_daytime":
            (any_share.reindex(origins.index).fillna(0),
             "averaged over daytime departures, any hospital incl. atoll"),
    }
    rows = []
    for indicator, (passes, definition) in tests.items():
        passes = pd.Series(np.asarray(passes, dtype=float), index=origins.index)
        for area, mask in areas.items():
            pop = origins.loc[mask, "population_2022"]
            within = int(round((pop * passes[mask]).sum()))
            rows.append(dict(indicator=indicator, area=area, population_within=within,
                             population=int(pop.sum()), share_pct=round(100 * within / pop.sum(), 1),
                             definition=definition))
    return pd.DataFrame(rows)


def load_last_mile(facilities, cfg):
    """M1's last_mile.csv if it has landed, else the walk-only placeholder
    (from M1's terminals.csv if that has landed, else PLACEHOLDER_TERMINALS)."""
    if cfg.LAST_MILE_CSV.exists():
        return pd.read_csv(cfg.LAST_MILE_CSV, encoding=cfg.READ_ENCODING)
    terminals = None
    if cfg.TERMINALS_CSV.exists():
        terminals = routing.terminals_from_csv(pd.read_csv(cfg.TERMINALS_CSV, encoding=cfg.READ_ENCODING))
    return routing.placeholder_last_mile(facilities, cfg, terminals)


def _read_if_there(path, cfg):
    return pd.read_csv(path, encoding=cfg.READ_ENCODING) if path.exists() else None


def load_inputs(cfg):
    """Everything an M3 run needs. M2's observed files are None until they land."""
    read = dict(encoding=cfg.READ_ENCODING)
    facilities = pd.read_csv(cfg.FACILITIES_CSV, **read)
    conns = pd.read_csv(cfg.CONNECTIONS_CSV, dtype={"route_id": str}, **read)
    terminals = _read_if_there(cfg.TERMINALS_CSV, cfg)
    stop_island = routing.terminals_from_csv(terminals) if terminals is not None else routing.PLACEHOLDER_TERMINALS
    stop_island = {stop: island for stop, (island, _, _) in stop_island.items()}
    observed_trips = _read_if_there(cfg.OBSERVED_TRIPS_CSV, cfg)
    return dict(
        conns=conns,
        islands=pd.read_csv(cfg.ISLANDS_CSV, **read),
        facilities=facilities,
        last_mile=load_last_mile(facilities, cfg),
        stop_island=stop_island,
        observed_pairs=_read_if_there(cfg.OBSERVED_PAIRS_CSV, cfg),
        observed_trips=observed_trips,
        observed_gap=(observed_gap(conns, observed_trips, stop_island, cfg)
                      if observed_trips is not None else None),
    )


def main(cfg=None):
    """Base run: door-to-door results and the indicators built from them.

    Writes access_results.csv (every island x 15-min departure x target),
    island_summary.csv, population_within.csv, hdx_comparison.csv and
    nsds_figures.csv to data/processed/.
    """
    if cfg is None:
        from kaafu import config as cfg
    data = load_inputs(cfg)
    conns, islands, facilities = data["conns"], data["islands"], data["facilities"]
    origins = islands.loc[islands["role"] == "origin", "island_key"].tolist()

    results = routing.access_results(conns, origins, facilities, data["last_mile"], cfg)
    summary = island_summary(results, islands, conns, cfg, observed_gap=data["observed_gap"])
    write = dict(index=False, encoding=cfg.WRITE_ENCODING)
    results.to_csv(cfg.ACCESS_RESULTS_CSV, **write)
    summary.to_csv(cfg.ISLAND_SUMMARY_CSV, **write)

    within = pd.concat([population_within(results, islands, cfg, target, dep)
                        for target in routing.TARGETS
                        for dep in [None, *range(0, cfg.MINUTES_PER_DAY, cfg.STEP_MIN)]])
    hdx = pd.read_csv(cfg.HDX_BENCHMARK_CSV, encoding=cfg.READ_ENCODING)
    within.to_csv(cfg.PROCESSED / POPULATION_WITHIN_CSV, **write)
    hdx_comparison(within[within["departure"] == "daytime"], hdx).to_csv(
        cfg.PROCESSED / HDX_COMPARISON_CSV, **write)
    nsds_figures(results, islands, facilities, conns, cfg).to_csv(cfg.PROCESSED / NSDS_FIGURES_CSV, **write)
    return results, summary


if __name__ == "__main__":
    main()
