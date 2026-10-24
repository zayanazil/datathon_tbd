"""Kaafu Connect dashboard: streamlit run app/streamlit_app.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import altair as alt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pydeck as pdk  # noqa: E402
import streamlit as st  # noqa: E402

from kaafu import config as C  # noqa: E402
from kaafu import indicators as ind  # noqa: E402
from kaafu import geo  # noqa: E402
from kaafu.geo import ACCESS_BANDS, UNREACHABLE, terminals  # noqa: E402
from kaafu.load import check_all, load_facilities, load_hdx, load_islands, load_origins, load_processed, \
    using_placeholder  # noqa: E402
from kaafu.scenarios import best_ferry_change, connections_for, run_scenario, DEFAULTS  # noqa: E402
from kaafu.timetable import legs, next_day  # noqa: E402

st.set_page_config(page_title="Kaafu Connect", page_icon="⛴️", layout="wide")

# Map colour bands come from geo (M1); categorical slots in fixed order for series.
SERIES = {"Kaafu (9 islands)": "#2a78d6", "All 23 islands": "#eb6834"}
LEGS = {"Home to harbour": "#2a78d6", "Wait": "#eb6834", "Boat": "#1baf7a", "Transfer": "#eda100",
        "Last mile": "#e87ba4"}
TIMES = [f"{m // 60:02d}:{m % 60:02d}" for m in range(0, 1440, C.STEP_MIN)]


def to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def css(rgb: list[int]) -> str:
    return "rgb({},{},{})".format(*rgb)


# --- Cached data --------------------------------------------------------------

@st.cache_data
def static_data():
    notes = check_all()
    return notes, load_islands(), load_origins(), load_facilities(), terminals(), load_hdx(), \
        load_processed("avas_hourly.csv"), load_processed("observed_pairs.csv")


@st.cache_data(show_spinner="Routing 23 islands × 96 departures…")
def scenario(params: tuple):
    p = dict(params)
    access, summary = run_scenario(p)
    return access, summary, connections_for({**DEFAULTS, **p})


@st.cache_data(show_spinner="Trying an extra evening run on every route…")
def ferry_changes(params: tuple):
    return best_ferry_change(dict(params))


@st.cache_data
def route_ids():
    return sorted(legs()["route_id"].unique())


notes, islands, origins, facilities, terms, hdx, avas_hourly, observed_pairs = static_data()

# --- Sidebar ------------------------------------------------------------------

with st.sidebar:
    st.header("Trip")
    dep_label = st.select_slider("Leave home at", TIMES, value="08:00")
    dep = to_min(dep_label)
    target = st.radio("Destination", list(C.TARGETS), format_func=C.TARGETS.get)
    day = st.selectbox("Service day", C.DAYS, index=C.DAYS.index(C.DAY))
    observed = st.radio("Boat times", ["Scheduled", "Observed (FollowMe)"], horizontal=True,
                        disabled=observed_pairs is None,
                        help=None if observed_pairs is not None else "observed_pairs.csv not built yet") != "Scheduled"

    st.header("What if…")
    routes = route_ids()
    ferry_route = st.selectbox("Ferry route to change", ["All routes", *routes])
    ferry_factor = st.slider("Ferry frequency", 0.5, 3.0, 1.0, 0.5, format="×%.1f")
    add_run = st.checkbox("Add an evening run")
    extra_run = None
    if add_run:
        run_route = st.selectbox("Route for the extra run", [r for r in routes if r != "VLM"])
        run_time = st.select_slider("Extra run leaves at", TIMES[64:], value="20:00")
        extra_run = (run_route, to_min(run_time))
    bus_factor = st.slider("Bus frequency", 0.5, 3.0, 1.0, 0.5, format="×%.1f")
    taxi = st.slider("Taxi availability: cut unserved requests by", 0, 100, 0, 10, format="%d%%") / 100
    thul = st.checkbox("Thulusdhoo hospital opens", help="Adds K.Thulusdhoo as an atoll-level hospital (any-hospital target)")

params = (("day", day), ("observed", observed), ("ferry_factor", ferry_factor),
          ("ferry_route", None if ferry_route == "All routes" else ferry_route), ("extra_run", extra_run),
          ("bus_factor", bus_factor), ("taxi_availability", taxi), ("thulusdhoo_hospital", thul))
access, summary, conns = scenario(params)
base_access = scenario((("day", day), ("observed", observed)))[0]

# --- Header -------------------------------------------------------------------

st.title("Kaafu Connect")
st.caption("Door-to-door time from 23 islands to a hospital: wait + boat + transfer + walk, bus or taxi.")
if using_placeholder("ferry_timetable.csv"):
    st.error("**Placeholder ferry timetable.** `data/sheets/ferry_timetable.csv` is missing, so boat times are "
             "invented stand-ins. Do not present these numbers as findings.", icon="⚠️")
if avas_hourly is None:
    st.warning("Taxi times use a flagged 20 km/h placeholder until `avas_hourly.csv` is built.", icon="🚕")

now = ind.at_departure(access, dep, target)
base_now = ind.at_departure(base_access, dep, target)
share = ind.share_within(now, origins)
base_share = ind.share_within(base_now, origins)
y120 = share.set_index("threshold_min").loc[120]
b120 = base_share.set_index("threshold_min").loc[120]
hdx_k = hdx.set_index("threshold_min").loc[120, "hdx_kaafu_pct"]

st.markdown(f"### HDX's car-only estimate: **{hdx_k:.1f}%** of Kaafu within 2 hours of a hospital. "
            f"With real boats leaving at **{dep_label}**: **{y120['kaafu_pct']:.1f}%**.")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Kaafu within 2 h", f"{y120['kaafu_pct']:.1f}%",
          f"{y120['kaafu_pct'] - b120['kaafu_pct']:+.1f} pts vs base"
          if abs(y120['kaafu_pct'] - b120['kaafu_pct']) > 0.05 else None)
c2.metric("All 23 islands within 2 h", f"{y120['all23_pct']:.1f}%",
          f"{y120['all23_pct'] - b120['all23_pct']:+.1f} pts vs base"
          if abs(y120['all23_pct'] - b120['all23_pct']) > 0.05 else None)
c3.metric("HDX car-only, Kaafu", f"{hdx_k:.1f}%")
grey_label = UNREACHABLE[0].replace("Wed-Thu", f"{day}-{next_day(day)}")
pop = origins.set_index("island_key")["population_2022"]
grey = now.reindex(pop.index).isna()
c4.metric(grey_label, f"{int(pop[grey].sum()):,} people",
          f"{int(grey.sum())} island{'' if grey.sum() == 1 else 's'}, {100 * pop[grey].sum() / pop.sum():.0f}% of the 23", delta_color="off")
if grey.any():
    st.caption(f"Grey islands at {dep_label} on {day}: their boat to Malé runs only some days, early in the "
               "morning, so once it has gone there is nothing until a later day. "
               f"({', '.join(pop[grey].index)})")

table = ind.hdx_table(share, hdx).rename(columns={
    "threshold_min": "Within (min)", "kaafu_pct": f"Kaafu, leaving {dep_label} (%)",
    "all23_pct": f"All 23, leaving {dep_label} (%)", "hdx_kaafu_pct": "HDX Kaafu, car-only (%)",
    "hdx_maldives_pct": "HDX Maldives, car-only (%)"})
st.dataframe(table, hide_index=True, width="stretch",
             column_config={c: st.column_config.NumberColumn(format="%.1f") for c in table.columns[1:]})

# --- Map ----------------------------------------------------------------------

left, right = st.columns([3, 2], gap="large")
with left:
    st.subheader(f"Minutes to a hospital, leaving at {dep_label}")
    islands_df = geo.islands_layer(access, dep, target)
    islands_df["tooltip"] = islands_df["tooltip"].str.replace(UNREACHABLE[0], grey_label, regex=False)
    bus_df, obs_df = geo.bus_routes_layer(), geo.observed_trips_layer()
    o1, o2 = st.columns(2)
    show_bus = o1.toggle("Bus routes", disabled=bus_df.empty,
                         help="Needs the Team Kandu RTL bus files in data/raw/" if bus_df.empty else None)
    show_obs = o2.toggle("Observed boat trips", disabled=obs_df.empty,
                         help="Needs observed_trips.csv from M2" if obs_df.empty else None)

    layers = [pdk.Layer("LineLayer", geo.boat_links_layer(conns), id="boat_links",
                        get_source_position=["from_lon", "from_lat"], get_target_position=["to_lon", "to_lat"],
                        get_color=[90, 110, 140, 150], get_width="width_px", width_units="pixels", pickable=True)]
    if show_bus:
        layers.append(pdk.Layer("PathLayer", bus_df, id="bus_routes", get_path="path", get_color=[27, 175, 122, 160],
                                get_width=2, width_units="pixels", pickable=True))
    if show_obs:
        layers.append(pdk.Layer("LineLayer", obs_df, id="observed_trips",
                                get_source_position=["from_lon", "from_lat"], get_target_position=["to_lon", "to_lat"],
                                get_color=[235, 104, 52, 140], get_width=2, width_units="pixels", pickable=True))
    layers += [
        pdk.Layer("ScatterplotLayer", islands_df, id="islands", get_position=["lon", "lat"], get_radius="radius_m",
                  get_fill_color="colour", radius_min_pixels=5, stroked=True, get_line_color=[255, 255, 255],
                  line_width_min_pixels=2, pickable=True),
        pdk.Layer("ScatterplotLayer", geo.hospitals_layer(), id="hospitals", get_position=["lon", "lat"],
                  get_fill_color=[20, 20, 20], get_radius=250, radius_min_pixels=4, stroked=True,
                  get_line_color=[255, 255, 255], line_width_min_pixels=2, pickable=True),
        pdk.Layer("ScatterplotLayer", geo.terminals_layer(), id="terminals", get_position=["lon", "lat"],
                  get_fill_color=[98, 80, 214], get_radius=150, radius_min_pixels=3, pickable=True),
    ]
    st.pydeck_chart(pdk.Deck(layers=layers, map_provider="carto", map_style="light",
                             initial_view_state=pdk.ViewState(latitude=4.1, longitude=73.25, zoom=8),
                             tooltip={"text": "{tooltip}"}), width="stretch")
    bands = [(label, rgb) for label, _, rgb in ACCESS_BANDS] + [(grey_label, UNREACHABLE[1])]
    legend = " &nbsp; ".join(f"<span style='color:{css(rgb)}'>●</span> {label}" for label, rgb in bands)
    st.markdown(f"{legend}<br/><b>●</b> hospital &nbsp; <span style='color:#6250d6'>●</span> ferry terminal &nbsp; "
                "lines = boat links (wider = more boats a day) &nbsp; circle area = population",
                unsafe_allow_html=True)

# --- Island panel ----------------------------------------------------------------

with right:
    st.subheader("One island's trip")
    worst = now.fillna(np.inf).idxmax()
    opts = origins["island_key"].tolist()
    pick = st.selectbox("Island", opts, index=opts.index(worst), help="Defaults to the worst-served island now")
    row = access[(access["origin_key"] == pick) & (access["dep_min"] == dep) & (access["target"] == target)].iloc[0]
    srow = summary.set_index("origin_key").loc[pick]

    if pd.isna(row["total_min"]):
        st.error(f"No way to reach a hospital from {pick} leaving at {dep_label} on {day} (or the next day).")
    else:
        parts = pd.DataFrame({"leg": list(LEGS), "minutes": [
            C.ACCESS_MIN, row["wait_min"], row["boat_min"], row["transfer_min"], row["lastmile_min"]]})
        parts["order"] = range(len(parts))
        bar = alt.Chart(parts).mark_bar(height=28, stroke="white", strokeWidth=2).encode(
            x=alt.X("minutes:Q", stack="zero", title="minutes"),
            color=alt.Color("leg:N", scale=alt.Scale(domain=list(LEGS), range=list(LEGS.values())),
                            legend=alt.Legend(orient="bottom", title=None)),
            order="order:Q",
            tooltip=["leg", alt.Tooltip("minutes:Q", format=".0f")],
        ).properties(height=90)
        st.altair_chart(bar, width="stretch")
        st.markdown(f"**{row['total_min']:.0f} min** door to door, to **{row['facility_id']}** "
                    f"({facilities.set_index('facility_id').name.get(row['facility_id'], row['facility_id'])}) "
                    f"by {row['lastmile_mode']} at the end.")
        st.caption(f"Route: {row['path']}")

    m1, m2, m3 = st.columns(3)
    m1.metric("Population", f"{int(srow['population']):,}")
    m2.metric("Boats a day", int(srow["boats_per_day"]))
    m3.metric("Last practical departure", srow["last_practical_departure"])
    m4, m5 = st.columns(2)
    m4.metric("Daytime median", "unreachable" if pd.isna(srow["day_median_min"]) else f"{srow['day_median_min']:.0f} min")
    gap = srow["observed_gap_min"]
    m5.metric("Scheduled − observed (daytime median)", "no FollowMe data" if pd.isna(gap) else f"{gap:+.0f} min")
    if observed_pairs is not None:
        op = observed_pairs[observed_pairs["from_key"] == pick]
        if not op.empty:
            st.dataframe(op, hide_index=True, width="stretch")

# --- Through the day ----------------------------------------------------------------

st.subheader("Share of people within 2 hours, by leave-home time")
td = ind.through_day(access, origins, target).melt("dep_min", var_name="group", value_name="pct")
td["group"] = td["group"].map({"kaafu_pct": "Kaafu (9 islands)", "all23_pct": "All 23 islands"})
td["time"] = td["dep_min"].map(lambda m: f"{m // 60:02d}:{m % 60:02d}")
hover = alt.selection_point(fields=["dep_min"], nearest=True, on="pointerover", empty=False)
base = alt.Chart(td).encode(x=alt.X("dep_min:Q", title="leave home at",
                                    scale=alt.Scale(domain=[0, 1440]),
                                    axis=alt.Axis(values=list(range(0, 1441, 180)),
                                                  labelExpr="timeFormat(datum.value*60000, '%H:%M')")))
lines = base.mark_line(strokeWidth=2, interpolate="step-after").encode(
    y=alt.Y("pct:Q", title="% of population", scale=alt.Scale(domain=[0, 100])),
    color=alt.Color("group:N", scale=alt.Scale(domain=list(SERIES), range=list(SERIES.values())),
                    legend=alt.Legend(orient="top", title=None)))
rule = base.mark_rule(color="#8a8984").encode(
    opacity=alt.condition(hover, alt.value(1), alt.value(0)),
    tooltip=[alt.Tooltip("time:N", title="leave at"), alt.Tooltip("group:N"), alt.Tooltip("pct:Q", format=".1f")]
).add_params(hover)
now_rule = alt.Chart(pd.DataFrame({"dep_min": [dep]})).mark_rule(strokeDash=[4, 3], color="#52514e").encode(x="dep_min:Q")
hdx_rule = alt.Chart(pd.DataFrame({"y": [hdx_k], "label": ["HDX car-only, Kaafu"]})).mark_rule(
    strokeDash=[2, 2], color="#52514e").encode(y="y:Q", tooltip=["label", "y"])
st.altair_chart((lines + rule + now_rule + hdx_rule).properties(height=260), width="stretch")

a1, a2 = st.columns(2)
with a1:
    st.subheader("Taxi requests unserved, by hour")
    if avas_hourly is None:
        st.info("Build `avas_hourly.csv` (Avas raw file in data/raw/, then `python -m kaafu.pipeline`).")
    else:
        av = avas_hourly[avas_hourly["zone"] == "all"].assign(pct=lambda d: 100 * d["expired_share"])
        st.altair_chart(alt.Chart(av).mark_bar(color="#2a78d6", cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
            x=alt.X("hour:O", title="hour of request"), y=alt.Y("pct:Q", title="% expired"),
            tooltip=["hour", alt.Tooltip("pct:Q", format=".1f"), "completed", "expired"]).properties(height=220),
            width="stretch")
with a2:
    st.subheader("NSDS-style indicators")
    n = ind.nsds(access, origins, conns)
    st.metric("People on islands with a daily scheduled boat to Greater Malé", f"{n['pct_with_daily_boat_to_gm']:.1f}%")
    st.metric("Within 30 min of any health facility (on-island centres)", f"{n['pct_within_30_health_facility']:.1f}%")
    st.metric("Within 2 h of a Greater Malé hospital (daytime median)",
              f"{n['pct_within_120_hospital_daytime_median']:.1f}%")

# --- Best ferry change ----------------------------------------------------------------

st.subheader("Best ferry change")
st.caption("One extra Malé-bound departure per route at 18:00, 20:00 or 22:00, ranked by people newly within "
           "2 h (population × share of 12:00–23:45 departures), then population-weighted minutes saved.")
if st.button("Rank the changes"):
    st.dataframe(ferry_changes(params), hide_index=True, width="stretch")

with st.expander("Table view: every island at this departure"):
    view = access[(access["dep_min"] == dep) & (access["target"] == target)].merge(
        origins[["island_key", "population_2022"]], left_on="origin_key", right_on="island_key")
    st.dataframe(view.drop(columns=["island_key", "scenario"]), hide_index=True, width="stretch")

with st.expander("Assumptions and data notes"):
    st.markdown("\n".join(f"- {x}" for x in [
        f"Home to harbour {C.ACCESS_MIN} min; boat to street {C.TERMINAL_EXIT_MIN} min; "
        f"changing boats ≥ {C.BOAT_TRANSFER_MIN} min; walking {C.WALK_M_PER_MIN} m/min in straight lines.",
        "Malé ferry rows without a named terminal land at Jetty NO5.",
        f"Senahiya military hospital {'included' if C.INCLUDE_SENAHIYA else 'excluded'} as a destination.",
        "Out of scope: flights, chartered speedboats, ambulance boats.",
        "FollowMe is Aug 2025, Avas is Aug–Sep 2026: different years from the timetable.",
        *notes]))
