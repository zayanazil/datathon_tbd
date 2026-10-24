"""What-if scenarios behind the dashboard sliders (BUILD_PLAN 6.7).

M4's entry point is run_scenario(params) -> (access_results, island_summary).
params (all optional; leaving one out means no change):
    ferry_factor         {route_id: factor}, 0.5 to 3
    extra_runs           [(route_id, minute), ...] one extra departure each, on DAY
    thulusdhoo_hospital  True adds K.Thulusdhoo as an atoll-level hospital (any_hospital)
    observed             True re-times legs with M2's observed slow medians (observed_durations)
    speedboats           with observed, also add synthetic speedboat departures (default True)
    bus_factor           bus frequency factor, 0.5 to 3 (divides the wait)
    taxi_availability    0 to 1, cuts the Avas unserved share by that fraction
    label                the scenario column value (default "base" or "scenario")
"""
import json
import re

import pandas as pd

from kaafu import indicators, routing

DEFAULTS = dict(ferry_factor={}, extra_runs=[], thulusdhoo_hospital=False, observed=False,
                speedboats=True, bus_factor=1.0, taxi_availability=0.0)
SPEEDBOAT_ROUTE = "SPEEDBOAT"  # route_id of the synthetic speedboat legs
WAIT_IN_DETAIL = re.compile(r"wait (\d+(?:\.\d+)?)")  # M1's last_mile.csv detail, e.g. "wait 7.5"
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


def observed_durations(conns, pairs, stop_island, cfg):
    """Scheduled legs re-timed with M2's observed `slow` medians (BUILD_PLAN 6.4 step 8).

    A leg takes the median of its island pair where n_trips >= OBSERVED_MIN_TRIPS and the
    median is at most OBSERVED_MAX_SLOWDOWN x the scheduled time (the slow class also holds
    cargo dhonis). Departures stay as scheduled, except that a boat can't leave a stop before
    it arrives there, so a later leg of a delayed trip leaves late.
    `stop_island` maps terminal IDs to island keys, as M2's pairs use island keys.
    """
    slow = pairs[(pairs["speed_class"] == "slow") & (pairs["n_trips"] >= cfg.OBSERVED_MIN_TRIPS)]
    median = slow.set_index(["from_key", "to_key"])["median_min"].to_dict()
    conns = conns.sort_values(["trip_id", "dep_min"]).copy()
    arrived = {}
    for i, c in zip(conns.index, conns.itertuples()):
        dep = max(c.dep_min, arrived.get(c.trip_id, c.dep_min))
        scheduled = c.arr_min - c.dep_min
        observed = median.get((stop_island.get(c.from_stop, c.from_stop),
                               stop_island.get(c.to_stop, c.to_stop)))
        if observed is not None and observed <= cfg.OBSERVED_MAX_SLOWDOWN * scheduled:
            conns.loc[i, ["estimated", "source"]] = ["yes", "observed FollowMe slow median"]
            duration = round(observed)
        else:
            duration = scheduled
        conns.loc[i, ["dep_min", "arr_min"]] = [dep, dep + duration]
        arrived[c.trip_id] = dep + duration
    return _finish(conns)


def speedboat_departures(pairs, stop_island, cfg):
    """Synthetic speedboat legs from M2's busy `fast` pairs into Greater Malé.

    For each origin -> Greater Malé pair with trips_per_day >= SPEEDBOAT_MIN_TRIPS_PER_DAY:
    a departure every round((last_hour - first_hour) x 60 / trips_per_day) minutes from
    first_hour to last_hour, taking the observed median, on DAY and again on NEXT_DAY.
    They arrive at the island's first terminal (Malé: T_MALE_NORTH, as for the CFN).
    Observed boat movements, not a published schedule: estimated = yes.
    """
    island_terminal = {}
    for stop, island in stop_island.items():
        island_terminal.setdefault(island, stop)
    busy = pairs[(pairs["speed_class"] == "fast")
                 & (pairs["trips_per_day"] >= cfg.SPEEDBOAT_MIN_TRIPS_PER_DAY)
                 & pairs["to_key"].isin(island_terminal) & ~pairs["from_key"].isin(island_terminal)]
    rows = []
    for p in busy.itertuples():
        every = round((p.last_hour - p.first_hour) * 60 / p.trips_per_day)
        for k, dep in enumerate(range(p.first_hour * 60, p.last_hour * 60 + 1, every)):
            for offset, suffix in ((0, ""), (cfg.MINUTES_PER_DAY, "_d2")):
                rows.append(dict(trip_id=f"{SPEEDBOAT_ROUTE}_{p.from_key}_{k:02d}{suffix}",
                                 route_id=SPEEDBOAT_ROUTE, from_stop=p.from_key,
                                 to_stop=island_terminal[p.to_key], dep_min=dep + offset,
                                 arr_min=dep + offset + round(p.median_min), mode="speedboat_observed",
                                 operator="observed (FollowMe)", day_type=cfg.DAY, estimated="yes",
                                 source="observed boat movements, not a published schedule"))
    return pd.DataFrame(rows)


def adjust_last_mile(last_mile, cfg, bus_factor=1.0, taxi_availability=0.0):
    """Last mile with bus waits divided by bus_factor and the taxi unserved share cut.

    Both read the wait from M1's `detail`. Bus: minutes - wait + wait / bus_factor.
    Taxi: the wait is TAXI_BASE_WAIT_MIN + expired_share x TAXI_RETRY_MIN, so the part
    above the base wait shrinks by taxi_availability. Unavailable rows are left alone.
    """
    lm = last_mile.copy()
    wait = lm["detail"].astype(str).str.extract(WAIT_IN_DETAIL)[0].astype(float)
    available = lm["available"].astype(str).str.lower().isin(["true", "yes", "1"]) & wait.notna()
    bus = available & (lm["mode"] == "bus")
    taxi = available & (lm["mode"] == "taxi")
    lm.loc[bus, "minutes"] -= wait[bus] - wait[bus] / bus_factor
    retry_part = (wait[taxi] - cfg.TAXI_BASE_WAIT_MIN).clip(lower=0)
    lm.loc[taxi, "minutes"] -= retry_part * taxi_availability
    lm["minutes"] = lm["minutes"].round(1)
    return lm


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
    key =json.dumps(params, sort_keys=True, default=str)
    if key in _results_cache:
        return _results_cache[key]

    data = _inputs(cfg)
    conns, facilities, last_mile = data["conns"], data["facilities"], data["last_mile"]
    if params["observed"]:
        if data["observed_pairs"] is None:
            raise FileNotFoundError(f"'observed' needs M2's {cfg.OBSERVED_PAIRS_CSV.name}")
        conns = observed_durations(conns, data["observed_pairs"], data["stop_island"], cfg)
        if params["speedboats"]:
            conns = _finish(pd.concat([conns, speedboat_departures(
                data["observed_pairs"], data["stop_island"], cfg)]))
    for route_id, factor in params["ferry_factor"].items():
        conns = scale_route(conns, str(route_id), factor)
    for route_id, minute in params["extra_runs"]:
        conns = extra_run(conns, str(route_id), int(minute))
    if params["bus_factor"] != 1 or params["taxi_availability"] != 0:
        last_mile = adjust_last_mile(last_mile, cfg, params["bus_factor"], params["taxi_availability"])
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
    summary = indicators.island_summary(results, data["islands"], conns, cfg, observed_gap=data["observed_gap"])
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
