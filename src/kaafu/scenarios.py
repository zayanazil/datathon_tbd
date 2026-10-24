"""What-if changes behind the dashboard sliders (BUILD_PLAN 6.7).

run_scenario(params) -> (access_results, island_summary), where params may carry:
  day                  service day label, default config.DAY
  observed             swap in FollowMe boat times
  ferry_factor         x0.5-x3, applied to ferry_route (or every route if None)
  ferry_route          route_id or None
  extra_run            (route_id, dep_min) or None: one more Malé-bound departure
  bus_factor           x0.5-x3, divides bus headways
  taxi_availability    0-1, multiplies expired_share by (1 - value)
  thulusdhoo_hospital  add K.Thulusdhoo as an atoll-level hospital
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from . import config as C
from .geo import footpaths
from .indicators import access_results, island_summary, targets
from .lastmile import atoll_rows
from .lastmile import build as build_lastmile
from .load import load_facilities, load_last_mile, load_origins, load_processed
from .routing import Network
from .timetable import build_connections, legs, trip_patterns

DEFAULTS = {"day": C.DAY, "observed": False, "ferry_factor": 1.0, "ferry_route": None, "extra_run": None,
            "bus_factor": 1.0, "taxi_availability": 0.0, "thulusdhoo_hospital": False}


@lru_cache(maxsize=1)
def _legs() -> pd.DataFrame:
    return legs()


@lru_cache(maxsize=1)
def base_last_mile() -> pd.DataFrame:
    """M1's last_mile.csv (data/processed); built from avas_hourly.csv only if it is missing."""
    lm = load_last_mile()
    return lm if lm is not None else build_lastmile(load_processed("avas_hourly.csv"))


def _respread(dl: pd.DataFrame, route, factor: float) -> pd.DataFrame:
    """Re-spread each route pattern's departures evenly between its first and last."""
    if factor == 1:
        return dl
    keep, new = [], []
    pats = trip_patterns(dl)
    for (rid, pattern), g in pats.groupby(["route_id", "pattern"]):
        if route is not None and rid != str(route):
            keep.append(g["trip_id"])
            continue
        n = max(1, int(round(len(g) * factor)))
        first, last = g["first_dep"].min(), g["first_dep"].max()
        if first == last and n > 1:  # a single daily run: spread the extra runs over the next 10 hours
            last = min(first + 600, 23 * 60)
        template = dl[dl["trip_id"] == g["trip_id"].iloc[0]].sort_values("dep_min")
        for k, t0 in enumerate(np.linspace(first, last, n).round().astype(int)):
            new.append(_shift_trip(template, t0, f"{rid}:x{k}"))
    out = dl[dl["trip_id"].isin(pd.concat(keep))] if keep else dl.iloc[0:0]
    return pd.concat([out, *new], ignore_index=True)


def _shift_trip(template: pd.DataFrame, t0: int, trip_id: str) -> pd.DataFrame:
    d = t0 - template["dep_min"].iloc[0]
    return template.assign(dep_min=template["dep_min"] + d, arr_min=template["arr_min"] + d,
                           trip_id=trip_id, estimated="scenario", source="scenario")


def malebound_template(dl: pd.DataFrame, route) -> pd.DataFrame | None:
    """The route's most common pattern that ends at a Greater Malé terminal."""
    pats = trip_patterns(dl)
    pats = pats[(pats["route_id"] == str(route)) & pats["pattern"].map(lambda p: str(p[-1]).startswith("T_"))]
    if pats.empty:
        return None
    common = pats["pattern"].value_counts().index[0]
    top = pats.loc[pats["pattern"].map(lambda p: p == common), "trip_id"].iloc[0]
    return dl[dl["trip_id"] == top].sort_values("dep_min")


def _add_run(dl: pd.DataFrame, route, dep_min: int) -> pd.DataFrame:
    template = malebound_template(_legs().pipe(lambda lg: lg.drop(columns="days")), route)
    if template is None:
        return dl
    return pd.concat([dl, _shift_trip(template, dep_min, f"{route}:extra")], ignore_index=True)


def scenario_last_mile(p: dict) -> pd.DataFrame:
    lm = base_last_mile().copy()
    taxi = lm["mode"] == "taxi"
    lm.loc[taxi, "minutes"] -= lm.loc[taxi, "expired_share"] * C.TAXI_RETRY_MIN * p["taxi_availability"]
    bus = lm["mode"] == "bus"
    lm.loc[bus, "minutes"] -= lm.loc[bus, "bus_wait_min"] * (1 - 1 / p["bus_factor"])
    if p["thulusdhoo_hospital"]:
        walk = load_facilities().set_index("facility_id").loc["C04", "walk_minutes"]
        extra = pd.DataFrame(atoll_rows("K.Thulusdhoo", C.THULUSDHOO_HOSPITAL_ID, walk), columns=lm.columns)
        lm = pd.concat([lm, extra], ignore_index=True)
    return lm


def scenario_name(p: dict) -> str:
    diff = {k: v for k, v in p.items() if DEFAULTS.get(k) != v and k != "day"}
    return "base" if not diff else ";".join(f"{k}={v}" for k, v in sorted(diff.items()))


def connections_for(p: dict) -> pd.DataFrame:
    def edit(dl):
        dl = _respread(dl, p["ferry_route"], p["ferry_factor"])
        if p["extra_run"]:
            dl = _add_run(dl, *p["extra_run"])
        return dl
    return build_connections(p["day"], edit=edit, observed=p["observed"], all_legs=_legs())


def run_scenario(params: dict | None = None, departures=None, with_summary: bool = True):
    p = {**DEFAULTS, **(params or {})}
    conns = connections_for(p)
    net = Network.build(conns, scenario_last_mile(p), footpaths())
    origins = load_origins()
    access = access_results(net, origins, scenario_name(p), p["day"], targets(p["thulusdhoo_hospital"]), departures)
    if not with_summary:
        return access, None
    return access, island_summary(access, origins, conns)


def best_ferry_change(params: dict | None = None, window=(12 * 60, 1440)) -> pd.DataFrame:
    """Rank one added evening departure per route by people newly within 2 h, then minutes saved.

    Measured over leave-home times in `window` (default 12:00-23:45), population-weighted:
    'people newly within 2 h' is the gain in population x share of those departure slots within 2 h.
    """
    p = {**DEFAULTS, **(params or {})}
    deps = range(window[0], window[1], C.STEP_MIN)
    origins = load_origins()
    w = origins.set_index("island_key")["population_2022"]

    def score(access):
        a = access[access["target"] == "gm_hospital"]
        m = a.pivot(index="origin_key", columns="dep_min", values="total_min").astype(float)
        within = (m <= C.HEADLINE_THRESHOLD_MIN).mean(axis=1)
        return (within * w).sum(), (m.fillna(1440).clip(upper=1440).mean(axis=1) * w).sum() / w.sum()

    base_within, base_min = score(run_scenario(p, deps, with_summary=False)[0])
    dl = _legs().drop(columns="days")
    rows = []
    for route in sorted(dl["route_id"].unique()):
        if malebound_template(dl, route) is None:
            continue
        for t in C.EVENING_RUN_TIMES:
            within, mins = score(run_scenario({**p, "extra_run": (route, t)}, deps, with_summary=False)[0])
            rows.append({"route_id": route, "added_departure": f"{t // 60:02d}:{t % 60:02d}",
                         "people_newly_within_2h": round(within - base_within),
                         "pop_weighted_min_saved": round(base_min - mins, 1)})
    out = pd.DataFrame(rows)
    return out.sort_values(["people_newly_within_2h", "pop_weighted_min_saved"], ascending=False) \
        .reset_index(drop=True) if not out.empty else out
