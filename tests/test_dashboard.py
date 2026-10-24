"""The dashboard on the team's code: the adapter in kaafu.dashboard, and the app itself."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kaafu import dashboard as D  # noqa: E402
from kaafu import scenarios  # noqa: E402


def test_default_view_is_m3s_published_run():
    access, summary, conns, source = D.run({})
    assert source == D.TEAM_RESULTS
    m3, _ = scenarios.run_scenario({})
    j = access.merge(m3, on=["origin_key", "dep_min", "target"], suffixes=("_pub", "_m3"))
    assert len(j) == 4416
    assert ((j["total_min_pub"].fillna(-1) - j["total_min_m3"].fillna(-1)).abs() <= 0.15).all()


def test_default_scenario_connections_are_m3s():
    built, published = D.scenario_connections({}), D.load_processed("connections.csv")
    key = ["from_stop", "to_stop", "dep_min", "arr_min"]
    assert sorted(map(tuple, built[key].values)) == sorted(map(tuple, published[key].values))


def test_slider_values_map_to_m3_parameters():
    q = D.m3_params({"ferry_factor": 2.0, "ferry_route": "309", "extra_run": ("307", 1320), "observed": True})
    assert q["ferry_factor"] == {"309": 2.0} and q["extra_runs"] == [("307", 1320)] and q["observed"]
    assert D.m3_params({"ferry_factor": 2.0})["ferry_factor"] == {r: 2.0 for r in D.route_ids()}
    assert D.m3_params({})["ferry_factor"] == {} and D.m3_params({})["extra_runs"] == []


def test_headline_figures():
    """M3's handover: ferries only 0% of Kaafu within 2 h; with observed speedboats 21.5% (09:00)."""
    origins = D.load_origins()
    base, _, _, _ = D.run({})
    assert D.share_within(D.at_departure(base, 540, "gm_hospital"), origins, [120])["kaafu_pct"].iloc[0] == 0
    obs, _, _, _ = D.run({"observed": True})
    assert round(D.share_within(D.at_departure(obs, 540, "gm_hospital"), origins, [120])["kaafu_pct"].iloc[0], 1) == 21.5


def test_hdx_table_has_every_threshold():
    t = D.load_hdx()
    assert t["threshold_min"].tolist() == D.THRESHOLDS_MIN
    assert round(t.set_index("threshold_min").loc[120, "hdx_kaafu_pct"], 1) == 77.4


def test_bus_routes_follow_the_roads():
    paths = D.bus_routes_layer()
    assert len(paths) == 15 and (paths["path"].map(len) > 50).all()


def test_app_runs_through_the_demo():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=300).run()
    assert not at.exception
    at.sidebar.select_slider[0].set_value("09:00").run()
    assert [m.value for m in at.metric][3] == "8,847 people"  # M1's grey-island finding
    at.sidebar.toggle[1].set_value(True).run()                 # add an evening run
    at.sidebar.toggle[2].set_value(True).run()                 # Thulusdhoo hospital
    at.sidebar.radio[0].set_value("any_hospital").run()
    at.sidebar.toggle[0].set_value(True).run()                 # observed boat times
    at.toggle[0].set_value(True).run()                         # bus routes layer
    at.toggle[1].set_value(True).run()                         # observed trips layer
    assert not at.exception
