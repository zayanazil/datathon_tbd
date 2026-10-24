"""Everything the dashboard needs that the shared modules don't provide (M4).

app/streamlit_app.py imports only from here and from the team's modules, so the dashboard
merges into main without editing a file another member owns. Journeys, island summaries and
scenarios are M3's (scenarios.run_scenario); map layers and the last mile are M1's (geo,
lastmile); observed boats and taxis are M2's (via M3 and M1).

The 11 pieces the dashboard used to take from the Saroof branch's own modules:
  1. kaafu.load (loaders + checks)  -> check_data, load_islands, load_origins, load_facilities,
                                       load_hdx, load_processed (below)
  2. geo.terminals                  -> geo.load_terminals (M1, already there)
  3. scenarios.connections_for      -> scenario_connections (below, from M3's functions)
  4. timetable.legs                 -> route_ids (below, from M3's connections.csv)
  5. timetable.next_day             -> config.NEXT_DAY (already there)
  6. config.DAYS                    -> dropped: M3's engine models one day, config.DAY (Wednesday)
  7. config.TARGETS                 -> TARGETS (below)
  8-11. indicators.at_departure, share_within, through_day, hdx_table -> below
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from kaafu import config as C
from kaafu import geo, indicators, scenarios

TARGETS = {"gm_hospital": "Nearest Greater Malé hospital", "any_hospital": "Any hospital"}
THRESHOLDS_MIN = [30, 60, 90, 120, 240]
HEADLINE_MIN = 120
BUS_ROAD_PATHS_JSON = C.PROCESSED / "bus_road_paths.json"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving/"
TEAM_RESULTS = "M3's published results (m3-network): access_results.csv, island_summary.csv, connections.csv"


# --- Loaders and checks (piece 1) ----------------------------------------------------

def _read(path) -> pd.DataFrame:
    return pd.read_csv(path, encoding=C.READ_ENCODING)


def load_islands() -> pd.DataFrame:
    return _read(C.ISLANDS_CSV)


def load_origins() -> pd.DataFrame:
    islands = load_islands()
    return islands[islands["role"] == "origin"].reset_index(drop=True)


def load_facilities() -> pd.DataFrame:
    return _read(C.FACILITIES_CSV)


def load_processed(name: str) -> pd.DataFrame | None:
    path = C.PROCESSED / name
    return _read(path) if path.exists() else None


def load_hdx() -> pd.DataFrame:
    """threshold_min, hdx_kaafu_pct, hdx_maldives_pct from the long HDX sheet."""
    df = _read(C.HDX_BENCHMARK_CSV)
    wide = df.pivot_table(index="threshold_min", columns="area", values="share_pct").reset_index()
    wide = wide.rename(columns={"Kaafu": "hdx_kaafu_pct", "Maldives": "hdx_maldives_pct"})
    wide = wide.reindex(columns=["threshold_min", "hdx_kaafu_pct", "hdx_maldives_pct"])
    return pd.DataFrame({"threshold_min": THRESHOLDS_MIN}).merge(wide, on="threshold_min", how="left")


def check_data() -> list[str]:
    """BUILD_PLAN section 9 data checks the dashboard relies on; raises ValueError on failure."""
    errors = []
    islands, facilities = load_islands(), load_facilities()
    keys = set(islands["island_key"])
    origins = islands[islands["role"] == "origin"]
    for label, rows, want in [("Kaafu", origins["atoll"] == "K", 17_749),
                              ("inbound", origins["atoll"] != "K", 13_665),
                              ("all", origins["atoll"].notna(), 31_414)]:
        if origins.loc[rows, "population_2022"].sum() != want:
            errors.append(f"{label} population is not {want:,}")
    if not set(facilities["island_key"]) <= keys:
        errors.append("facilities.csv has an island_key not in islands.csv")
    conns = load_processed("connections.csv")
    if conns is None:
        errors.append("connections.csv is missing (M3)")
    else:
        stops = keys | set(geo.load_terminals()["terminal_id"])
        if not (set(conns["from_stop"]) | set(conns["to_stop"])) <= stops:
            errors.append("connections.csv has a stop not in islands.csv or terminals.csv")
        if (conns["dep_min"] >= conns["arr_min"]).any():
            errors.append("connections.csv has dep_min >= arr_min")
    for name in ("access_results.csv", "island_summary.csv", "last_mile.csv"):
        if load_processed(name) is None:
            errors.append(f"{name} is missing")
    if errors:
        raise ValueError("Data checks failed: " + "; ".join(errors))
    return [f"{len(conns):,} boat connections ({C.DAY} + {C.NEXT_DAY})"]


# --- Scenarios (pieces 3 and 4) --------------------------------------------------------

DEFAULTS = {"observed": False, "ferry_factor": 1.0, "ferry_route": None, "extra_run": None,
            "bus_factor": 1.0, "taxi_availability": 0.0, "thulusdhoo_hospital": False}


def route_ids() -> list[str]:
    return sorted(load_processed("connections.csv")["route_id"].astype(str).unique())


def m3_params(p: dict) -> dict:
    """The dashboard's slider values as M3's run_scenario parameters."""
    p = {**DEFAULTS, **p}
    routes = route_ids() if p["ferry_route"] is None else [str(p["ferry_route"])]
    return {"ferry_factor": {r: p["ferry_factor"] for r in routes} if p["ferry_factor"] != 1 else {},
            "extra_runs": [tuple(p["extra_run"])] if p["extra_run"] else [],
            "thulusdhoo_hospital": p["thulusdhoo_hospital"], "observed": p["observed"],
            "bus_factor": p["bus_factor"], "taxi_availability": p["taxi_availability"]}


def scenario_connections(p: dict) -> pd.DataFrame:
    """The boat legs behind a scenario, built with M3's functions in run_scenario's order."""
    q = {**scenarios.DEFAULTS, **m3_params(p)}
    data = scenarios._inputs(C)
    conns = data["conns"]
    if q["observed"] and data["observed_pairs"] is not None:
        conns = scenarios.observed_durations(conns, data["observed_pairs"], data["stop_island"], C)
        if q["speedboats"]:
            conns = scenarios._finish(pd.concat([conns, scenarios.speedboat_departures(
                data["observed_pairs"], data["stop_island"], C)]))
    for route_id, factor in q["ferry_factor"].items():
        conns = scenarios.scale_route(conns, str(route_id), factor)
    for route_id, minute in q["extra_runs"]:
        conns = scenarios.extra_run(conns, str(route_id), int(minute))
    return conns


def run(p: dict):
    """(access_results, island_summary, connections, source) for the dashboard.

    Default settings show M3's published files as they are; anything else runs M3's
    run_scenario on the same inputs.
    """
    p = {**DEFAULTS, **p}
    if p == DEFAULTS:
        files = [load_processed(f) for f in ("access_results.csv", "island_summary.csv", "connections.csv")]
        if all(f is not None for f in files):
            access, summary, conns = files
            return access, summary, conns.assign(route_id=conns["route_id"].astype(str)), TEAM_RESULTS
    access, summary = scenarios.run_scenario(m3_params(p))
    return access, summary, scenario_connections(p), "Recomputed for these settings with M3's run_scenario"


# --- Indicators at a chosen departure (pieces 8-11) -------------------------------------

def at_departure(access: pd.DataFrame, dep_min: int, target: str) -> pd.Series:
    """Door-to-door minutes per origin at one departure step (NaN = unreachable)."""
    sel = access[(access["dep_min"] == dep_min) & (access["target"] == target)]
    return sel.set_index("origin_key")["total_min"].astype(float)


def _groups(origins: pd.DataFrame) -> dict[str, list[str]]:
    return {"kaafu": origins.loc[origins["atoll"] == "K", "island_key"].tolist(),
            "all23": origins["island_key"].tolist()}


def share_within(minutes: pd.Series, origins: pd.DataFrame, thresholds=None) -> pd.DataFrame:
    """Population share (%) within each threshold, for Kaafu and all 23 (minutes indexed by origin)."""
    w = origins.set_index("island_key")["population_2022"]
    rows = []
    for th in thresholds or THRESHOLDS_MIN:
        row = {"threshold_min": th}
        for g, keys in _groups(origins).items():
            row[f"{g}_pct"] = 100 * w[keys][(minutes.reindex(keys) <= th).to_numpy()].sum() / w[keys].sum()
        rows.append(row)
    return pd.DataFrame(rows)


def through_day(access: pd.DataFrame, origins: pd.DataFrame, target: str,
                threshold: int = HEADLINE_MIN) -> pd.DataFrame:
    """Share within `threshold` for every departure step: dep_min, kaafu_pct, all23_pct."""
    rows = []
    for dep, g in access[access["target"] == target].groupby("dep_min"):
        s = share_within(g.set_index("origin_key")["total_min"].astype(float), origins, [threshold]).iloc[0]
        rows.append({"dep_min": dep, "kaafu_pct": s["kaafu_pct"], "all23_pct": s["all23_pct"]})
    return pd.DataFrame(rows)


def hdx_table(ours: pd.DataFrame, hdx: pd.DataFrame) -> pd.DataFrame:
    return ours.merge(hdx[["threshold_min", "hdx_kaafu_pct", "hdx_maldives_pct"]], on="threshold_min", how="left")


# --- Bus routes on the roads ---------------------------------------------------------

def bus_routes_layer() -> pd.DataFrame:
    """M1's geo.bus_routes_layer, with each route's path along the roads where it has been
    snapped (bus_road_paths.json); M1's straight stop-to-stop lines otherwise."""
    paths = geo.bus_routes_layer()
    if paths.empty or not BUS_ROAD_PATHS_JSON.exists():
        return paths
    roads = json.loads(BUS_ROAD_PATHS_JSON.read_text(encoding="utf-8"))
    on_road = paths["route_number"].isin(roads.get("routes", {}))
    paths.loc[on_road, "path"] = paths.loc[on_road, "route_number"].map(roads["routes"])
    partly = paths["route_number"].isin(roads.get("straight_legs", {}))
    paths["tooltip"] = paths["tooltip"] + np.select(
        [~on_road, partly], [" (stops joined by straight lines)", " (some stops joined by straight lines)"], "")
    return paths


def _metres(a, b) -> float:
    (lon1, lat1), (lon2, lat2) = np.radians(a), np.radians(b)
    h = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return float(2 * 6_371_000 * np.arcsin(np.sqrt(h)))


def _osrm(points: list, **params):
    import requests

    r = requests.get(OSRM_URL + ";".join(f"{x:.6f},{y:.6f}" for x, y in points),
                     params={"geometries": "geojson", **params},
                     headers={"User-Agent": C.OVERPASS_USER_AGENT}, timeout=30)
    r.raise_for_status()
    return r.json()["routes"][0]


def write_bus_road_paths(pause_s: float = 1.0) -> dict[str, str]:
    """Snap M1's bus routes (bus_routes.csv) onto OpenStreetMap roads via the public OSRM server.

    Run once (needs internet): `python -c "from kaafu import dashboard; dashboard.write_bus_road_paths()"`.
    Only public bus-stop coordinates are sent. Each stop-to-stop leg follows the roads. OSM's one-way
    tags at Velana Domestic Terminal send some airport legs on an 11 km loop via Hulhumalé, so for any
    leg over 2 x straight + 500 m the shorter of the forward path and the reverse path (flipped) is drawn.
    """
    stops = _read(geo.BUS_ROUTES_CSV).sort_values(["route_number", "order"])
    out, notes, straight_legs = {}, {}, {}
    for route, g in stops.groupby("route_number"):
        pts = g[["lon", "lat"]].to_numpy().tolist()
        try:
            legs = _osrm(pts, overview="false", steps="true")["legs"]
        except Exception as e:  # network or OSRM failure: keep M1's straight lines for this route
            notes[route] = f"not snapped: {type(e).__name__}"
            continue
        path, bad = [], []
        for i, leg in enumerate(legs):
            straight = _metres(pts[i], pts[i + 1])
            piece = [c for step in leg["steps"] for c in step["geometry"]["coordinates"]]
            if leg["distance"] > 2 * straight + 500:
                try:
                    rev = _osrm([pts[i + 1], pts[i]], overview="full")
                    if rev["distance"] < leg["distance"]:
                        piece = [pts[i], *rev["geometry"]["coordinates"][::-1], pts[i + 1]]
                except Exception:
                    pass
            if not piece:
                piece = [pts[i], pts[i + 1]]
                bad.append(f"{g.stop.iloc[i]} → {g.stop.iloc[i + 1]} (no road path)")
            path.extend(piece if not path else piece[1:])
        out[route] = [[round(x, 6), round(y, 6)] for x, y in path]
        if bad:
            straight_legs[route] = bad
        notes[route] = f"{len(legs) - len(bad)}/{len(legs)} legs on roads"
        time.sleep(pause_s)
    BUS_ROAD_PATHS_JSON.write_text(json.dumps(
        {"source": "OSRM (router.project-osrm.org) on OpenStreetMap roads, © OpenStreetMap contributors (ODbL)",
         "notes": notes, "straight_legs": straight_legs, "routes": out}, ensure_ascii=False), encoding="utf-8")
    return notes
