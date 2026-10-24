"""Ferry sheet -> boat connections (BUILD_PLAN 6.1)."""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from . import config as C
from .load import hhmm_to_min, load_ferry, load_processed

TERMINAL_FOR_ISLAND = {"K.Hulhumalé": "T_HULHUMALE", "K.Villimalé": "T_VILLIMALE", "K.Hulhulé": "T_AIRPORT"}
CONN_COLUMNS = ["conn_id", "trip_id", "route_id", "from_stop", "to_stop", "dep_min", "arr_min",
                "mode", "operator", "day_type", "estimated", "source"]
ASSUMPTIONS: list[str] = []


def next_day(day: str) -> str:
    return C.DAYS[(C.DAYS.index(day) + 1) % 7]


def parse_days(text) -> set[str]:
    """'daily', 'Sat-Thu', 'Sat Mon Wed', 'Sat,Sun', 'except Fri' -> set of day labels."""
    s = str(text if pd.notna(text) else "daily").strip().lower()
    if s in ("", "daily", "all", "everyday", "every day"):
        return set(C.DAYS)
    low = [d.lower() for d in C.DAYS]
    if s.startswith("except"):
        return set(C.DAYS) - parse_days(s.replace("except", "", 1))
    out: set[str] = set()
    for tok in s.replace(",", " ").replace(";", " ").split():
        if "-" in tok:
            a, b = (t[:3] for t in tok.split("-", 1))
            i, j = low.index(a), low.index(b)
            out |= {C.DAYS[(i + k) % 7] for k in range(((j - i) % 7) + 1)}
        elif tok[:3] in low:
            out.add(C.DAYS[low.index(tok[:3])])
    return out


def _male_terminal(value) -> str | None:
    if pd.isna(value) or not str(value).strip():
        return None
    v = str(value).strip().upper()
    if v.startswith("T_"):
        return v
    v = v.casefold()
    if "west" in v or "maafannu" in v:
        return "T_MALE_WEST"
    if "villi" in v:
        return "T_VILLIMALE"
    if "hulhum" in v:
        return "T_HULHUMALE"
    if "airport" in v or "hulhul" in v:
        return "T_AIRPORT"
    return "T_MALE_NORTH"


def _stop(key: str, terminal) -> str:
    if key == "K.Malé":
        t = _male_terminal(terminal)
        if t is None:
            msg = f"Malé rows without a terminal use {C.DEFAULT_MALE_TERMINAL}"
            if msg not in ASSUMPTIONS:
                ASSUMPTIONS.append(msg)
            return C.DEFAULT_MALE_TERMINAL
        return t
    return TERMINAL_FOR_ISLAND.get(key, key)


def _infer_trips(df: pd.DataFrame) -> pd.Series:
    """Chain legs of one route where a leg leaves from where the previous one arrived."""
    trip = pd.Series(index=df.index, dtype=object)
    for route, g in df.sort_values("dep_min").groupby("route_id", sort=False):
        open_trips: list[tuple[str, str, int]] = []  # (trip_id, at_stop, arr_min)
        n = 0
        for i, r in g.iterrows():
            match = next((t for t in open_trips if t[1] == r["from_stop"] and 0 <= r["dep_min"] - t[2] <= 30), None)
            if match:
                open_trips.remove(match)
                tid = match[0]
            else:
                n += 1
                tid = f"{route}-{n:02d}"
            trip[i] = tid
            open_trips.append((tid, r["to_stop"], r["arr_min"]))
    return trip


def legs() -> pd.DataFrame:
    """Every ferry leg with stops, minutes and the set of days it runs."""
    f = load_ferry()
    if "trips_per_day" in f.columns:  # rtl_connections layout: spread departures evenly
        rows = []
        for _, r in f.iterrows():
            n, first, last = int(float(r["trips_per_day"])), hhmm_to_min(r["depart"]), hhmm_to_min(r["arrive"])
            dur = int(float(r["shortest_minutes"]))
            for k, dep in enumerate(np.linspace(first, last, max(n, 1)).round().astype(int)):
                rows.append({**r, "depart": f"{dep // 60:02d}:{dep % 60:02d}", "trip_id": f"{r['route_id']}-{k + 1:02d}",
                             "arrive": f"{(dep + dur) // 60 % 24:02d}:{(dep + dur) % 60:02d}", "estimated": "yes"})
        f = pd.DataFrame(rows)
    out = pd.DataFrame({
        "route_id": f["route_id"].astype(str),
        "from_stop": [_stop(k, t) for k, t in zip(f["from_key"], f.get("departure_terminal", pd.Series(index=f.index)))],
        "to_stop": [_stop(k, t) for k, t in zip(f["to_key"], f.get("arrival_terminal", pd.Series(index=f.index)))],
        "dep_min": f["depart"].map(hhmm_to_min),
        "arr_min": f["arrive"].map(hhmm_to_min),
        "mode": f.get("mode", pd.Series("ferry", index=f.index)).fillna("ferry"),
        "operator": f.get("operator", pd.Series("MTCC/RTL", index=f.index)).fillna(""),
        "estimated": f.get("estimated", pd.Series("no", index=f.index)).fillna("no"),
        "source": f.get("source", pd.Series("ferry_timetable.csv", index=f.index)).fillna("ferry_timetable.csv"),
        "days": f["days"].map(parse_days),
    })
    out["arr_min"] = out["arr_min"].where(out["arr_min"] > out["dep_min"], out["arr_min"] + 1440)
    if "trip_id" in f.columns and f["trip_id"].notna().all():
        out["trip_id"] = f["route_id"].astype(str) + ":" + f["trip_id"].astype(str)
    else:
        out["trip_id"] = _infer_trips(out)
    return out


def day_legs(day: str, all_legs: pd.DataFrame | None = None) -> pd.DataFrame:
    lg = legs() if all_legs is None else all_legs
    return lg[lg["days"].map(lambda d: day in d)].drop(columns="days").reset_index(drop=True)


def trip_patterns(dl: pd.DataFrame) -> pd.DataFrame:
    """One row per trip: route, stop sequence, first departure, and leg offsets."""
    rows = []
    for tid, g in dl.sort_values("dep_min").groupby("trip_id", sort=False):
        t0 = g["dep_min"].iloc[0]
        rows.append({"trip_id": tid, "route_id": g["route_id"].iloc[0], "first_dep": t0,
                     "pattern": tuple(g["from_stop"]) + (g["to_stop"].iloc[-1],),
                     "offsets": list(zip(g["dep_min"] - t0, g["arr_min"] - t0))})
    return pd.DataFrame(rows)


def apply_observed(conns: pd.DataFrame, pairs: pd.DataFrame | None) -> pd.DataFrame:
    """M3's observed switch (m3-network scenarios.observed_durations / speedboat_departures).

    1. A leg takes its island pair's observed `slow` median where n_trips >= OBSERVED_MIN_TRIPS and
       the median is at most OBSERVED_MAX_SLOWDOWN x the scheduled time. Departures stay as
       scheduled, except a boat can't leave a stop before it arrives there.
    2. Island -> Greater Malé pairs whose `fast` trips average >= SPEEDBOAT_MIN_TRIPS_PER_DAY get a
       departure every (last_hour - first_hour) x 60 / trips_per_day minutes, taking the fast
       median, today and tomorrow. Observed boat movements, not a published schedule.
    """
    if pairs is None or pairs.empty:
        return conns
    from .geo import stop_island

    isl = stop_island()
    slow = pairs[(pairs["speed_class"] == "slow") & (pairs["n_trips"] >= C.OBSERVED_MIN_TRIPS)]
    median = slow.set_index(["from_key", "to_key"])["median_min"].to_dict()
    c = conns.sort_values(["trip_id", "dep_min"]).copy()
    arrived: dict[str, int] = {}
    for i, r in zip(c.index, c.itertuples()):
        dep = max(r.dep_min, arrived.get(r.trip_id, r.dep_min))
        scheduled = r.arr_min - r.dep_min
        observed = median.get((isl[r.from_stop], isl[r.to_stop]))
        duration = round(observed) if observed is not None and observed <= C.OBSERVED_MAX_SLOWDOWN * scheduled \
            else scheduled
        c.loc[i, ["dep_min", "arr_min"]] = [dep, dep + duration]
        arrived[r.trip_id] = dep + duration

    busy = pairs[(pairs["speed_class"] == "fast") & (pairs["trips_per_day"] >= C.SPEEDBOAT_MIN_TRIPS_PER_DAY)
                 & pairs["to_key"].isin(C.GREATER_MALE) & ~pairs["from_key"].isin(C.GREATER_MALE)]
    extra = []
    for p in busy.itertuples():
        every = round((p.last_hour - p.first_hour) * 60 / p.trips_per_day)
        for k, dep in enumerate(range(p.first_hour * 60, p.last_hour * 60 + 1, every)):
            for day_off in (0, 1440):
                extra.append({"trip_id": f"OBS:{p.from_key}:{k:02d}{'+1' if day_off else ''}",
                              "route_id": "observed speedboat", "from_stop": p.from_key,
                              "to_stop": _stop(p.to_key, None), "dep_min": dep + day_off,
                              "arr_min": dep + day_off + round(p.median_min), "mode": "speedboat_observed",
                              "operator": "observed (FollowMe)", "day_type": c["day_type"].iloc[0],
                              "estimated": "yes", "source": "observed boat movements, not a published schedule"})
    if extra:
        c = pd.concat([c, pd.DataFrame(extra)], ignore_index=True)
    return c


def build_connections(day: str = C.DAY, edit: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
                      observed: bool = False, all_legs: pd.DataFrame | None = None) -> pd.DataFrame:
    """Connections for `day` plus the next day shifted by +1440, sorted by departure."""
    lg = legs() if all_legs is None else all_legs
    today, tomorrow = day_legs(day, lg), day_legs(next_day(day), lg)
    if edit is not None:
        today, tomorrow = edit(today), edit(tomorrow)
    tomorrow = tomorrow.assign(dep_min=tomorrow["dep_min"] + 1440, arr_min=tomorrow["arr_min"] + 1440,
                               trip_id=tomorrow["trip_id"] + "+1")
    conns = pd.concat([today, tomorrow], ignore_index=True)
    conns["day_type"] = day
    if observed:
        conns = apply_observed(conns, load_processed("observed_pairs.csv"))
    conns = conns.sort_values(["dep_min", "arr_min"]).reset_index(drop=True)
    conns["conn_id"] = np.arange(len(conns))
    return conns[CONN_COLUMNS]
