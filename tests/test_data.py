"""Data checks (BUILD_PLAN section 9), on the committed sheets and the team's processed files."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kaafu import config as C  # noqa: E402
from kaafu import dashboard as D  # noqa: E402
from kaafu import geo  # noqa: E402


def test_check_data_passes():
    D.check_data()


def test_population_totals():
    o = D.load_origins()
    assert len(o) == 23
    assert o.loc[o["atoll"] == "K", "population_2022"].sum() == 17_749
    assert o.loc[o["atoll"] != "K", "population_2022"].sum() == 13_665
    assert o["population_2022"].sum() == 31_414


def test_every_connection_stop_exists_and_departs_before_it_arrives():
    conns = D.load_processed("connections.csv")
    stops = set(D.load_islands()["island_key"]) | set(geo.load_terminals()["terminal_id"])
    assert set(conns["from_stop"]) | set(conns["to_stop"]) <= stops
    assert (conns["dep_min"] < conns["arr_min"]).all()


def test_last_mile_walks():
    lm = D.load_processed("last_mile.csv")
    walk = lm[lm["mode"] == "walk"]
    for t in geo.load_terminals()["terminal_id"]:
        for h in C.GM_HOSPITALS:
            assert len(walk[(walk["stop_id"] == t) & (walk["facility_id"] == h)]) == 24
    igmh = walk[(walk["stop_id"] == "T_MALE_NORTH") & (walk["facility_id"] == "H01")]["minutes"]
    assert igmh.between(20, 25).all()  # plan: Jetty NO5 to IGMH about 20-25 min


def test_no_imei_in_outputs():
    for path in C.PROCESSED.glob("*"):
        if path.is_file():
            head = path.read_text(encoding="utf-8", errors="ignore")[:5000].lower()
            assert "imei" not in head, path.name
