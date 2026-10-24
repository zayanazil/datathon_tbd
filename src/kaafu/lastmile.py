"""Terminal to hospital door by walk, bus or taxi, for every hour (BUILD_PLAN 6.3)."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from . import config as C
from .avas import TERMINAL_ZONE
from .geo import haversine_m, terminals
from .load import hhmm_to_min, load_bus_hours, load_facilities, load_raw_csv

COLUMNS = ["stop_id", "facility_id", "hour", "mode", "minutes", "available", "detail",
           "expired_share", "bus_wait_min"]


def _road_linked(a: str, b: str) -> bool:
    return a == b or (a in C.ROAD_LINKED and b in C.ROAD_LINKED)


def _col(df, *names):
    return next(c for c in df.columns if c.lower() in names)


def _bus_network():
    """Per route: ordered stops with coordinates, ride minutes from the first stop, headway, hours."""
    stops, deps, routes = (load_raw_csv(n) for n in ("rtl_bus_stops.csv", "rtl_bus_departures.csv",
                                                   "rtl_bus_routes.csv"))
    hours = load_bus_hours()
    if any(x is None for x in (stops, deps, routes, hours)):
        return None
    try:
        s_code, s_lat, s_lon = _col(stops, "stop_code", "code", "stop_id"), _col(stops, "lat", "latitude", "stop_lat"), \
            _col(stops, "lon", "lng", "longitude", "stop_lon")
        coords = stops.assign(code=stops[s_code].astype(str)).drop_duplicates("code").set_index("code")[[s_lat, s_lon]]
        d_route, d_trip, d_code, d_time = (_col(deps, "route_id", "route"), _col(deps, "trip_id", "trip"),
                                           _col(deps, "stop_code", "code", "stop_id"),
                                           _col(deps, "time", "departure", "departure_time"))
        deps = deps.assign(code=deps[d_code].astype(str), m=deps[d_time].map(hhmm_to_min))
        tpd = routes.set_index(_col(routes, "route_id", "route"))[_col(routes, "trips_per_day")]
        h = hours.set_index(_col(hours, "route_id", "route"))
        first = h[_col(hours, "first_departure", "first", "first_dep")].map(hhmm_to_min)
        last = h[_col(hours, "last_departure", "last", "last_dep")].map(hhmm_to_min)
    except (StopIteration, KeyError, ValueError) as e:
        warnings.warn(f"bus sheets present but not in the expected layout ({e}); bus rows unavailable")
        return None
    net = {}
    for route, g in deps.groupby(d_route):
        route = str(route)
        if route not in C.BUS_ROUTES or route not in first.index or route not in tpd.index:
            continue
        g = g.assign(rel=g["m"] - g.groupby(d_trip)["m"].transform("min"))
        seq = g.groupby("code")["rel"].median().sort_values()
        seq = seq[seq.index.isin(coords.index)]
        if len(seq) < 2:
            continue
        headway = (last[route] - first[route]) / max(float(tpd[route]), 1)
        net[route] = {"codes": list(seq.index), "rel": seq.to_numpy(), "xy": coords.loc[seq.index].to_numpy(float),
                      "headway": headway, "first": first[route], "last": last[route]}
    return net


def _bus_option(net, a_xy, b_xy, hour, island_a, island_b):
    """Fastest timed route from point a to point b at this hour: (minutes, wait, detail) or None."""
    if not net or not _road_linked(island_a, island_b):
        return None
    best = None
    for route, r in net.items():
        if not (r["first"] <= hour * 60 + 59 and hour * 60 <= r["last"]):
            continue
        da, db = haversine_m(r["xy"], [a_xy]), haversine_m(r["xy"], [b_xy])
        i, j = int(np.argmin(da)), int(np.argmin(db))
        if j <= i or da[i] > 1000 or db[j] > 1000:
            continue
        wait = r["headway"] / 2
        minutes = da[i] / C.WALK_M_PER_MIN + wait + (r["rel"][j] - r["rel"][i]) + db[j] / C.WALK_M_PER_MIN
        if best is None or minutes < best[0]:
            best = (minutes, wait, f"{route} {r['codes'][i]}→{r['codes'][j]}")
    return best


def build(avas_hourly: pd.DataFrame | None = None, avas_rides: pd.DataFrame | None = None) -> pd.DataFrame:
    """last_mile.csv for the base scenario."""
    fac = load_facilities().set_index("facility_id")
    term = terminals()
    bus = _bus_network()
    av = avas_hourly.set_index(["zone", "hour"]) if avas_hourly is not None else None
    rows = []
    for _, t in term.iterrows():
        for fid in C.GM_HOSPITALS:
            h = fac.loc[fid]
            a_xy, b_xy = (t["lat"], t["lon"]), (h["lat"], h["lon"])
            dist = haversine_m([a_xy], [b_xy])[0]
            linked = _road_linked(t["island_key"], h["island_key"])
            od = {}
            if avas_rides is not None and linked:
                from .avas import od_median_minutes
                od = od_median_minutes(avas_rides, a_xy, b_xy).to_dict()
            for hour in range(24):
                same = t["island_key"] == h["island_key"]
                rows.append([t["terminal_id"], fid, hour, "walk", C.TERMINAL_EXIT_MIN + dist / C.WALK_M_PER_MIN,
                             same, f"{dist:.0f} m straight line" if same else "different island", 0.0, 0.0])

                opt = _bus_option(bus, a_xy, b_xy, hour, t["island_key"], h["island_key"])
                rows.append([t["terminal_id"], fid, hour, "bus",
                             C.TERMINAL_EXIT_MIN + opt[0] if opt else np.nan, opt is not None,
                             opt[2] if opt else ("no bus data" if bus is None else "no route / not running"),
                             0.0, opt[1] if opt else 0.0])

                zone = TERMINAL_ZONE.get(t["island_key"])
                if not (linked and zone):
                    rows.append([t["terminal_id"], fid, hour, "taxi", np.nan, False, "no road link", 0.0, 0.0])
                    continue
                if av is not None:
                    rec = av.loc[(zone, hour)] if (zone, hour) in av.index else av.loc[("all", hour)]
                    share, speed, src = float(rec["expired_share"]), float(rec["median_speed_kmh"]), "Avas"
                else:
                    share, speed, src = 0.07, C.TAXI_PLACEHOLDER_KMH, "PLACEHOLDER speed"
                if hour in od:
                    drive, how = od[hour], "Avas OD median"
                else:
                    drive, how = dist * C.TAXI_DETOUR / 1000 / speed * 60, f"{src} {speed:.0f} km/h ×{C.TAXI_DETOUR}"
                minutes = C.TERMINAL_EXIT_MIN + C.TAXI_BASE_WAIT_MIN + share * C.TAXI_RETRY_MIN + drive
                rows.append([t["terminal_id"], fid, hour, "taxi", minutes, True, how, share, 0.0])

    # Islands with their own atoll hospital: step off the boat and walk.
    for fid in C.ATOLL_HOSPITALS:
        rows.extend(atoll_rows(fac.loc[fid, "island_key"], fid, fac.loc[fid, "walk_minutes"]))
    return pd.DataFrame(rows, columns=COLUMNS)


def atoll_rows(island_key: str, facility_id: str, walk_minutes: float) -> list[list]:
    return [[island_key, facility_id, hour, "walk", C.TERMINAL_EXIT_MIN + float(walk_minutes), True,
             "harbour to atoll hospital", 0.0, 0.0] for hour in range(24)]
