"""Final figures for slides 5-6 (M3 Step 5).

    PYTHONPATH=src python -m kaafu.m3_figures

Writes docs/figures/m3_*.png and docs/figures/m3_slide_numbers.md from the base
scenario (public ferries only) and the observed switch (+ observed speedboats).
Colours follow the entity in every chart: orange = ferries only (a hollow ring in
dot charts), blue = with observed speedboats, grey = HDX car-only benchmark.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from kaafu import indicators, scenarios  # noqa: E402

FERRY, SPEEDBOAT, HDX = "#eb6834", "#2a78d6", "#898781"
SURFACE, INK, INK_2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
FERRY_LABEL, SPEEDBOAT_LABEL = "Public ferries only", "With observed speedboats"
CAPTION = ("Wednesday CFN timetable; observed speedboats from FollowMe, Aug 2025 (not a published "
           "schedule). Malé jetty assumed Jetty NO5. Door to door: home, boat, walk/bus/taxi.")
UNREACHABLE_X = 1.1  # the "unreachable today" column sits this far past the axis end (fraction of span)

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 11,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK_2,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK_2, "ytick.labelcolor": INK_2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "grid.linestyle": "-",
    "legend.frameon": False, "legend.labelcolor": INK_2,
})


def _figure(height, title, subtitle, top_in=1.35, bottom_in=0.85, left=0.17, right=0.97):
    """A 12-inch-wide figure with title and subtitle at fixed distances from the top."""
    fig, ax = plt.subplots(figsize=(12, height))
    fig.subplots_adjust(left=left, right=right, top=1 - top_in / height, bottom=bottom_in / height)
    fig.text(0.012, 1 - 0.3 / height, title, ha="left", va="top", fontsize=16, fontweight="bold", color=INK)
    fig.text(0.012, 1 - 0.72 / height, subtitle, ha="left", va="top", fontsize=11, color=INK_2)
    return fig, ax


def _save(fig, path):
    fig.text(0.012, 0.012, CAPTION, color=MUTED, fontsize=8.5, ha="left", va="bottom")
    fig.savefig(path, dpi=200)
    plt.close(fig)


def _ferry_dot(ax, x, y):
    ax.plot(x, y, "o", markersize=13, markerfacecolor="none", markeredgecolor=FERRY, markeredgewidth=2.2, zorder=3)


def _speedboat_dot(ax, x, y):
    ax.plot(x, y, "o", markersize=8, color=SPEEDBOAT, markeredgecolor=SURFACE, markeredgewidth=1.5, zorder=4)


def _dot_legend(ax, ferry_label=FERRY_LABEL, speedboat_label=SPEEDBOAT_LABEL):
    handles = [plt.Line2D([], [], marker="o", linestyle="", markersize=12, markerfacecolor="none",
                          markeredgecolor=FERRY, markeredgewidth=2.2),
               plt.Line2D([], [], marker="o", linestyle="", markersize=8, color=SPEEDBOAT)]
    ax.legend(handles, [ferry_label, speedboat_label], loc="lower left", bbox_to_anchor=(0, 1.0),
              ncol=2, fontsize=10.5, handletextpad=0.3, columnspacing=1.6, borderaxespad=0.3)


def within_vs_hdx(base, observed, islands, hdx, cfg, path):
    """Population within 30-240 min of any hospital (daytime median) next to HDX car-only."""
    fig = plt.figure(figsize=(12, 6))
    axes = fig.subplots(1, 2, sharey=True)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.72, bottom=0.16, wspace=0.08)
    fig.text(0.012, 0.95, "Real boats put far fewer people near a hospital than the car-only estimate",
             ha="left", va="top", fontsize=16, fontweight="bold", color=INK)
    fig.text(0.012, 0.88, "Share of people within each travel time of the nearest hospital (any level), "
                          "daytime median, against HDX", ha="left", va="top", fontsize=11, color=INK_2)
    rows = {}
    for name, results in ((FERRY_LABEL, base), (SPEEDBOAT_LABEL, observed)):
        w = indicators.population_within(results, islands, cfg, "any_hospital")
        rows[name] = w.pivot_table(index="threshold_min", columns="area", values="share_pct")
    theirs = hdx.pivot_table(index="threshold_min", columns="area", values="share_pct")
    thresholds = list(cfg.THRESHOLDS_MIN)
    x = np.arange(len(thresholds))
    width = 0.26
    for ax, (area, hdx_area, title) in zip(axes, (("Kaafu", "Kaafu", "Kaafu (9 islands, 17,749 people)"),
                                                 ("All 23", "Maldives", "All 23 islands (31,414 people; "
                                                                        "HDX: whole Maldives)"))):
        series = [(HDX, theirs[hdx_area].reindex(thresholds)),
                  (FERRY, rows[FERRY_LABEL][area].reindex(thresholds)),
                  (SPEEDBOAT, rows[SPEEDBOAT_LABEL][area].reindex(thresholds))]
        for k, (colour, values) in enumerate(series):
            pos = x + (k - 1) * width
            ax.bar(pos, values.fillna(0), width=width - 0.03, color=colour, zorder=3)
            for p, v, t in zip(pos, values, thresholds):
                if np.isnan(v):
                    ax.text(p, 1, "n/a", ha="center", va="bottom", fontsize=8.5, color=MUTED)
                elif t == 120:
                    ax.text(p, v + 1.5, f"{v:.0f}%", ha="center", va="bottom", fontsize=10, color=INK)
        ax.set_xticks(x, ["30 min", "1 h", "1.5 h", "2 h", "4 h"][:len(thresholds)])
        ax.set_title(title, fontsize=11.5, color=INK_2, loc="left")
        ax.set_ylim(0, 100)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("Share of population within")
    axes[0].yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(decimals=0))
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (HDX, FERRY, SPEEDBOAT)]
    fig.legend(handles, ["HDX car-only estimate (no 4 h value)", FERRY_LABEL, SPEEDBOAT_LABEL],
               loc="upper left", bbox_to_anchor=(0.06, 0.83), ncol=3, fontsize=10.5)
    _save(fig, path)


def within_2h_through_day(base, observed, islands, hdx, cfg, path):
    """Share of Kaafu within 2 h of a Greater Malé hospital by departure time."""
    fig, ax = _figure(6, "Within 2 hours of a Malé hospital depends on when you leave",
                      "Share of Kaafu's 17,749 people who reach a Greater Malé hospital within 2 h, "
                      "by departure time", left=0.08, right=0.97)
    deps = list(range(0, cfg.MINUTES_PER_DAY, cfg.STEP_MIN))
    hours = np.array(deps) / 60
    for colour, label, results, nudge in ((FERRY, FERRY_LABEL, base, (-8, 6)),
                                          (SPEEDBOAT, SPEEDBOAT_LABEL, observed, (8, 6))):
        share = [indicators.population_within(results, islands, cfg, "gm_hospital", d)
                 .query("area == 'Kaafu' and threshold_min == 120")["share_pct"].iloc[0] for d in deps]
        ax.plot(hours, share, color=colour, linewidth=2, solid_joinstyle="round", solid_capstyle="round",
                label=label, zorder=3)
        peak = int(np.argmax(share))
        ax.annotate(f"{share[peak]:.0f}% leaving at {indicators.hhmm(deps[peak])}", (hours[peak], share[peak]),
                    xytext=nudge, textcoords="offset points", ha="right" if nudge[0] < 0 else "left",
                    fontsize=10, color=INK)
    hdx_2h = hdx.query("area == 'Kaafu' and threshold_min == 120")["share_pct"].iloc[0]
    ax.axhline(hdx_2h, color=HDX, linewidth=1.5, zorder=2)
    ax.text(23.9, hdx_2h + 1.5, f"HDX car-only estimate: {hdx_2h:.1f}%", ha="right", fontsize=10, color=INK_2)
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3), [f"{h:02d}:00" for h in range(0, 25, 3)])
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(decimals=0))
    ax.set_xlabel("Leaving home at")
    ax.set_ylabel("Kaafu population within 2 h")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, fontsize=10.5, borderaxespad=0.3)
    _save(fig, path)


def _dumbbell(ax, order, ferry, speedboat, xmax, fmt):
    """One row per island: ferries-only ring and with-speedboats dot joined by a hairline.
    Missing values go in an "unreachable today" column past the axis end."""
    unreachable = xmax * UNREACHABLE_X
    y = np.arange(len(order))[::-1]
    for yi, island in zip(y, order):
        a, b = ferry.get(island, np.nan), speedboat.get(island, np.nan)
        a_x, b_x = (unreachable if np.isnan(a) else a), (unreachable if np.isnan(b) else b)
        if abs(a_x - b_x) > 0.05:
            ax.plot([a_x, b_x], [yi, yi], color=AXIS, linewidth=1.5, zorder=2)
        _ferry_dot(ax, a_x, yi)
        _speedboat_dot(ax, b_x, yi)
        if not np.isnan(b) and b_x < a_x - 0.05:
            ax.text(b, yi + 0.3, fmt(b), ha="center", va="bottom", fontsize=8.5, color=INK)
    ax.axvspan(xmax * 1.03, xmax * 1.17, color=GRID, alpha=0.35, zorder=1, linewidth=0)
    ax.set_xlim(0, xmax * 1.17)
    ax.set_yticks(y, order)
    ax.set_ylim(-0.7, len(order) - 0.3)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    ax.spines["bottom"].set_bounds(0, xmax)


def _summary_values(summary, column, to_number):
    return summary.set_index("origin_key")[column].map(to_number).astype(float)


def worst_served(base_summary, obs_summary, path):
    """Daytime median door-to-door hours per island, worst first."""
    hours = lambda v: np.nan if pd.isna(v) else v / 60  # noqa: E731
    ferry = _summary_values(base_summary, "day_median_min", hours)
    speedboat = _summary_values(obs_summary, "day_median_min", hours)
    worst = lambda s, k: np.inf if np.isnan(s[k]) else s[k]  # noqa: E731
    order = sorted(ferry.index, key=lambda k: (-worst(ferry, k), -worst(speedboat, k)))
    fig, ax = _figure(9, "Worst-served islands: most can't reach a Malé hospital the same day",
                      "Typical door-to-door time from each island to a Greater Malé hospital, worst first",
                      bottom_in=1.2)
    _dumbbell(ax, order, ferry, speedboat, 30, lambda h: f"{h:.1f} h")
    ticks = list(range(0, 31, 6))
    ax.set_xticks(ticks + [30 * UNREACHABLE_X], [f"{h} h" for h in ticks] + ["unreachable\ntoday"])
    ax.set_xlabel("Daytime median, door to door (departures 06:00-18:00)")
    _dot_legend(ax)
    _save(fig, path)


def last_departures(base_summary, obs_summary, path):
    """Latest departure that still reaches a Greater Malé hospital before midnight."""
    clock = lambda v: np.nan if v == "none" else indicators.minutes_of(v) / 60  # noqa: E731
    ferry = _summary_values(base_summary, "last_practical_departure", clock)
    speedboat = _summary_values(obs_summary, "last_practical_departure", clock)
    earliest = lambda s, k: -1 if np.isnan(s[k]) else s[k]  # noqa: E731
    order = sorted(ferry.index, key=lambda k: (earliest(ferry, k), earliest(speedboat, k)))
    fig, ax = _figure(9, "Miss the morning boat and the hospital is out of reach until tomorrow",
                      "Latest time to leave home on a Wednesday and still reach a Greater Malé hospital "
                      "before midnight, earliest first", bottom_in=1.2)
    _dumbbell(ax, order, ferry, speedboat, 24, lambda h: indicators.hhmm(round(h * 60)))
    ax.set_xticks(list(range(0, 25, 3)) + [24 * UNREACHABLE_X],
                  [f"{h:02d}:00" for h in range(0, 25, 3)] + ["no boat\non Wednesday"])
    ax.set_xlabel("Last practical departure")
    _dot_legend(ax)
    _save(fig, path)


def scheduled_against_observed(both, path):
    """Scheduled boat minutes to Greater Malé against the observed median of tracked trips."""
    both = both.dropna().sort_values("scheduled_min", ascending=False)
    fig, ax = _figure(8, "The boats people actually take are much faster than the timetable",
                      "Boat time to Greater Malé: quickest scheduled public ferry against the median "
                      "of tracked boats (islands with at least 5 tracked trips)")
    y = np.arange(len(both))[::-1]
    for yi, (island, r) in zip(y, both.iterrows()):
        ax.plot([r.observed_min, r.scheduled_min], [yi, yi], color=AXIS, linewidth=1.5, zorder=2)
        _ferry_dot(ax, r.scheduled_min, yi)
        _speedboat_dot(ax, r.observed_min, yi)
        ax.text(r.scheduled_min + 9, yi, f"−{r.scheduled_min - r.observed_min:.0f} min",
                va="center", fontsize=8.5, color=INK_2)
    ax.set_xlim(0, both["scheduled_min"].max() * 1.1)
    ax.set_yticks(y, both.index)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Boat minutes from the island to Greater Malé")
    _dot_legend(ax, "Scheduled public ferry (quickest)", "Observed median of tracked boats (FollowMe, Aug 2025)")
    _save(fig, path)


def best_change(table, path):
    """The best extra evening run of each CFN route, by people-hours saved."""
    t = (table[table["pop_minutes_saved"] > 0].sort_values("pop_minutes_saved", ascending=False)
         .drop_duplicates("route_id").iloc[::-1])
    labels = [f"Route {r.route_id} at {r.run_time}" for r in t.itertuples()]
    fig, ax = _figure(5.5, "One extra evening ferry: where it helps most",
                      "Best added run of each CFN route (18:00, 20:00 or 22:00), public ferries only, "
                      "ranked by people-hours saved across the day")
    people_hours = t["pop_minutes_saved"] / 60 / 1000
    ax.barh(labels, people_hours, height=0.5, color=FERRY, zorder=3)
    for yi, (v, r) in enumerate(zip(people_hours, t.itertuples())):
        ax.text(v + people_hours.max() * 0.01, yi,
                f"{v:.1f}k people-hours · {r.people_helped:,} people, {r.avg_min_saved_per_person / 60:.1f} h each · "
                f"{r.islands_helped.replace(' ', ', ')}", va="center", fontsize=9, color=INK_2)
    ax.set_xlim(0, people_hours.max() * 1.9)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("People-hours saved (thousands), averaged over every departure time of the day")
    _save(fig, path)


def slide_numbers(base, observed, base_summary, obs_summary, islands, hdx, nsds, both, best, cfg):
    """Markdown with the headline numbers for slides 5-6."""
    def share(results, area, threshold, target):
        w = indicators.population_within(results, islands, cfg, target)
        return w.query("area == @area and threshold_min == @threshold")["share_pct"].iloc[0]

    hdx_k = hdx.query("area == 'Kaafu' and threshold_min == 120")["share_pct"].iloc[0]
    hdx_m = hdx.query("area == 'Maldives' and threshold_min == 120")["share_pct"].iloc[0]
    lines = [
        "# M3 slide numbers (generated by `python -m kaafu.m3_figures`)", "",
        "Every number: Wednesday CFN timetable, Malé jetty assumed Jetty NO5, daytime median "
        "(departures 06:00-18:00) unless stated. \"With speedboats\" = observed FollowMe boat "
        "movements, Aug 2025, not a published schedule.", "",
        "## Within 2 h of a hospital", "",
        "| | HDX car-only | Public ferries only | With observed speedboats |", "|---|---|---|---|",
        f"| Kaafu, nearest hospital | {hdx_k:.1f}% | {share(base, 'Kaafu', 120, 'any_hospital'):.1f}% "
        f"| {share(observed, 'Kaafu', 120, 'any_hospital'):.1f}% |",
        f"| All 23 islands, any hospital (HDX: Maldives) | {hdx_m:.1f}% "
        f"| {share(base, 'All 23', 120, 'any_hospital'):.1f}% | {share(observed, 'All 23', 120, 'any_hospital'):.1f}% |",
        f"| All 23 islands, Greater Malé hospital | | {share(base, 'All 23', 120, 'gm_hospital'):.1f}% "
        f"| {share(observed, 'All 23', 120, 'gm_hospital'):.1f}% |", "",
        "## Worst served (Greater Malé hospital)", "",
        "| Island | People | Daytime median, ferries | With speedboats | Last practical departure, ferries "
        "| With speedboats |", "|---|---|---|---|---|---|",
    ]
    s = base_summary.merge(obs_summary, on="origin_key", suffixes=("", "_obs")).set_index("origin_key")
    s["sort"] = s["last_practical_departure"].map(lambda v: -1 if v == "none" else indicators.minutes_of(v))
    for island, r in s.sort_values("sort").iterrows():
        def med(v):
            return "unreachable today" if pd.isna(v) else f"{v / 60:.1f} h"
        lines.append(f"| {island} | {r.population:,} | {med(r.day_median_min)} | {med(r.day_median_min_obs)} "
                     f"| {r.last_practical_departure} | {r.last_practical_departure_obs} |")
    lines += ["", "## Scheduled against observed boat time to Greater Malé", "",
              "| Island | Scheduled ferry (quickest) | Observed median | Tracked trips |", "|---|---|---|---|"]
    for island, r in both.dropna().sort_values("scheduled_min", ascending=False).iterrows():
        lines.append(f"| {island} | {r.scheduled_min:.0f} min | {r.observed_min:.0f} min | {int(r.observed_trips)} |")
    lines += ["", "## Best extra evening ferry (public ferries only, best run per route)", "",
              "| Run | People helped | Avg saved per person | Islands |", "|---|---|---|---|"]
    top = best[best["pop_minutes_saved"] > 0].sort_values("pop_minutes_saved", ascending=False)
    for r in top.drop_duplicates("route_id").itertuples():
        lines.append(f"| Route {r.route_id} at {r.run_time} | {r.people_helped:,} "
                     f"| {r.avg_min_saved_per_person / 60:.1f} h | {r.islands_helped} |")
    lines += ["", "No extra run brings an island newly within 2 h by ferry.", "",
              "## NSDS-style indicators (public ferries only)", "",
              "| Indicator | Kaafu | All 23 | Definition |", "|---|---|---|---|"]
    for ind, g in nsds.groupby("indicator", sort=False):
        k, a = g.set_index("area")["share_pct"]["Kaafu"], g.set_index("area")["share_pct"]["All 23"]
        lines.append(f"| {ind} | {k:.1f}% | {a:.1f}% | {g['definition'].iloc[0]} |")
    return "\n".join(lines) + "\n"


def main(cfg=None):
    if cfg is None:
        from kaafu import config as cfg
    data = scenarios._inputs(cfg)
    base, base_summary = scenarios.run_scenario({}, cfg)
    observed, obs_summary = scenarios.run_scenario({"observed": True}, cfg)
    islands = data["islands"]
    hdx = pd.read_csv(cfg.HDX_BENCHMARK_CSV, encoding=cfg.READ_ENCODING)
    nsds = pd.read_csv(cfg.PROCESSED / indicators.NSDS_FIGURES_CSV, encoding=cfg.READ_ENCODING)
    best = pd.read_csv(cfg.PROCESSED / scenarios.BEST_FERRY_CHANGE_CSV, encoding=cfg.READ_ENCODING,
                       dtype={"route_id": str}).fillna({"islands_helped": ""})
    both = indicators.scheduled_vs_observed(data["conns"], data["observed_trips"], data["stop_island"], cfg)

    out = cfg.FIGURES
    out.mkdir(parents=True, exist_ok=True)
    within_vs_hdx(base, observed, islands, hdx, cfg, out / "m3_within_vs_hdx.png")
    within_2h_through_day(base, observed, islands, hdx, cfg, out / "m3_within_2h_through_day.png")
    worst_served(base_summary, obs_summary, out / "m3_worst_served.png")
    last_departures(base_summary, obs_summary, out / "m3_last_departure.png")
    scheduled_against_observed(both, out / "m3_scheduled_vs_observed.png")
    best_change(best, out / "m3_best_ferry_change.png")
    (out / "m3_slide_numbers.md").write_text(
        slide_numbers(base, observed, base_summary, obs_summary, islands, hdx, nsds, both, best, cfg),
        encoding=cfg.WRITE_ENCODING)


if __name__ == "__main__":
    main()
