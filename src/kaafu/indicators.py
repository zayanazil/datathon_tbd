"""Door-to-door times for every island x departure x target, and the indicators built on them (6.6)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .load import load_facilities
from .routing import Network, journey

ACCESS_COLUMNS = ["scenario", "day_type", "origin_key", "dep_min", "target", "facility_id", "total_min",
                  "wait_min", "boat_min", "transfer_min", "lastmile_mode", "lastmile_min", "n_boats", "path"]


def targets(thulusdhoo_hospital: bool = False) -> dict[str, set[str]]:
    gm = set(C.gm_hospitals())
    anyh = gm | set(C.ATOLL_HOSPITALS) | ({C.THULUSDHOO_HOSPITAL_ID} if thulusdhoo_hospital else set())
    return {"gm_hospital": gm, "any_hospital": anyh}


def access_results(net: Network, origins: pd.DataFrame, scenario: str, day: str,
                   tg: dict[str, set[str]], departures=None) -> pd.DataFrame:
    departures = range(0, 1440, C.STEP_MIN) if departures is None else departures
    rows = []
    for o in origins["island_key"]:
        for t in departures:
            for name, r in journey(net, o, t, tg).items():
                rows.append({"scenario": scenario, "day_type": day, "origin_key": o, "dep_min": t,
                             "target": name, **r})
    return pd.DataFrame(rows, columns=ACCESS_COLUMNS)


def _weights(origins: pd.DataFrame) -> pd.Series:
    return origins.set_index("island_key")["population_2022"]


def _groups(origins: pd.DataFrame) -> dict[str, list[str]]:
    return {"kaafu": origins.loc[origins["atoll"] == "K", "island_key"].tolist(),
            "all23": origins["island_key"].tolist()}


def share_within(minutes: pd.Series, origins: pd.DataFrame, thresholds=None) -> pd.DataFrame:
    """minutes: index origin_key. Population share (%) within each threshold, Kaafu and all 23."""
    thresholds = thresholds or C.THRESHOLDS_MIN
    w = _weights(origins)
    rows = []
    for th in thresholds:
        row = {"threshold_min": th}
        for g, keys in _groups(origins).items():
            m = minutes.reindex(keys)
            row[f"{g}_pct"] = 100 * w[keys][(m <= th).to_numpy()].sum() / w[keys].sum()
        rows.append(row)
    return pd.DataFrame(rows)


def at_departure(access: pd.DataFrame, dep_min: int, target: str) -> pd.Series:
    sel = access[(access["dep_min"] == dep_min) & (access["target"] == target)]
    return sel.set_index("origin_key")["total_min"].astype(float)


def daytime_median(access: pd.DataFrame, target: str) -> pd.Series:
    day = access[(access["target"] == target) & access["dep_min"].between(C.DAY_START_MIN, C.DAY_END_MIN)]
    # Unreachable counts as infinitely long, so it pulls the median up rather than vanishing.
    return day.assign(m=day["total_min"].astype(float).fillna(np.inf)).groupby("origin_key")["m"].median()


def through_day(access: pd.DataFrame, origins: pd.DataFrame, target: str,
                threshold: int = C.HEADLINE_THRESHOLD_MIN) -> pd.DataFrame:
    rows = []
    for dep, g in access[access["target"] == target].groupby("dep_min"):
        s = share_within(g.set_index("origin_key")["total_min"].astype(float), origins, [threshold]).iloc[0]
        rows.append({"dep_min": dep, "kaafu_pct": s["kaafu_pct"], "all23_pct": s["all23_pct"]})
    return pd.DataFrame(rows)


def last_practical_departure(access: pd.DataFrame, target: str = "gm_hospital") -> pd.Series:
    """Latest departure step that still reaches the hospital before midnight; None if never."""
    a = access[access["target"] == target]
    ok = a[(a["dep_min"] + a["total_min"].astype(float)) <= 1440]
    last = ok.groupby("origin_key")["dep_min"].max()
    return last.reindex(a["origin_key"].unique())


def fmt_min(m) -> str:
    if m is None or pd.isna(m):
        return "none"
    m = int(m)
    return f"{m // 60 % 24:02d}:{m % 60:02d}" + (" (+1 day)" if m >= 1440 else "")


def boats_per_day(conns: pd.DataFrame, origins: pd.DataFrame) -> pd.Series:
    day = conns[conns["dep_min"] < 1440]
    return day.groupby("from_stop")["trip_id"].nunique().reindex(origins["island_key"]).fillna(0).astype(int)


def island_summary(access: pd.DataFrame, origins: pd.DataFrame, conns: pd.DataFrame) -> pd.DataFrame:
    """island_summary.csv with M3's definitions (m3-network indicators.island_summary).

    Daytime = departures DAY_START_MIN-DAY_END_MIN. Unreachable counts as infinite, so a median,
    best or worst that is unreachable is left blank. last_practical_departure: the latest step
    that reaches the hospital before midnight. observed_gap_min: see observed_gap().
    """
    gm = access[access["target"] == "gm_hospital"]
    total = gm["total_min"].astype(float).fillna(np.inf)
    day = total[gm["dep_min"].between(C.DAY_START_MIN, C.DAY_END_MIN)].groupby(gm["origin_key"])
    same_day = gm[(gm["dep_min"] + total) < 1440].groupby("origin_key")["dep_min"].max()
    s = pd.DataFrame({"origin_key": origins["island_key"],
                      "population": origins["population_2022"].to_numpy()}).set_index("origin_key")
    s["day_median_min"] = day.median().replace(np.inf, np.nan).round(1)
    s["best_min"] = day.min().replace(np.inf, np.nan).round(1)
    s["worst_day_min"] = day.max().replace(np.inf, np.nan).round(1)
    s["last_practical_departure"] = same_day.reindex(s.index).map(
        lambda m: "none" if pd.isna(m) else f"{int(m) // 60:02d}:{int(m) % 60:02d}")
    s["boats_per_day"] = boats_per_day(conns, origins)
    s["observed_gap_min"] = observed_gap(conns)
    return s.reset_index()


def observed_gap(conns: pd.DataFrame) -> pd.Series:
    """Scheduled minus observed boat minutes from each island to Greater Malé (M3's definition).

    Scheduled: the quickest timetabled ride from the island to a Greater Malé terminal on one trip.
    Observed: M2's median of tracked trips from the island to Malé, Hulhumalé or Villimalé, with
    at least OBSERVED_MIN_TRIPS. Positive = the boats people take are faster than the timetable.
    """
    from .load import load_processed

    trips = load_processed("observed_trips.csv")
    if trips is None:
        return pd.Series(dtype=float)
    scheduled: dict[str, float] = {}
    for _, trip in conns[~conns["mode"].str.contains("observed")].sort_values("dep_min").groupby("trip_id"):
        legs = list(trip.itertuples())
        for i, leg in enumerate(legs):
            if leg.from_stop.startswith("T_"):
                continue
            at_gm = next((later.arr_min for later in legs[i:] if later.to_stop.startswith("T_")), None)
            if at_gm is not None:
                scheduled[leg.from_stop] = min(scheduled.get(leg.from_stop, at_gm - leg.dep_min), at_gm - leg.dep_min)
    from .geo import terminals

    terminal_islands = set(terminals()["island_key"])  # Malé, Hulhumalé, Villimalé: not the airport
    to_gm = trips[trips["to_key"].isin(terminal_islands)].groupby("from_key")["duration_min"]
    observed = to_gm.median()[to_gm.size() >= C.OBSERVED_MIN_TRIPS]
    return (pd.Series(scheduled, dtype=float) - observed).dropna().round(1)


def hdx_table(ours: pd.DataFrame, hdx: pd.DataFrame) -> pd.DataFrame:
    t = ours.merge(hdx[["threshold_min", "hdx_kaafu_pct", "hdx_maldives_pct"]], on="threshold_min", how="left")
    return t
