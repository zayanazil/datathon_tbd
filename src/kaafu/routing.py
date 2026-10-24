"""Earliest arrival by connection scan, then door-to-door times (BUILD_PLAN 6.2)."""
from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass, field

import pandas as pd

from . import config as C

INF = math.inf


@dataclass
class Network:
    """Sorted boat connections, terminal footpaths and the last-mile table, ready for scanning."""
    conns: list[tuple]                       # (dep, arr, from, to, trip_id, route_id, mode)
    deps: list[int]
    footpaths: dict[str, list[tuple[str, float]]] = field(default_factory=dict)
    # stop -> hour -> list of (facility_id, minutes, mode); fastest available mode only
    lastmile: dict[str, dict[int, list[tuple[str, float, str]]]] = field(default_factory=dict)
    transfer_min: float = C.BOAT_TRANSFER_MIN
    access_min: float = C.ACCESS_MIN

    @classmethod
    def build(cls, conns: pd.DataFrame, last_mile: pd.DataFrame, footpaths=None, **kw) -> "Network":
        c = conns.sort_values(["dep_min", "arr_min"])
        rows = list(zip(c["dep_min"].astype(int), c["arr_min"].astype(int), c["from_stop"], c["to_stop"],
                        c["trip_id"], c["route_id"].astype(str), c["mode"]))
        return cls(conns=rows, deps=[r[0] for r in rows], footpaths=footpaths or {},
                   lastmile=lastmile_lookup(last_mile), **kw)


def lastmile_lookup(last_mile: pd.DataFrame) -> dict:
    lm = last_mile[last_mile["available"].astype(bool)]
    best = lm.sort_values("minutes").drop_duplicates(["stop_id", "facility_id", "hour"])
    out: dict[str, dict[int, list]] = {}
    for stop, fac, hour, minutes, mode in zip(best["stop_id"], best["facility_id"], best["hour"],
                                              best["minutes"], best["mode"]):
        out.setdefault(stop, {}).setdefault(int(hour), []).append((fac, float(minutes), mode))
    return out


def earliest_arrival(net: Network, origin: str, t: float, stop_when=None, on_reach=None):
    """Connection scan from `origin` leaving home at `t`.

    Returns (reach, came_by). `stop_when(dep)` may end the scan early once no later
    departure can help; `on_reach(stop, time)` is told of every improvement.
    came_by[stop] is ("boat", conn) or ("walk", from_stop, minutes).
    """
    reach: dict[str, float] = {origin: t + net.access_min}
    came_by: dict[str, tuple] = {}
    boarded: set[str] = set()
    for i in range(bisect_left(net.deps, t + net.access_min), len(net.conns)):
        c = net.conns[i]
        dep, arr, frm, to, trip = c[0], c[1], c[2], c[3], c[4]
        if stop_when is not None and stop_when(dep):
            break
        if trip not in boarded:
            ready = reach.get(frm, INF) + (0 if frm == origin else net.transfer_min)
            if ready > dep:
                continue
            boarded.add(trip)
        if arr < reach.get(to, INF):
            reach[to] = arr
            came_by[to] = ("boat", c)
            if on_reach is not None:
                on_reach(to, arr)
            for nxt, walk in net.footpaths.get(to, ()):
                if arr + walk < reach.get(nxt, INF):
                    reach[nxt] = arr + walk
                    came_by[nxt] = ("walk", to, walk)
                    if on_reach is not None:
                        on_reach(nxt, arr + walk)
    return reach, came_by


def _best_hospital(net: Network, origin: str, t: float, reach: dict, facilities: set[str]):
    best = (INF, None, None, None, None)  # arrival, stop, facility, mode, lastmile_min
    for stop, at in reach.items():
        hours = net.lastmile.get(stop)
        if not hours:
            continue
        if stop == origin:  # own atoll hospital: just get there
            for fac, _, _ in hours.get(int(t // 60) % 24, ()):
                if fac in facilities and t + net.access_min < best[0]:
                    best = (t + net.access_min, stop, fac, "on island", 0.0)
            continue
        for fac, minutes, mode in hours.get(int(at // 60) % 24, ()):
            if fac in facilities and at + minutes < best[0]:
                best = (at + minutes, stop, fac, mode, minutes)
    return best


def _legs_to(came_by: dict, stop: str, origin: str) -> list[tuple]:
    legs = []
    while stop != origin and stop in came_by:
        how = came_by[stop]
        legs.append(how)
        stop = how[1][2] if how[0] == "boat" else how[1]
    return legs[::-1]


def journey(net: Network, origin: str, t: float, targets: dict[str, set[str]]) -> dict[str, dict]:
    """Door-to-door result for each target (name -> facility ids), from one scan."""
    best = {name: _best_hospital(net, origin, t, {origin: t + net.access_min}, facs)[0]
            for name, facs in targets.items()}

    def on_reach(stop, at):
        for fac, minutes, _ in net.lastmile.get(stop, {}).get(int(at // 60) % 24, ()):
            for name, facs in targets.items():
                if fac in facs and at + minutes < best[name]:
                    best[name] = at + minutes

    # No departure at or after the worst target's best hospital arrival can improve any target.
    reach, came_by = earliest_arrival(net, origin, t, stop_when=lambda dep: dep >= max(best.values()),
                                      on_reach=on_reach)
    out = {}
    for name, facs in targets.items():
        arrival, stop, fac, mode, lm_min = _best_hospital(net, origin, t, reach, facs)
        out[name] = _describe(origin, t, arrival, stop, fac, mode, lm_min, came_by, net)
    return out


def _describe(origin, t, arrival, stop, fac, mode, lm_min, came_by, net) -> dict:
    if arrival == INF:
        return {"facility_id": None, "total_min": None, "wait_min": None, "boat_min": None, "transfer_min": None,
                "lastmile_mode": None, "lastmile_min": None, "n_boats": 0, "path": "unreachable"}
    legs = _legs_to(came_by, stop, origin)
    boats = [l[1] for l in legs if l[0] == "boat"]
    total = arrival - t
    if not boats:
        return {"facility_id": fac, "total_min": total, "wait_min": 0.0, "boat_min": 0.0, "transfer_min": 0.0,
                "lastmile_mode": mode, "lastmile_min": total - net.access_min, "n_boats": 0,
                "path": f"{origin} → {fac} ({mode})"}
    groups: list[list[tuple]] = []
    for c in boats:
        if groups and groups[-1][-1][4] == c[4]:
            groups[-1].append(c)
        else:
            groups.append([c])
    wait = boats[0][0] - (t + net.access_min)
    boat = sum(g[-1][1] - g[0][0] for g in groups)
    reached = arrival - lm_min
    transfer = reached - boats[0][0] - boat
    parts = [origin]
    for g in groups:
        dep = int(g[0][0])
        parts.append(f"[{g[0][5]} {dep // 60 % 24:02d}:{dep % 60:02d}{' +1d' if dep >= 1440 else ''}]")
        parts.extend(c[3] for c in g)
    if legs[-1][0] == "walk":
        parts.append(f"walk→{stop}")
    parts.append(f"{mode}→{fac}")
    return {"facility_id": fac, "total_min": round(total, 1), "wait_min": wait, "boat_min": boat,
            "transfer_min": round(transfer, 1), "lastmile_mode": mode, "lastmile_min": round(lm_min, 1),
            "n_boats": len(groups), "path": " ".join(parts)}
