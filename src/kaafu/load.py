"""Load and check every sheet. All sheets are UTF-8 with a BOM, so read with utf-8-sig."""
from __future__ import annotations

import warnings

import pandas as pd

from . import config as C


class DataCheckError(RuntimeError):
    pass


def _read(path, **kw) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig", **kw)


def load_islands() -> pd.DataFrame:
    return _read(C.SHEETS / "islands.csv")


def load_origins() -> pd.DataFrame:
    df = load_islands()
    return df[df["role"] == "origin"].reset_index(drop=True)


def load_facilities() -> pd.DataFrame:
    return _read(C.SHEETS / "facilities.csv", dtype={"access_point_code": "string"})


def load_names() -> pd.DataFrame:
    return _read(C.SHEETS / "island_names.csv")


def to_island_key(names: pd.Series, what: str = "name") -> pd.Series:
    """Map any spelling to island_key via island_names.csv; raise listing every unknown name."""
    table = load_names()
    exact = dict(zip(table["variant"], table["island_key"]))
    loose = {_loose(v): k for v, k in exact.items()}
    keys = names.map(lambda n: exact.get(n, loose.get(_loose(n))) if pd.notna(n) else None)
    unknown = sorted(set(names[keys.isna() & names.notna()]))
    if unknown:
        raise DataCheckError(f"Unknown {what} (add to island_names.csv): {unknown}")
    return keys


def _loose(name) -> str:
    return "".join(str(name).casefold().replace("'", "").split())


# --- Sheets that may still be missing -----------------------------------------

_WARNED: set[str] = set()


def sheet_path(name: str):
    """Real sheet if present, else its placeholder. Returns (path, is_placeholder)."""
    real = C.SHEETS / name
    if real.exists():
        return real, False
    ph = C.PLACEHOLDER / name
    if ph.exists():
        if name not in _WARNED:
            _WARNED.add(name)
            warnings.warn(f"{name} missing from data/sheets/: using PLACEHOLDER data", stacklevel=3)
        return ph, True
    return None, False


def using_placeholder(name: str) -> bool:
    return sheet_path(name)[1]


FERRY_ALIASES = {
    "route": "route_id", "route_no": "route_id", "route_number": "route_id",
    "from_island": "from", "origin": "from", "from_stop": "from",
    "to_island": "to", "destination": "to", "to_stop": "to",
    "departure": "depart", "dep": "depart", "dep_time": "depart", "departure_time": "depart",
    "arrival": "arrive", "arr": "arrive", "arr_time": "arrive", "arrival_time": "arrive",
    "days_of_operation": "days", "operating_days": "days",
}


def load_ferry() -> pd.DataFrame:
    """ferry_timetable.csv with standard column names: route_id, from, to, depart, arrive, days, ..."""
    path, _ = sheet_path("ferry_timetable.csv")
    if path is None:
        raise DataCheckError("No ferry_timetable.csv in data/sheets/ and no placeholder: "
                             "run `python tests/make_placeholders.py`")
    df = _read(path, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.rename(columns={c: FERRY_ALIASES[c] for c in df.columns if c in FERRY_ALIASES})
    missing = {"route_id", "from", "to", "depart", "arrive"} - set(df.columns)
    if missing:
        raise DataCheckError(f"ferry_timetable.csv lacks columns {sorted(missing)}")
    if "days" not in df:
        df["days"] = "daily"
    df["from_key"] = to_island_key(df["from"], "ferry 'from'")
    df["to_key"] = to_island_key(df["to"], "ferry 'to'")
    return df


def load_bus_hours() -> pd.DataFrame | None:
    path, _ = sheet_path("bus_service_hours.csv")
    return _read(path) if path else None


def load_bus_headways() -> pd.DataFrame | None:
    path, _ = sheet_path("bus_headways.csv")
    return _read(path) if path else None


def load_hdx() -> pd.DataFrame:
    """threshold_min, hdx_kaafu_pct, hdx_maldives_pct from the long HDX sheet (one row per area x threshold)."""
    df = _read(C.SHEETS / "hdx_benchmark.csv")
    if "area" not in df.columns:  # already wide
        return df
    wide = df.pivot_table(index="threshold_min", columns="area", values="share_pct").reset_index()
    wide = wide.rename(columns={"Kaafu": "hdx_kaafu_pct", "Maldives": "hdx_maldives_pct"})
    return wide[["threshold_min", "hdx_kaafu_pct", "hdx_maldives_pct"]]


def load_processed(name: str) -> pd.DataFrame | None:
    path = C.PROCESSED / name
    return _read(path) if path.exists() else None


def load_raw_csv(name: str) -> pd.DataFrame | None:
    for path in (C.RAW / name, *C.RAW.rglob(name)):
        if path.exists():
            return _read(path)
    return None


# --- Checks (BUILD_PLAN section 9) ------------------------------------------

def hhmm_to_min(s) -> int:
    h, m = str(s).strip().split(":")[:2]
    return int(h) * 60 + int(m)


def check_all() -> list[str]:
    """Run every data check; raise DataCheckError listing all failures. Returns notes."""
    from .geo import haversine_m, terminals

    errors, notes = [], []
    islands, fac = load_islands(), load_facilities()
    keys = set(islands["island_key"])
    name_keys = set(load_names()["island_key"])

    bad = set(fac["island_key"]) - keys - name_keys
    if bad:
        errors.append(f"facilities.csv island_key not in islands.csv: {sorted(bad)}")

    origins = islands[islands["role"] == "origin"]
    pops = {"Kaafu": origins.loc[origins["atoll"] == "K", "population_2022"].sum(),
            "inbound": origins.loc[origins["atoll"] != "K", "population_2022"].sum(),
            "all": origins["population_2022"].sum()}
    for label, want in {"Kaafu": 17749, "inbound": 13665, "all": 31414}.items():
        if pops[label] != want:
            errors.append(f"{label} origin population {pops[label]} != {want}")

    try:
        ferry = load_ferry()
    except DataCheckError as e:
        errors.append(str(e))
        ferry = None
    if ferry is not None:
        if using_placeholder("ferry_timetable.csv"):
            notes.append("ferry_timetable.csv is a PLACEHOLDER")
        dep = ferry["depart"].map(hhmm_to_min)
        arr = ferry["arrive"].map(hhmm_to_min)
        arr = arr.where(arr > dep, arr + 1440)  # legs that cross midnight
        if ((arr - dep) <= 0).any() or ((arr - dep) > 12 * 60).any():
            errors.append("ferry rows with dep >= arr (or a leg over 12 h)")
        pts = islands.set_index("island_key")[["harbour_lat", "harbour_lon"]]
        d = haversine_m(pts.loc[ferry["from_key"]].to_numpy(), pts.loc[ferry["to_key"]].to_numpy())
        kmh = d / 1000 / ((arr - dep).to_numpy() / 60)
        if (kmh > C.MAX_BOAT_KMH).any():
            errors.append(f"{int((kmh > C.MAX_BOAT_KMH).sum())} ferry legs faster than {C.MAX_BOAT_KMH} km/h")
        notes.append(f"fastest ferry leg {kmh.max():.1f} km/h straight-line")

    conns = load_processed("connections.csv")
    if conns is not None:
        stops = keys | set(terminals()["terminal_id"])
        bad = (set(conns["from_stop"]) | set(conns["to_stop"])) - stops
        if bad:
            errors.append(f"connections.csv stops not in islands/terminals: {sorted(bad)}")
        if (conns["dep_min"] >= conns["arr_min"]).any():
            errors.append("connections.csv has dep_min >= arr_min")

    if errors:
        raise DataCheckError("Data checks failed:\n  - " + "\n  - ".join(errors))
    return notes
