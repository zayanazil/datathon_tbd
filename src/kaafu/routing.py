"""Earliest arrival over boat connections, then door-to-door hospital times (BUILD_PLAN 6.2).

A connection scan: go through every boat leg in departure order and keep the
earliest time each island or terminal can be reached. Every parameter comes
from the `cfg` passed in (src/kaafu/config.py on the day).
"""
import bisect
import math

import pandas as pd

TARGETS = ("gm_hospital", "any_hospital")

# Used until M1's terminals.csv lands: the bus stops named in BUILD_PLAN section 4,
# coordinates from Team Kandu's rtl_bus_stops.csv.
PLACEHOLDER_TERMINALS = {
    "T_MALE_NORTH": ("K.Malé", 4.178784, 73.513422),      # Jetty NO5, code 1008
    "T_MALE_WEST": ("K.Malé", 4.172281, 73.502060),       # Maafannu Ferry Terminal, 1101
    "T_HULHUMALE": ("K.Hulhumalé", 4.216739, 73.537853),  # Hulhumalé Ferry Terminal, 507
    "T_VILLIMALE": ("K.Villimalé", 4.175107, 73.486942),  # Villimale Ferry Terminal, 1301
}


def target_hospitals(facilities, target, cfg):
    """gm_hospital: GM_HOSPITALS. any_hospital: those plus ATOLL_HOSPITALS."""
    ids = list(cfg.GM_HOSPITALS)
    if target == "any_hospital":
        ids += list(cfg.ATOLL_HOSPITALS.values())
    ids = [f for f in ids if cfg.INCLUDE_SENAHIYA or f != cfg.SENAHIYA_ID]
    return facilities[facilities["facility_id"].isin(ids)]


def terminals_from_csv(terminals):
    """M1's terminals.csv rows in the {terminal_id: (island_key, lat, lon)} form used here."""
    return {r.terminal_id: (r.island_key, r.lat, r.lon) for r in terminals.itertuples()}


def _metres(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371000 * math.asin(math.sqrt(a))


def placeholder_last_mile(facilities, cfg, terminals=None):
    """Walk-only rows in the last_mile.csv layout, used until M1's file lands.

    Terminal to hospital on the same island: TERMINAL_EXIT_MIN + straight line / WALK_M_PER_MIN.
    Atoll-hospital islands: TERMINAL_EXIT_MIN + the hospital's walk_minutes.
    `terminals` is {terminal_id: (island_key, lat, lon)}; PLACEHOLDER_TERMINALS by default.
    """
    terminals = terminals or PLACEHOLDER_TERMINALS
    rows = []
    for f in facilities[facilities["type"] == "hospital"].itertuples():
        stops = [(tid, _metres(lat, lon, f.lat, f.lon) / cfg.WALK_M_PER_MIN)
                 for tid, (island, lat, lon) in terminals.items() if island == f.island_key]
        if not stops:
            stops = [(f.island_key, f.walk_minutes)]
        for stop_id, walk in stops:
            for hour in range(24):
                rows.append((stop_id, f.facility_id, hour, "walk",
                             round(cfg.TERMINAL_EXIT_MIN + walk, 1), True, "placeholder walk"))
    return pd.DataFrame(rows, columns=["stop_id", "facility_id", "hour", "mode",
                                       "minutes", "available", "detail"])


def last_mile_index(last_mile):
    """{(stop_id, hour): [(facility_id, minutes, mode), ...]}, fastest available mode only."""
    lm = last_mile[last_mile["available"].astype(str).str.lower().isin(["true", "yes", "1"])]
    lm = lm.sort_values("minutes").drop_duplicates(["stop_id", "facility_id", "hour"])
    index = {}
    for r in lm.itertuples():
        index.setdefault((r.stop_id, int(r.hour)), []).append((r.facility_id, r.minutes, r.mode))
    return index


def as_rows(conns):
    """Connections as a list of row tuples. Convert once and pass the list to
    earliest_arrival when scanning many times; a DataFrame is converted per call."""
    return conns if isinstance(conns, list) else list(conns.itertuples(index=False))


def earliest_arrival(conns, origin, t, cfg):
    """Earliest reach time at every stop leaving home on `origin` at minute `t`.

    `conns` (DataFrame or as_rows() list) must be sorted by dep_min. came_by[stop] = (last leg into stop, the
    leg where that trip was boarded), so the journey can be walked back.
    """
    rows = as_rows(conns)
    reach = {origin: t + cfg.ACCESS_MIN}
    came_by = {}
    boarded = {}
    start = bisect.bisect_left(rows, t, key=lambda c: c.dep_min)  # skip boats that left before t
    for c in rows[start:]:
        on_board = c.trip_id in boarded
        need = 0 if c.from_stop == origin else cfg.BOAT_TRANSFER_MIN
        can_board = c.from_stop in reach and reach[c.from_stop] + need <= c.dep_min
        if on_board or can_board:
            if not on_board:
                boarded[c.trip_id] = c
            if c.arr_min < reach.get(c.to_stop, math.inf):
                reach[c.to_stop] = c.arr_min
                came_by[c.to_stop] = (c, boarded[c.trip_id])
    return reach, came_by


def journey(came_by, origin, stop):
    """Boat legs from origin to stop, one per trip: (route_id, from, dep, to, arr)."""
    legs = []
    while stop != origin:
        last, entered = came_by[stop]
        legs.append((last.route_id, entered.from_stop, entered.dep_min, stop, last.arr_min))
        stop = entered.from_stop
    return legs[::-1]


def latest_departure(conns, origin, t, stop, at, cfg):
    """came_by of the scan from the latest departure >= t that still reaches `stop` by `at`."""
    lo, hi = t, int(at)  # reach is monotone in the departure time, so bisect on it
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if earliest_arrival(conns, origin, mid, cfg)[0].get(stop, math.inf) <= at:
            lo = mid
        else:
            hi = mid - 1
    return earliest_arrival(conns, origin, lo, cfg)[1]


UNREACHABLE ="unreachable: no hospital by the end of NEXT_DAY's boats"


def door_to_door(conns, origin, t, hospitals, lm_index, cfg, scan=None):
    """Fastest trip from home on `origin` at `t` to any of `hospitals`.

    Returns the access_results.csv fields from facility_id on; total_min is None
    when no hospital is reached within the two days of connections. `scan` is an
    earlier earliest_arrival() result for the same origin and t, to reuse it.
    """
    if origin in set(hospitals["island_key"]):
        f = hospitals[hospitals["island_key"] == origin].iloc[0]
        return dict(facility_id=f.facility_id, total_min=cfg.ACCESS_MIN, wait_min=0, boat_min=0,
                    transfer_min=0, lastmile_mode="on_island", lastmile_min=0, n_boats=0,
                    path=f"{origin}>{f.facility_id}")

    wanted = set(hospitals["facility_id"])
    conns = as_rows(conns)
    reach, came_by = scan or earliest_arrival(conns, origin, t, cfg)
    best = None
    for stop, at in reach.items():
        if stop == origin:
            continue
        for facility_id, minutes, mode in lm_index.get((stop, (int(at) // 60) % 24), []):
            if facility_id in wanted and (best is None or at + minutes < best[0]):
                best = (at + minutes, stop, facility_id, minutes, mode)
    if best is None:
        return dict(facility_id=None, total_min=None, wait_min=None, boat_min=None,
                    transfer_min=None, lastmile_mode=None, lastmile_min=None, n_boats=0,
                    path=UNREACHABLE)

    arrival, stop, facility_id, minutes, mode = best
    legs = journey(came_by, origin, stop)
    if len(legs) > 1:
        # Same arrival, but on the latest boats that still make it, so the waiting
        # happens at home rather than overnight at a transfer island (e.g. ADh on Wed).
        legs = journey(latest_departure(conns, origin, t, stop, reach[stop], cfg), origin, stop)
    transfers = sum(nxt[2] - prev[4] for prev, nxt in zip(legs, legs[1:]))
    path = ">".join([origin] + [f"{to}({route})" for route, _, _, to, _ in legs] + [mode, facility_id])
    return dict(facility_id=facility_id, total_min=round(arrival - t, 1),
                wait_min=legs[0][2] - (t + cfg.ACCESS_MIN),
                boat_min=sum(arr - dep for _, _, dep, _, arr in legs),
                transfer_min=transfers, lastmile_mode=mode, lastmile_min=minutes,
                n_boats=len(legs), path=path)


ACCESS_COLUMNS = [
    "scenario", "day_type", "origin_key", "dep_min", "target", "facility_id", "total_min",
    "wait_min", "boat_min", "transfer_min", "lastmile_mode", "lastmile_min", "n_boats", "path",
]


def access_results(conns, origins, facilities, last_mile, cfg, scenario="base", targets=None):
    """access_results.csv: every origin x departure (every STEP_MIN) x target.

    `targets` maps target -> hospital rows; by default target_hospitals() for each of TARGETS.
    """
    lm_index = last_mile_index(last_mile)
    if targets is None:
        targets = {target: target_hospitals(facilities, target, cfg) for target in TARGETS}
    conn_rows = as_rows(conns)
    rows = []
    for origin in origins:
        for t in range(0, cfg.MINUTES_PER_DAY, cfg.STEP_MIN):
            scan = earliest_arrival(conn_rows, origin, t, cfg)
            for target, hospitals in targets.items():
                r = door_to_door(conn_rows, origin, t, hospitals, lm_index, cfg, scan)
                rows.append(dict(scenario=scenario, day_type=cfg.DAY, origin_key=origin,
                                 dep_min=t, target=target, **r))
    return pd.DataFrame(rows, columns=ACCESS_COLUMNS)
