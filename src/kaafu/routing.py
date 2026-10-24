"""Earliest arrival over boat connections, then door-to-door hospital times (BUILD_PLAN 6.2).

A connection scan: go through every boat leg in departure order and keep the
earliest time each island or terminal can be reached. Every parameter comes
from the `cfg` passed in (src/kaafu/config.py on the day).
"""
import math

import pandas as pd

TARGET_FACILITIES = {
    "gm_hospital": ["H01", "H02", "H03", "H04", "H05", "H06"],
    "any_hospital": ["H01", "H02", "H03", "H04", "H05", "H06", "H07", "H08", "H09"],
}

# Placeholder until M1's terminals.csv: the bus stops named in BUILD_PLAN section 4,
# coordinates from Team Kandu's rtl_bus_stops.csv.
PLACEHOLDER_TERMINALS = {
    "T_MALE_NORTH": ("K.Malé", 4.178784, 73.513422),      # Jetty NO5, code 1008
    "T_MALE_WEST": ("K.Malé", 4.172281, 73.502060),       # Maafannu Ferry Terminal, 1101
    "T_HULHUMALE": ("K.Hulhumalé", 4.216739, 73.537853),  # Hulhumalé Ferry Terminal, 507
    "T_VILLIMALE": ("K.Villimalé", 4.175107, 73.486942),  # Villimale Ferry Terminal, 1301
}


def target_hospitals(facilities, target, cfg):
    ids = [f for f in TARGET_FACILITIES[target] if cfg.INCLUDE_SENAHIYA or f != "H03"]
    return facilities[facilities["facility_id"].isin(ids)]


def _metres(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371000 * math.asin(math.sqrt(a))


def placeholder_last_mile(facilities, cfg, terminals=None):
    """Walk-only rows in the last_mile.csv layout, used until M1's file lands.

    Terminal to hospital on the same island: TERMINAL_EXIT_MIN + straight line / WALK_M_PER_MIN.
    Atoll-hospital islands: TERMINAL_EXIT_MIN + the hospital's walk_minutes.
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


def earliest_arrival(conns, origin, t, cfg):
    """Earliest reach time at every stop leaving home on `origin` at minute `t`.

    `conns` must be sorted by dep_min. came_by[stop] = (last leg into stop, the
    leg where that trip was boarded), so the journey can be walked back.
    """
    reach = {origin: t + cfg.ACCESS_MIN}
    came_by = {}
    boarded = {}
    for c in conns.itertuples():
        if c.dep_min < t:
            continue
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


def door_to_door(conns, origin, t, hospitals, lm_index, cfg):
    """Fastest trip from home on `origin` at `t` to any of `hospitals`.

    Returns the access_results.csv fields from total_min on; total_min is None
    when no hospital is reached within the two days of connections.
    """
    if origin in set(hospitals["island_key"]):
        f = hospitals[hospitals["island_key"] == origin].iloc[0]
        return dict(facility_id=f.facility_id, total_min=cfg.ACCESS_MIN, wait_min=0, boat_min=0,
                    transfer_min=0, lastmile_mode="on_island", lastmile_min=0, n_boats=0,
                    path=f"{origin}>{f.facility_id}")

    wanted = set(hospitals["facility_id"])
    reach, came_by = earliest_arrival(conns, origin, t, cfg)
    best = None
    for stop, at in reach.items():
        if stop == origin:
            continue
        for facility_id, minutes, mode in lm_index.get((stop, (int(at) // 60) % 24), []):
            if facility_id in wanted and (best is None or at + minutes < best[0]):
                best = (at + minutes, stop, facility_id, minutes, mode)
    if best is None:
        return dict(facility_id=None, total_min=None, wait_min=None, boat_min=None,
                    transfer_min=None, lastmile_mode=None, lastmile_min=None, n_boats=0, path=None)

    arrival, stop, facility_id, minutes, mode = best
    legs = journey(came_by, origin, stop)
    transfers = sum(nxt[2] - prev[4] for prev, nxt in zip(legs, legs[1:]))
    path = ">".join([origin] + [f"{to}({route})" for route, _, _, to, _ in legs] + [mode, facility_id])
    return dict(facility_id=facility_id, total_min=round(arrival - t, 1),
                wait_min=legs[0][2] - (t + cfg.ACCESS_MIN),
                boat_min=sum(arr - dep for _, _, dep, _, arr in legs),
                transfer_min=transfers, lastmile_mode=mode, lastmile_min=minutes,
                n_boats=len(legs), path=path)
