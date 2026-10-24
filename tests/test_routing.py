"""Routing tests on a three-island toy timetable (BUILD_PLAN section 9)."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kaafu.routing import door_to_door, earliest_arrival  # noqa: E402

CFG = SimpleNamespace(ACCESS_MIN=5, BOAT_TRANSFER_MIN=10, TERMINAL_EXIT_MIN=5, WALK_M_PER_MIN=80)


def toy(legs):
    """legs: (trip_id, from_stop, to_stop, dep_min, arr_min)."""
    conns = pd.DataFrame(legs, columns=["trip_id", "from_stop", "to_stop", "dep_min", "arr_min"])
    conns["route_id"] = conns["trip_id"].str[:2]
    return conns.sort_values(["dep_min", "arr_min"], kind="stable").reset_index(drop=True)


def arrival(conns, origin, t, stop):
    reach, _ = earliest_arrival(conns, origin, t, CFG)
    return reach.get(stop)


def test_direct_boat():
    conns = toy([("T1", "A", "B", 480, 540)])
    assert arrival(conns, "A", 400, "B") == 540


def test_access_time_before_first_boat():
    conns = toy([("T1", "A", "B", 480, 540)])
    assert arrival(conns, "A", 476, "B") is None  # 476 + ACCESS_MIN 5 > 480


def test_after_last_boat_takes_next_morning():
    conns = toy([("T1", "A", "B", 480, 540), ("T1_d2", "A", "B", 480 + 1440, 540 + 1440)])
    assert arrival(conns, "A", 600, "B") == 540 + 1440


def test_transfer_needs_boat_transfer_min():
    # T2 leaves B 5 minutes after T1 arrives: too tight. T3 leaves exactly 10 after.
    legs = [("T1", "A", "B", 480, 540), ("T2", "B", "C", 545, 580), ("T3", "B", "C", 550, 590)]
    assert arrival(toy(legs), "A", 400, "C") == 590
    assert arrival(toy(legs[:2]), "A", 400, "C") is None


def test_staying_on_board_needs_no_transfer():
    # T1 calls at B and goes on to C 5 minutes later: no transfer time applies.
    legs = [("T1", "A", "B", 480, 540), ("T1", "B", "C", 545, 620), ("T2", "B", "C", 545, 580)]
    assert arrival(toy(legs), "A", 400, "C") == 620


def test_leaving_later_never_arrives_earlier():
    legs = []
    for day in (0, 1440):
        legs += [(f"T1{day}", "A", "B", 420 + day, 470 + day), (f"T1{day}", "B", "C", 475 + day, 530 + day),
                 (f"T2{day}", "A", "C", 700 + day, 800 + day), (f"T3{day}", "B", "C", 900 + day, 940 + day),
                 (f"T4{day}", "A", "B", 860 + day, 885 + day)]
    conns = toy(legs)
    previous = 0
    for t in range(0, 1440, 5):
        at = arrival(conns, "A", t, "C")
        assert at is not None and at >= previous
        previous = at


def test_breakdown_adds_up():
    conns = toy([("T1", "A", "B", 480, 540), ("T3", "B", "C", 550, 590)])
    hospitals = pd.DataFrame({"facility_id": ["H1"], "island_key": ["C"]})
    lm_index = {("C", 9): [("H1", 12.0, "walk")]}
    r = door_to_door(conns, "A", 400, hospitals, lm_index, CFG)
    assert r["total_min"] == 590 + 12 - 400
    assert r["wait_min"] == 480 - 405 and r["boat_min"] == 100 and r["transfer_min"] == 10
    assert r["total_min"] == CFG.ACCESS_MIN + r["wait_min"] + r["boat_min"] + r["transfer_min"] + r["lastmile_min"]
    assert r["n_boats"] == 2 and r["path"] == "A>B(T1)>C(T3)>walk>H1"


def test_own_hospital_scores_access_min():
    conns = toy([("T1", "A", "B", 480, 540)])
    hospitals = pd.DataFrame({"facility_id": ["H1"], "island_key": ["A"]})
    assert door_to_door(conns, "A", 600, hospitals, {}, CFG)["total_min"] == CFG.ACCESS_MIN
