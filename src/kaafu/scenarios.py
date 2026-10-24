"""What-if scenarios behind the dashboard sliders (BUILD_PLAN 6.7).

M4's entry point is run_scenario(params) -> (access_results, island_summary).
params (all optional; leaving one out means no change):
    ferry_factor         {route_id: factor}, 0.5 to 3
    extra_runs           [(route_id, minute), ...] one extra departure each, on DAY
    thulusdhoo_hospital  True adds K.Thulusdhoo as an atoll-level hospital (any_hospital)
    observed             True uses observed boat times        -- waiting for M2's observed_pairs.csv
    bus_factor           bus frequency factor                 -- waiting for M1's last_mile.csv
    taxi_availability    0 to 1, cuts the unserved share      -- waiting for M1's taxi function
    label                the scenario column value (default "base" or "scenario")
"""
import json

import pandas as pd

from kaafu import indicators, routing

DEFAULTS = dict(ferry_factor={}, extra_runs=[], thulusdhoo_hospital=False, observed=False,
                bus_factor=1.0, taxi_availability=0.0)
PENDING = {"observed": "M2's observed_pairs.csv", "bus_factor": "M1's last_mile.csv (bus waits)",
           "taxi_availability": "M1's taxi function"}
THULUSDHOO_ID = "H10"
BEST_FERRY_CHANGE_CSV = "best_ferry_change.csv"  # extra table, not in the section 4 contracts

_inputs_cache = {}
_results_cache = {}


def _finish(conns):
    conns = conns.sort_values(["dep_min", "arr_min"], kind="stable").reset_index(drop=True)
    conns["conn_id"] = range(1, len(conns) + 1)
    return conns


def _first_departures(legs):
    return legs.groupby("trip_id")["dep_min"].min().sort_values()


def _pattern(trip_legs):
    trip_legs = trip_legs.sort_values("dep_min")
    return tuple(zip(trip_legs["from_stop"], trip_legs["to_stop"]))


def _new_id(template, tag):
    """A copy's trip_id; next-day copies keep the _d2 suffix at the end."""
    if template.endswith("_d2"):
        return f"{template[:-3]}~{tag}_d2"
    return f"{template}~{tag}"


def _copy_trip(conns, trip_id, offset, new_id):
    legs = conns[conns["trip_id"] == trip_id].copy()
    legs["dep_min"] += offset
    legs["arr_min"] += offset
    legs["trip_id"] = new_id
    legs["estimated"] = "yes"
    legs["source"] = "scenario"
    return legs


def scale_route(conns, route_id, factor):
    """Re-space round(n x factor) runs of a route evenly between its first and last departure.

    Done separately for each direction (stop pattern) and each day, so the morning boat
    to Malé and the afternoon boat back stay what they are. Each new run copies the
    original run nearest to its time, all legs shifted by the same offset. A route with
    a single run that day has no span to re-space and is left alone: use extra_run.
    """
    if factor == 1:
        return conns
    keep = conns[conns["route_id"] != route_id]
    route = conns[conns["route_id"] == route_id]
    new = []
    for _, day in route.groupby(route["trip_id"].str.endswith("_d2")):
        firsts = _first_departures(day)
        lo, hi = firsts.min(), firsts.max()
        if lo == hi:
            new.append(day)
            continue
        patterns = {trip: _pattern(legs) for trip, legs in day.groupby("trip_id")}
        for pattern in set(patterns.values()):
            trips = firsts[[t for t in firsts.index if patterns[t] == pattern]]
            m = max(1, round(len(trips) * factor))
            if m == 1:
                new.append(day[day["trip_id"] == trips.index[0]])
                continue
            for k in range(m):
                at = round(lo + k * (hi - lo) / (m - 1))
                template = (trips - at).abs().idxmin()
                new.append(_copy_trip(day, template, at - trips[template], _new_id(template, f"f{k}")))
    return _finish(pd.concat([keep, *new]))


def extra_run(conns, route_id, minute, towards_male=True):
    """Add one run of a route leaving at `minute` on DAY: a copy of its run with the
    closest first departure. With towards_male, only runs that start outside Greater Malé
    are copied (the boat islanders would take to hospital), if the route has any."""
    day = conns[(conns["route_id"] == route_id) & ~conns["trip_id"].str.endswith("_d2")]
    if day.empty:
        raise ValueError(f"route {route_id} has no runs on the service day")
    firsts = _first_departures(day)
    if towards_male:
        start = day.sort_values("dep_min").groupby("trip_id")["from_stop"].first()
        inbound = firsts[[t for t in firsts.index if not start[t].startswith("T_")]]
        firsts = inbound if len(inbound) else firsts
    template = (firsts - minute).abs().idxmin()
    run = _copy_trip(day, template, minute - firsts[template], _new_id(template, f"x{minute}"))
    return _finish(pd.concat([conns, run]))


def thulusdhoo_hospital(facilities, islands, last_mile, cfg):
    """Facilities, any_hospital ids and last mile with a hospital on K.Thulusdhoo.

    Placed at the island's harbour point, with the same walk as its health centre (C04).
    """
    island = islands.set_index("island_key").loc["K.Thulusdhoo"]
    walk = facilities.set_index("facility_id").loc[island["health_facility_ids"].split()[0], "walk_minutes"]
    row = dict(facility_id=THULUSDHOO_ID, name="K. Thulusdhoo Hospital (scenario)", type="hospital",
               level="regional/atoll", island_key="K.Thulusdhoo", island="Thulusdhoo", atoll="K",
               lat=island["harbour_lat"], lon=island["harbour_lon"], walk_minutes=walk,
               location_quality="estimated", source="scenario: hospital under construction")
    facilities = pd.concat([facilities, pd.DataFrame([row])], ignore_index=True)
    new_rows = routing.placeholder_last_mile(facilities[facilities["facility_id"] == THULUSDHOO_ID], cfg)
    return facilities, pd.concat([last_mile, new_rows], ignore_index=True)


def _inputs(cfg):
    key = id(cfg)
    if key not in _inputs_cache:
        _inputs_cache[key] = indicators.load_inputs(cfg)
    return _inputs_cache[key]


def run_scenario(params=None, cfg=None):
    """(access_results, island_summary) for one set of slider values. Cached per params."""
    if cfg is None:
        from kaafu import config as cfg
    params = {**DEFAULTS, **(params or {})}
    for name, needs in PENDING.items():
        if params[name] != DEFAULTS[name]:
            raise NotImplementedError(f"'{name}' needs {needs}, which hasn't landed yet")
    key = json.dumps(params, sort_keys=True, default=str)
    if key in _results_cache:
        return _results_cache[key]

    data = _inputs(cfg)
    conns, facilities, last_mile = data["conns"], data["facilities"], data["last_mile"]
    for route_id, factor in params["ferry_factor"].items():
        conns = scale_route(conns, str(route_id), factor)
    for route_id, minute in params["extra_runs"]:
        conns = extra_run(conns, str(route_id), int(minute))
    targets = None
    if params["thulusdhoo_hospital"]:
        facilities, last_mile = thulusdhoo_hospital(facilities, data["islands"], last_mile, cfg)
        targets = {t: routing.target_hospitals(facilities, t, cfg) for t in routing.TARGETS}
        targets["any_hospital"] = pd.concat(
            [targets["any_hospital"], facilities[facilities["facility_id"] == THULUSDHOO_ID]])

    changed = any(params[k] != DEFAULTS[k] for k in DEFAULTS)
    label = params.get("label") or ("scenario" if changed else "base")
    origins = data["islands"].loc[data["islands"]["role"] == "origin", "island_key"].tolist()
    results = routing.access_results(conns, origins, facilities, last_mile, cfg, label, targets)
    summary = indicators.island_summary(results, data["islands"], conns, cfg)
    _results_cache[key] = (results, summary)
    return results, summary


def _arrival_or_horizon(results, target, cfg):
    """Total minutes per (origin, dep_min); unreachable counted as arriving at the end of
    the two-day horizon (2 x MINUTES_PER_DAY), so minutes saved on those rows are a lower bound."""
    r = results[results["target"] == target].set_index(["origin_key", "dep_min"])["total_min"]
    horizon = 2 * cfg.MINUTES_PER_DAY - r.index.get_level_values("dep_min")
    return r.astype(float).fillna(pd.Series(horizon, index=r.index))


def best_ferry_change(cfg=None, times=None, target="gm_hospital", dep_min=None):
    """Rank one extra run per CFN route x time (BUILD_PLAN 6.6, stretch).

    times: "HH:MM" strings, EVENING_RUN_TIMES by default.
    newly_within_120_pop: people on islands that now reach a hospital within 2 h and didn't
    before -- at any daytime departure, or at dep_min if given. pop_minutes_saved:
    population x mean minutes saved over all departures of the day.
    """
    if cfg is None:
        from kaafu import config as cfg
    times = [indicators.minutes_of(t) for t in (times or cfg.EVENING_RUN_TIMES)]
    base, _ = run_scenario({}, cfg)
    population = _inputs(cfg)["islands"].set_index("island_key")["population_2022"]
    routes = sorted(r for r in _inputs(cfg)["conns"]["route_id"].unique() if r != "VILI")

    def within(results):
        r = results[(results["target"] == target) & results["total_min"].notna()]
        r = r[r["dep_min"] == dep_min] if dep_min is not None else r[
            r["dep_min"].between(cfg.DAYTIME_START_MIN, cfg.DAYTIME_END_MIN)]
        return set(r.loc[r["total_min"] <= 120, "origin_key"])

    base_within, base_minutes = within(base), _arrival_or_horizon(base, target, cfg)
    rows = []
    for route_id in routes:
        for minute in times:
            results, _ = run_scenario({"extra_runs": [(route_id, minute)],
                                       "label": f"extra_{route_id}_{indicators.hhmm(minute)}"}, cfg)
            saved = (base_minutes - _arrival_or_horizon(results, target, cfg)).groupby("origin_key").mean()
            newly = within(results) - base_within
            helped = saved[saved > 0.05]
            helped_pop = population[helped.index]
            pop_minutes = float((helped * helped_pop).sum())
            rows.append(dict(route_id=route_id, run_time=indicators.hhmm(minute),
                             newly_within_120_pop=int(population[list(newly)].sum()),
                             pop_minutes_saved=round(pop_minutes),
                             people_helped=int(helped_pop.sum()),
                             avg_min_saved_per_person=round(pop_minutes / helped_pop.sum()) if len(helped) else 0,
                             islands_helped=" ".join(helped.index)))
    return (pd.DataFrame(rows)
            .sort_values(["newly_within_120_pop", "pop_minutes_saved"], ascending=False)
            .reset_index(drop=True))


def main(cfg=None):
    if cfg is None:
        from kaafu import config as cfg
    table = best_ferry_change(cfg)
    table.to_csv(cfg.PROCESSED / BEST_FERRY_CHANGE_CSV, index=False, encoding=cfg.WRITE_ENCODING)
    return table


if __name__ == "__main__":
    main()
