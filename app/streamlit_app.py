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

ASSETS = Path(__file__).parent / "assets"
st.set_page_config(page_title="Kaafu Connect", page_icon=str(ASSETS / "mark.svg"), layout="wide")
st.logo(str(ASSETS / "wordmark.svg"), icon_image=str(ASSETS / "mark.svg"), size="large")

# Brand neutrals and one accent (also in .streamlit/config.toml). Data colours below are separate.
INK, MUTED, LINE, SURFACE, ACCENT = "#111418", "#6B7178", "#E6E7E3", "#F5F6F4", "#0E7C86"
# Map colour bands come from geo (M1); categorical slots in fixed order for series.
SERIES = {"Kaafu (9 islands)": "#2a78d6", "All 23 islands": "#eb6834"}
LEGS = {"Home to harbour": "#2a78d6", "Wait": "#eb6834", "Boat": "#1baf7a", "Transfer": "#eda100",
        "Last mile": "#e87ba4"}
TIMES = [f"{m // 60:02d}:{m % 60:02d}" for m in range(0, 1440, C.STEP_MIN)]

st.markdown(f"""<style>
.block-container {{ padding-top: 3.2rem; padding-bottom: 3rem; max-width: 1360px; }}
[data-testid="stDecoration"] {{ display: none; }}
h1, h2, h3 {{ letter-spacing: -0.02em; }}
h3 {{ font-size: 1.05rem !important; margin-bottom: .25rem; }}
[data-testid="stCaptionContainer"] {{ color: {MUTED}; }}
[data-testid="stMetric"] {{ min-height: 7.6rem; background: #fff; border: 1px solid {LINE}; border-radius: 14px; padding: 14px 18px; }}
[data-testid="stMetricLabel"] p {{ color: {MUTED}; font-size: .8rem; font-weight: 500; }}
[data-testid="stMetricValue"] {{ font-size: 1.65rem; font-weight: 600; letter-spacing: -0.02em; }}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{ font-size: .85rem; }}
[data-testid="stSidebar"] [role="radiogroup"] p, [data-testid="stSidebar"] [data-baseweb="select"] div {{ font-size: .9rem; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 1.6rem; border-bottom: 1px solid {LINE}; }}
.stTabs [data-baseweb="tab"] {{ padding: .4rem 0; font-weight: 500; color: {MUTED}; }}
.stTabs [aria-selected="true"] {{ color: {INK}; }}
.kc-label {{ font-size: .7rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase;
             color: {MUTED}; margin: .6rem 0 .2rem; }}
.kc-top {{ display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap;
           margin-bottom: 1.6rem; }}
.kc-title {{ font-size: 1.35rem; font-weight: 650; letter-spacing: -0.02em; color: {INK}; }}
.kc-chips {{ display: flex; gap: .4rem; flex-wrap: wrap; }}
.kc-chip {{ font-size: .78rem; color: {INK}; background: {SURFACE}; border: 1px solid {LINE};
            border-radius: 999px; padding: .2rem .7rem; }}
.kc-hero {{ display: flex; align-items: flex-end; gap: 2.4rem; flex-wrap: wrap; margin: .2rem 0 1.4rem; }}
.kc-eyebrow {{ font-size: .8rem; color: {MUTED}; margin-bottom: .5rem; }}
.kc-num {{ font-size: 3.2rem; font-weight: 650; letter-spacing: -0.04em; line-height: 1; color: {INK}; }}
.kc-num.muted {{ color: #A3A7AC; }}
.kc-cap {{ font-size: .85rem; color: {MUTED}; margin-top: .35rem; }}
.kc-vs {{ font-size: 1.4rem; color: #C2C5C8; padding-bottom: 1.3rem; }}
.kc-note {{ font-size: .85rem; color: {MUTED}; border-left: 2px solid {LINE}; padding: .1rem 0 .1rem .8rem;
            margin: .9rem 0 .4rem; }}
.kc-legend {{ display: flex; flex-wrap: wrap; gap: .3rem 1rem; font-size: .8rem; color: {INK}; margin-top: .5rem; }}
.kc-legend i {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: .35rem; }}
.kc-legend .meta {{ color: {MUTED}; }}
.kc-total {{ font-size: 2.2rem; font-weight: 650; letter-spacing: -0.03em; line-height: 1.1; }}
.kc-stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: .9rem 1rem; margin-top: 1rem;
             border-top: 1px solid {LINE}; padding-top: .9rem; }}
.kc-stats div {{ font-size: .75rem; color: {MUTED}; }}
.kc-stats b {{ display: block; font-size: 1rem; font-weight: 600; color: {INK}; margin-top: .1rem; }}
.kc-path {{ font-size: .78rem; color: {MUTED}; margin-top: .4rem; word-break: break-word; }}
</style>""", unsafe_allow_html=True)


def to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def first_upper(text: str) -> str:
    return text[:1].upper() + text[1:]


def css(rgb: list[int]) -> str:
    return "rgb({},{},{})".format(*rgb)


def label(text: str):
    st.markdown(f"<div class='kc-label'>{text}</div>", unsafe_allow_html=True)


def styled(chart, height: int):
    """Quiet chart chrome: no frame or axis lines, faint grid, muted labels."""
    return (chart.properties(height=height)
            .configure(font="Inter", background="transparent")
            .configure_view(stroke=None)
            .configure_axis(labelColor=MUTED, titleColor=MUTED, labelFontSize=11, titleFontSize=11,
                            titleFontWeight=500, gridColor="#EEEFEC", domain=False, tickColor=LINE)
            .configure_legend(labelColor=INK, labelFontSize=11, symbolType="circle", title=None))


def weighted_median(minutes: pd.Series, weights: pd.Series) -> float:
    m = minutes.reindex(weights.index).fillna(np.inf)
    order = m.sort_values().index
    cum = weights[order].cumsum()
    return float(m[order][cum >= weights.sum() / 2].iloc[0])


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
    label("Trip")
    dep_label = st.select_slider("Leave home at", TIMES, value="08:00")
    dep = to_min(dep_label)
    target = st.radio("Destination", list(C.TARGETS), format_func=C.TARGETS.get)
    day = st.selectbox("Service day", C.DAYS, index=C.DAYS.index(C.DAY))
    observed = st.toggle("Observed boat times", disabled=observed_pairs is None,
                         help="FollowMe GPS boat times (Aug 2025) instead of the timetable"
                         if observed_pairs is not None else "observed_pairs.csv not built yet")

    label("What if")
    routes = route_ids()
    ferry_route = st.selectbox("Ferry route", ["All routes", *routes])
    ferry_factor = st.slider("Ferry frequency", 0.5, 3.0, 1.0, 0.5, format="×%.1f")
    add_run = st.toggle("Add an evening run")
    extra_run = None
    if add_run:
        run_route = st.selectbox("Route for the extra run", [r for r in routes if r != "VLM"])
        run_time = st.select_slider("Extra run leaves at", TIMES[64:], value="20:00")
        extra_run = (run_route, to_min(run_time))
    bus_factor = st.slider("Bus frequency", 0.5, 3.0, 1.0, 0.5, format="×%.1f")
    taxi = st.slider("Cut unserved taxi requests by", 0, 100, 0, 10, format="%d%%") / 100
    thul = st.toggle("Thulusdhoo hospital opens", help="Adds K.Thulusdhoo as an atoll-level hospital "
                                                       "(any-hospital target)")

params = (("day", day), ("observed", observed), ("ferry_factor", ferry_factor),
          ("ferry_route", None if ferry_route == "All routes" else ferry_route), ("extra_run", extra_run),
          ("bus_factor", bus_factor), ("taxi_availability", taxi), ("thulusdhoo_hospital", thul))
access, summary, conns = scenario(params)
base_access = scenario((("day", day), ("observed", observed)))[0]
is_base = access["scenario"].iloc[0] == "base"

# --- Numbers ------------------------------------------------------------------

now = ind.at_departure(access, dep, target)
base_now = ind.at_departure(base_access, dep, target)
share = ind.share_within(now, origins)
base_share = ind.share_within(base_now, origins)
y120 = share.set_index("threshold_min").loc[120]
b120 = base_share.set_index("threshold_min").loc[120]
hdx_k = hdx.set_index("threshold_min").loc[120, "hdx_kaafu_pct"]
grey_label = UNREACHABLE[0].replace("Wed-Thu", f"{day}-{next_day(day)}")
pop = origins.set_index("island_key")["population_2022"]
grey = now.reindex(pop.index).isna()
median_now = weighted_median(now, pop)

# --- Header -------------------------------------------------------------------

chips = [day, dep_label, C.TARGETS[target], "Observed boats" if observed else "Scheduled boats"]
if not is_base:
    chips.append("Scenario on")
st.markdown(f"""<div class="kc-top">
  <div class="kc-title">Island access to hospitals</div>
  <div class="kc-chips">{''.join(f'<span class="kc-chip">{c}</span>' for c in chips)}</div>
</div>""", unsafe_allow_html=True)

if using_placeholder("ferry_timetable.csv"):
    st.error("**Placeholder ferry timetable.** `data/sheets/ferry_timetable.csv` is missing, so boat times are "
             "invented stand-ins. Do not present these numbers as findings.", icon=":material/warning:")
if avas_hourly is None:
    st.warning("Taxi times use a flagged 20 km/h placeholder until `avas_hourly.csv` is built.",
               icon=":material/local_taxi:")

st.markdown(f"""<div class="kc-eyebrow">Share of Kaafu within 2 hours of a hospital</div>
<div class="kc-hero">
  <div><div class="kc-num muted">{hdx_k:.1f}%</div><div class="kc-cap">by car, HDX global estimate</div></div>
  <div class="kc-vs">vs</div>
  <div><div class="kc-num">{y120['kaafu_pct']:.1f}%</div>
       <div class="kc-cap">by real boat, leaving at {dep_label} on {day}</div></div>
</div>""", unsafe_allow_html=True)


def delta(now_pct, base_pct):
    return f"{now_pct - base_pct:+.1f} pts vs base" if abs(now_pct - base_pct) > 0.05 else None


c1, c2, c3, c4 = st.columns(4)
c1.metric("Kaafu within 2 h", f"{y120['kaafu_pct']:.1f}%", delta(y120["kaafu_pct"], b120["kaafu_pct"]))
c2.metric("All 23 islands within 2 h", f"{y120['all23_pct']:.1f}%", delta(y120["all23_pct"], b120["all23_pct"]))
c3.metric("Median trip, all 23 islands", "over a day" if not np.isfinite(median_now) else
          (f"{median_now / 60:.1f} h" if median_now >= 120 else f"{median_now:.0f} min"))
c4.metric(first_upper(grey_label), f"{int(pop[grey].sum()):,} people",
          f"{int(grey.sum())} island{'' if grey.sum() == 1 else 's'} · {100 * pop[grey].sum() / pop.sum():.0f}%",
          delta_color="off", delta_arrow="off")
if grey.any():
    st.markdown(f"<div class='kc-note'>Grey islands at {dep_label}: their boat to Malé runs only some days, "
                f"early in the morning, so once it has gone there is nothing until a later day. "
                f"{', '.join(k.split('.', 1)[1] for k in pop[grey].index)}.</div>", unsafe_allow_html=True)

st.write("")
tab_map, tab_day, tab_bench, tab_ferry, tab_data = st.tabs(
    ["Map", "Through the day", "Benchmarks", "Ferry changes", "Data"])

# --- Map and island panel -----------------------------------------------------

with tab_map:
    left, right = st.columns([3, 2], gap="large")
    with left:
        # islands_layer filters on scenario, so pass this run's name, not the "base" default.
        islands_df = geo.islands_layer(access, dep, target, scenario=access["scenario"].iloc[0])
        islands_df["tooltip"] = islands_df["tooltip"].str.replace(UNREACHABLE[0], grey_label, regex=False)
        bus_df, obs_df = geo.bus_routes_layer(), geo.observed_trips_layer()
        toggles = st.container(horizontal=True, gap="large")
        show_bus = toggles.toggle("Bus routes", disabled=bus_df.empty,
                             help="Needs data/processed/bus_routes.csv from M1" if bus_df.empty else None)
        show_obs = toggles.toggle("Observed trips", disabled=obs_df.empty,
                             help="Needs observed_pairs.csv from M2" if obs_df.empty else None)

        # Layer styling follows M1's geo.example_deck; colours come from each layer's `colour` column.
        lines = dict(get_source_position=["from_lon", "from_lat"], get_target_position=["to_lon", "to_lat"],
                     get_color="colour", get_width="width_px", pickable=True)
        layers = []
        if show_bus:
            layers.append(pdk.Layer("PathLayer", bus_df, id="bus_routes", get_path="path", get_color="colour",
                                    width_min_pixels=1, pickable=True))
        layers.append(pdk.Layer("LineLayer", geo.boat_links_layer(conns), id="boat_links", **lines))
        if show_obs:
            layers.append(pdk.Layer("LineLayer", obs_df, id="observed_trips", **lines))
        layers += [
            # 2px white ring keeps overlapping island circles apart
            pdk.Layer("ScatterplotLayer", islands_df, id="islands", get_position=["lon", "lat"],
                      get_radius="radius_m", radius_scale=4, radius_min_pixels=4, get_fill_color="colour", stroked=True,
                      get_line_color=[255, 255, 255], line_width_min_pixels=2, pickable=True),
            pdk.Layer("ScatterplotLayer", geo.hospitals_layer(), id="hospitals", get_position=["lon", "lat"],
                      get_radius=150, radius_min_pixels=5, get_fill_color="colour", stroked=True,
                      get_line_color=[208, 59, 59], line_width_min_pixels=2, pickable=True),
            pdk.Layer("ScatterplotLayer", geo.terminals_layer(), id="terminals", get_position=["lon", "lat"],
                      get_radius=100, radius_min_pixels=4, get_fill_color="colour", pickable=True),
        ]
        st.pydeck_chart(pdk.Deck(layers=layers, map_provider="carto", map_style="light",
                                 initial_view_state=pdk.ViewState(latitude=4.1, longitude=73.25, zoom=8),
                                 tooltip={"text": "{tooltip}"}), width="stretch", height=540)
        bands = [(lab, rgb) for lab, _, rgb in ACCESS_BANDS] + [(grey_label, UNREACHABLE[1])]
        chips_html = "".join(f"<span><i style='background:{css(rgb)}'></i>{first_upper(lab)}</span>"
                             for lab, rgb in bands)
        extra = ("<span><i style='background:rgb(70,110,150)'></i>Observed slow</span>"
                 "<span><i style='background:rgb(150,90,170)'></i>Observed fast</span>") if show_obs else ""
        st.markdown(f"<div class='kc-legend'>{chips_html}{extra}</div>"
                    "<div class='kc-legend meta'><span><i style='background:#fff;border:2px solid rgb(208,59,59)'>"
                    "</i>Hospital</span><span><i style='background:rgb(40,40,40)'></i>Ferry terminal</span>"
                    "<span>Circle area = population · line width = boats a day</span></div>",
                    unsafe_allow_html=True)

    with right:
        worst = now.fillna(np.inf).idxmax()
        opts = origins["island_key"].tolist()
        pick = st.selectbox("Island", opts, index=opts.index(worst),
                            format_func=lambda k: k.split(".", 1)[1] + f"  ·  {k.split('.')[0]}",
                            help="Starts on the worst-served island at this time")
        row = access[(access["origin_key"] == pick) & (access["dep_min"] == dep)
                     & (access["target"] == target)].iloc[0]
        srow = summary.set_index("origin_key").loc[pick]

        if pd.isna(row["total_min"]):
            st.markdown(f"<div class='kc-total' style='color:#8C8C88'>No boat</div>"
                        f"<div class='kc-cap'>Nothing reaches a hospital from {pick.split('.', 1)[1]} leaving "
                        f"{dep_label} on {day}, or the next day.</div>", unsafe_allow_html=True)
        else:
            hosp = facilities.set_index("facility_id").name.get(row["facility_id"], row["facility_id"])
            total = row["total_min"]
            nice = f"{int(total // 60)} h {int(total % 60):02d} min" if total >= 60 else f"{total:.0f} min"
            st.markdown(f"<div class='kc-total'>{nice}</div><div class='kc-cap'>door to door to {hosp}, "
                        f"{row['lastmile_mode']} at the end</div>", unsafe_allow_html=True)
            parts = pd.DataFrame({"leg": list(LEGS), "minutes": [
                C.ACCESS_MIN, row["wait_min"], row["boat_min"], row["transfer_min"], row["lastmile_min"]]})
            parts["order"] = range(len(parts))
            bar = alt.Chart(parts).mark_bar(height=22, stroke="white", strokeWidth=2).encode(
                x=alt.X("minutes:Q", stack="zero", title=None, axis=alt.Axis(grid=False, tickCount=4)),
                color=alt.Color("leg:N", scale=alt.Scale(domain=list(LEGS), range=list(LEGS.values())),
                                legend=alt.Legend(orient="bottom", columns=3)),
                order="order:Q",
                tooltip=["leg", alt.Tooltip("minutes:Q", format=".0f")],
            )
            st.altair_chart(styled(bar, 70), theme=None, width="stretch")
            st.markdown(f"<div class='kc-path'>{row['path']}</div>", unsafe_allow_html=True)

        median = "unreachable" if pd.isna(srow["day_median_min"]) else f"{srow['day_median_min']:.0f} min"
        gap = srow["observed_gap_min"]
        stats = [("Population", f"{int(srow['population']):,}"), ("Boats a day", int(srow["boats_per_day"])),
                 ("Last practical departure", srow["last_practical_departure"]),
                 ("Daytime median", median),
                 ("Scheduled − observed", "no data" if pd.isna(gap) else f"{gap:+.0f} min"),
                 ("Atoll", pick.split(".")[0])]
        st.markdown("<div class='kc-stats'>" + "".join(f"<div>{k}<b>{v}</b></div>" for k, v in stats)
                    + "</div>", unsafe_allow_html=True)
        if observed_pairs is not None:
            op = observed_pairs[observed_pairs["from_key"] == pick]
            if not op.empty:
                with st.expander("Observed boat trips from this island"):
                    st.dataframe(op, hide_index=True, width="stretch")

# --- Through the day ----------------------------------------------------------

with tab_day:
    st.markdown("### Share within 2 hours, by leave-home time")
    td = ind.through_day(access, origins, target).melt("dep_min", var_name="group", value_name="pct")
    td["group"] = td["group"].map({"kaafu_pct": "Kaafu (9 islands)", "all23_pct": "All 23 islands"})
    td["time"] = td["dep_min"].map(lambda m: f"{m // 60:02d}:{m % 60:02d}")
    hover = alt.selection_point(fields=["dep_min"], nearest=True, on="pointerover", empty=False)
    base = alt.Chart(td).encode(x=alt.X("dep_min:Q", title="leave home at",
                                        scale=alt.Scale(domain=[0, 1440]),
                                        axis=alt.Axis(values=list(range(0, 1441, 180)), grid=False,
                                                      labelExpr="utcFormat(datum.value*60000, '%H:%M')")))
    trend = base.mark_line(strokeWidth=2, interpolate="step-after").encode(
        y=alt.Y("pct:Q", title="% of population", scale=alt.Scale(domain=[0, 100]), axis=alt.Axis(tickCount=5)),
        color=alt.Color("group:N", scale=alt.Scale(domain=list(SERIES), range=list(SERIES.values())),
                        legend=alt.Legend(orient="top")))
    rule = base.mark_rule(color="#8a8984").encode(
        opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("time:N", title="leave at"), alt.Tooltip("group:N"),
                 alt.Tooltip("pct:Q", format=".1f")]).add_params(hover)
    now_rule = alt.Chart(pd.DataFrame({"dep_min": [dep]})).mark_rule(strokeDash=[4, 3], color=MUTED) \
        .encode(x="dep_min:Q")
    hdx_rule = alt.Chart(pd.DataFrame({"y": [hdx_k], "label": ["HDX car-only, Kaafu"]})).mark_rule(
        strokeDash=[2, 2], color=MUTED).encode(y="y:Q", tooltip=["label", "y"])
    st.altair_chart(styled(trend + rule + now_rule + hdx_rule, 300), theme=None, width="stretch")
    st.caption("Dashed vertical line: your leave-home time. Dashed horizontal line: HDX car-only estimate for Kaafu.")

    st.markdown("### Taxi requests unserved, by hour")
    if avas_hourly is None:
        st.info("Build `avas_hourly.csv` (Avas raw file in data/raw/, then `python -m kaafu.pipeline`).")
    else:
        av = avas_hourly[avas_hourly["zone"] == "all"].assign(pct=lambda d: 100 * d["expired_share"])
        taxi_chart = alt.Chart(av).mark_bar(color="#2a78d6", cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
            x=alt.X("hour:O", title="hour of request", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("pct:Q", title="% expired", axis=alt.Axis(tickCount=4)),
            tooltip=["hour", alt.Tooltip("pct:Q", format=".1f"), "completed", "expired"])
        st.altair_chart(styled(taxi_chart, 200), theme=None, width="stretch")

# --- Benchmarks -----------------------------------------------------------------

with tab_bench:
    st.markdown(f"### Within X minutes of a hospital, leaving at {dep_label}")
    table = ind.hdx_table(share, hdx).rename(columns={
        "threshold_min": "Within (min)", "kaafu_pct": "Kaafu, real boats (%)",
        "all23_pct": "All 23, real boats (%)", "hdx_kaafu_pct": "Kaafu, HDX car-only (%)",
        "hdx_maldives_pct": "Maldives, HDX car-only (%)"})
    for col in table.columns[1:]:
        table[col] = table[col].map(lambda v: "—" if pd.isna(v) else f"{v:.1f}")
    st.dataframe(table, hide_index=True, width="stretch")
    st.caption("HDX is a car-only model with its own population base: compare percentages, not head counts.")

    st.markdown("### NSDS-style indicators")
    n = ind.nsds(access, origins, conns)
    k1, k2, k3 = st.columns(3)
    k1.metric("Daily scheduled boat to Greater Malé", f"{n['pct_with_daily_boat_to_gm']:.1f}%",
              help="Share of people on islands with at least one daily scheduled boat to Greater Malé")
    k2.metric("Within 30 min of a health facility", f"{n['pct_within_30_health_facility']:.1f}%",
              help="On-island health centres")
    k3.metric("Within 2 h of a Greater Malé hospital", f"{n['pct_within_120_hospital_daytime_median']:.1f}%",
              help="Daytime median trip, departures 06:00–18:00")

# --- Ferry changes ---------------------------------------------------------------

with tab_ferry:
    st.markdown("### Which one extra ferry helps most?")
    st.caption("One extra Malé-bound departure per route at 18:00, 20:00 or 22:00, ranked by people newly within "
               "2 h (population × share of 12:00–23:45 departures), then population-weighted minutes saved.")
    if st.button("Rank the changes", type="primary", icon=":material/sort:"):
        st.dataframe(ferry_changes(params), hide_index=True, width="stretch")

# --- Data -------------------------------------------------------------------------

with tab_data:
    st.markdown(f"### Every island, leaving at {dep_label}")
    view = access[(access["dep_min"] == dep) & (access["target"] == target)].merge(
        origins[["island_key", "population_2022"]], left_on="origin_key", right_on="island_key")
    st.dataframe(view.drop(columns=["island_key", "scenario"]), hide_index=True, width="stretch")

    st.markdown("### Assumptions")
    st.markdown("\n".join(f"- {x}" for x in [
        f"Home to harbour {C.ACCESS_MIN} min; boat to street {C.TERMINAL_EXIT_MIN} min; "
        f"changing boats ≥ {C.BOAT_TRANSFER_MIN} min; walking {C.WALK_M_PER_MIN} m/min in straight lines.",
        "Malé ferry rows without a named terminal land at Jetty NO5.",
        f"Senahiya military hospital {'included' if C.INCLUDE_SENAHIYA else 'excluded'} as a destination.",
        "Out of scope: flights, chartered speedboats, ambulance boats.",
        "FollowMe is Aug 2025, Avas is Aug–Sep 2026: different years from the timetable.",
        *notes]))
    st.caption("Sources: MTCC/RTL ferry and bus timetables · Census 2022 (MBS) via Team Kandu · "
               "© OpenStreetMap contributors (ODbL) · OSRM · FollowMe and Avas (organisers) · HDX.")
