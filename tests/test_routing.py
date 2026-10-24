"""Connection-scan checks on a three-island toy timetable (BUILD_PLAN section 9)."""
import pandas as pd
import pytest

from kaafu import config as C
from kaafu.routing import Network, earliest_arrival, journey

LASTMILE_MIN = 10
TARGETS = {"gm_hospital": {"H"}}


def make_net(rows):
    conns = pd.DataFrame(rows, columns=["trip_id", "route_id", "from_stop", "to_stop", "dep_min", "arr_min"])
    conns["mode"] = "ferry"
    lm = pd.DataFrame([{"stop_id": "T", "facility_id": "H", "hour": h, "mode": "walk", "minutes": LASTMILE_MIN,
                        "available": True} for h in range(24)])
    return Network.build(conns, lm)


# A -> B -> T on one boat, plus a separate B -> T boat, and the next morning's A -> T boat.
TOY = [
    ("t1", "r1", "A", "B", 480, 510),
    ("t1", "r1", "B", "T", 510, 540),
    ("t2", "r2", "B", "T", 515, 550),
    ("t3", "r3", "A", "T", 1440 + 480, 1440 + 540),
]


def test_direct_boat_arrival():
    net = make_net(TOY)
    r = journey(net, "A", 420, TARGETS)["gm_hospital"]
    assert r["total_min"] == 540 + LASTMILE_MIN - 420
    assert r["wait_min"] == 480 - 420 - C.ACCESS_MIN
    assert r["n_boats"] == 1


def test_after_last_boat_takes_next_morning():
    net = make_net(TOY)
    r = journey(net, "A", 600, TARGETS)["gm_hospital"]
    assert r["total_min"] == 1440 + 540 + LASTMILE_MIN - 600
    assert "+1d" in r["path"]


def test_transfer_needs_transfer_time_staying_on_does_not():
    # t1 reaches B at 510; a different boat from B at 515 is too soon (needs BOAT_TRANSFER_MIN).
    rows = [("t1", "r1", "A", "B", 480, 510), ("t2", "r2", "B", "T", 515, 530),
            ("t3", "r3", "B", "T", 510 + C.BOAT_TRANSFER_MIN, 560)]
    reach, came = earliest_arrival(make_net(rows), "A", 420)
    assert reach["T"] == 560
    # Staying on the same trip with zero dwell is fine.
    reach, _ = earliest_arrival(make_net(TOY), "A", 420)
    assert reach["T"] == 540


def test_unreachable_is_blank():
    r = journey(make_net(TOY), "C", 420, TARGETS)["gm_hospital"]
    assert r["total_min"] is None and r["path"] == "unreachable"


@pytest.mark.parametrize("origin", ["A", "B"])
def test_leaving_later_never_arrives_earlier(origin):
    net = make_net(TOY)
    totals = [journey(net, origin, t, TARGETS)["gm_hospital"]["total_min"] for t in range(0, 1440, 15)]
    arrivals = [t * 15 + (float("inf") if m is None else m) for t, m in enumerate(totals)]
    assert all(b >= a for a, b in zip(arrivals, arrivals[1:]))


def test_nothing_reachable_before_first_boat():
    net = make_net(TOY)
    reach, _ = earliest_arrival(net, "A", 0)
    assert min(v for k, v in reach.items() if k != "A") >= 480
