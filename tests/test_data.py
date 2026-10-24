"""Data checks (BUILD_PLAN section 9). load.check_all() runs the same checks at startup."""
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from kaafu import config as C
from kaafu.geo import haversine_m, terminals
from kaafu.load import (check_all, hhmm_to_min, load_facilities, load_ferry, load_islands, load_names,
                        load_processed)
from kaafu.timetable import legs

ROOT = Path(__file__).resolve().parents[1]


def test_check_all_passes():
    check_all()


def test_every_name_resolves():
    keys, names = set(load_islands()["island_key"]), set(load_names()["island_key"])
    assert set(load_facilities()["island_key"]) <= keys
    assert names <= keys
    f = load_ferry()
    assert set(f["from_key"]) | set(f["to_key"]) <= keys


def test_no_variant_points_to_two_keys():
    n = load_names().drop_duplicates(["variant", "island_key"])
    assert not n["variant"].duplicated().any()


def test_population_totals():
    o = load_islands().query("role == 'origin'")
    assert o.loc[o["atoll"] == "K", "population_2022"].sum() == 17749
    assert o.loc[o["atoll"] != "K", "population_2022"].sum() == 13665
    assert o["population_2022"].sum() == 31414
    assert len(o) == 23


def test_ferry_dep_before_arr_and_not_too_fast():
    lg = legs()
    assert (lg["dep_min"] < lg["arr_min"]).all()
    pts = load_islands().set_index("island_key")[["harbour_lat", "harbour_lon"]]
    pts = pd.concat([pts, terminals().set_index("terminal_id")[["lat", "lon"]].set_axis(pts.columns, axis=1)])
    km = haversine_m(pts.loc[lg["from_stop"]].to_numpy(), pts.loc[lg["to_stop"]].to_numpy()) / 1000
    assert (km / ((lg["arr_min"] - lg["dep_min"]) / 60) <= C.MAX_BOAT_KMH).all()


def test_every_greater_male_stop_has_a_terminal():
    lg = legs()
    gm = set(terminals()["terminal_id"])
    for col in ("from_stop", "to_stop"):
        assert not lg[col].isin(C.GREATER_MALE).any(), f"{col} has a Greater Malé island, not a terminal"
    assert (set(lg["from_stop"]) | set(lg["to_stop"])) & gm


def test_connection_stops_exist():
    conns = load_processed("connections.csv")
    if conns is None:
        pytest.skip("connections.csv not built yet (python -m kaafu.pipeline)")
    stops = set(load_islands()["island_key"]) | set(terminals()["terminal_id"])
    assert set(conns["from_stop"]) | set(conns["to_stop"]) <= stops
    assert (conns["dep_min"] < conns["arr_min"]).all()


def test_last_mile_rules():
    lm = load_processed("last_mile.csv")
    if lm is None:
        pytest.skip("last_mile.csv not built yet")
    walk = lm[lm["mode"] == "walk"]
    for t in terminals()["terminal_id"]:
        for h in C.GM_HOSPITALS:
            assert len(walk[(walk["stop_id"] == t) & (walk["facility_id"] == h)]) == 24
    vil = lm[(lm["stop_id"] == "T_VILLIMALE") & lm["facility_id"].isin(["H01", "H02", "H03", "H04", "H05"])]
    assert not vil[vil["mode"].isin(["walk", "taxi"])]["available"].astype(bool).any()
    hh = walk[(walk["stop_id"] == "T_HULHUMALE") & (walk["facility_id"] == "H04")]["minutes"]
    assert (hh < 15).all()
    igmh = walk[(walk["stop_id"] == "T_MALE_NORTH") & (walk["facility_id"] == "H01")]["minutes"]
    assert igmh.between(18, 27).all()


def test_no_imei_in_outputs():
    for path in C.PROCESSED.glob("*"):
        if path.is_file():
            head = path.read_text(encoding="utf-8", errors="ignore")[:5000].lower()
            assert "imei" not in head, path.name


def test_hhmm():
    assert hhmm_to_min("07:25") == 445
