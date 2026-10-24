"""Avas taxi requests to an hourly table by pickup zone (BUILD_PLAN 6.5).

Reads data/raw/avas/avas_rides_aug_sep_2026.csv and writes
data/processed/avas_hourly.csv: one row per zone x hour (0-23) with completed
and expired requests, the unserved share, and the median speed of completed
rides. Zones are the pickup boxes in config.AVAS_ZONES, plus "all".

With config.AVAS_SPEED_SAME_ZONE, the speed comes only from rides that start
and end in the same zone. Most rides cross the Malé-Hulhumalé bridge, so all
rides give ~39 km/h, too fast for the short hops where lastmile.py needs it.

Run `python -m kaafu.avas` (add `--plot PATH` for a pickup scatter with the boxes).
"""
import argparse

import pandas as pd

HOURLY_COLUMNS = ["zone", "hour", "completed", "expired", "expired_share", "median_speed_kmh"]
COMPLETED = {"payment_completed", "ride_completed"}
EXPIRED = {"ride_expired"}
HOURS = range(24)


def load_rides(path, weekdays):
    """Requests on the build's day group (Sun-Thu), with hour, outcome and speed."""
    rides = pd.read_csv(path, parse_dates=["date_started"])
    unknown = sorted(set(rides["status"]) - COMPLETED - EXPIRED)
    if unknown:
        raise ValueError(f"unknown Avas status values: {unknown}")
    rides = rides[rides["date_started"].dt.day_of_week.isin(weekdays)].copy()
    rides["hour"] = rides["date_started"].dt.hour
    rides["completed"] = rides["status"].isin(COMPLETED)
    rides["kmh"] = rides["distance_km"] / (rides["time_sec"] / 3600)
    return rides


def assign_zones(lat, lng, zones):
    """The first box (in config order) that contains each point; NA if none.

    Order matters where boxes touch: airport is checked before hulhumale.
    """
    zone = pd.Series(pd.NA, index=lat.index, dtype="object")
    for name, (lat_min, lat_max, lon_min, lon_max) in zones.items():
        inside = zone.isna() & lat.between(lat_min, lat_max) & lng.between(lon_min, lon_max)
        zone[inside] = name
    return zone


def _counts(rides):
    """Completed, expired and unserved share for hours 0-23."""
    counts = (rides.groupby(["hour", "completed"]).size()
              .unstack(fill_value=0).reindex(index=HOURS, columns=[True, False], fill_value=0))
    table = pd.DataFrame({"completed": counts[True], "expired": counts[False]})
    table["expired_share"] = table["expired"] / (table["completed"] + table["expired"])
    return table.rename_axis("hour")


def _speeds(rides, min_rides):
    """Median speed by hour, and where it came from.

    "hour" if that hour has at least `min_rides` rides, else "day" (the
    all-day median) if the rides as a whole do, else NA.
    """
    by_hour = rides.groupby("hour")["kmh"].agg(["size", "median"]).reindex(HOURS)
    enough = by_hour["size"] >= min_rides
    speed = by_hour["median"].where(enough)
    source = pd.Series("hour", index=by_hour.index).where(enough)
    if len(rides) >= min_rides:
        source = source.fillna("day")
        speed = speed.fillna(rides["kmh"].median())
    return speed, source


def hourly_table(rides, zone_names, min_rides, same_zone=True):
    """One row per zone x hour, "all" included.

    Counts use every request. Speed uses completed rides (same-zone only if
    `same_zone`): an hour with fewer than `min_rides` takes that zone's
    all-day median, and a zone with too few rides all day takes "all". A
    zone-hour with no requests takes the "all" unserved share. Returns the
    table and the speed source for every zone-hour.
    """
    speed_rides = rides[rides["completed"]]
    if same_zone:
        speed_rides = speed_rides[speed_rides["zone"] == speed_rides["drop_zone"]]

    every = _counts(rides)
    every["median_speed_kmh"], every_source = _speeds(speed_rides, min_rides)
    tables = [every.assign(zone="all")]
    sources = {"all": every_source}
    for name in zone_names:
        table = _counts(rides[rides["zone"] == name])
        speed, source = _speeds(speed_rides[speed_rides["zone"] == name], min_rides)
        missing = speed.isna()
        speed[missing] = every.loc[missing, "median_speed_kmh"]
        source[missing] = "all"
        table["median_speed_kmh"] = speed
        empty = table["expired_share"].isna()
        table.loc[empty, "expired_share"] = every.loc[empty, "expired_share"]
        source[empty] = source[empty] + ", share from all"
        tables.insert(-1, table.assign(zone=name))
        sources[name] = source

    hourly = pd.concat(tables).reset_index()[HOURLY_COLUMNS]
    hourly["expired_share"] = hourly["expired_share"].round(4)
    hourly["median_speed_kmh"] = hourly["median_speed_kmh"].round(1)
    return hourly, pd.DataFrame(sources)


def check_hourly(hourly, zone_names):
    """96 rows (4 zones x 24 hours), no blanks."""
    expected = len(zone_names) + 1
    if len(hourly) != expected * 24:
        raise ValueError(f"expected {expected * 24} rows, got {len(hourly)}")
    if hourly.isna().any().any():
        raise ValueError(f"blanks in avas_hourly:\n{hourly[hourly.isna().any(axis=1)]}")


def summary(rides, hourly, sources, dropped, min_rides):
    """The Step 1 'done when' checks and the slide-5 numbers, as text."""
    lines = [f"rides Sun-Thu: {len(rides) + dropped:,}; outside every zone box (dropped): "
             f"{dropped:,} ({dropped / (len(rides) + dropped):.2%})",
             f"rides by pickup zone: {rides['zone'].value_counts().to_dict()}"]

    unserved = (~rides["completed"]).mean()
    lines.append(f"overall unserved share (all zones): {unserved:.3f}")
    every = hourly[hourly["zone"] == "all"].set_index("hour")
    peaks = every["expired_share"].nlargest(4)
    lines.append("highest unserved hours (all): "
                 + ", ".join(f"{h:02d}:00 {s:.3f}" for h, s in peaks.items()))
    airport = hourly[(hourly["zone"] == "airport") & (hourly["hour"] == 23)].iloc[0]
    lines.append(f"airport 23:00 unserved: {airport.expired_share:.3f} "
                 f"({airport.expired} of {airport.completed + airport.expired})")

    zones = hourly[hourly["zone"] != "all"]
    real = zones[zones["completed"] + zones["expired"] >= min_rides]
    worst = real.loc[real["expired_share"].idxmax()]
    lines.append(f"worst zone-hour (>= {min_rides} requests): {worst.zone} {worst.hour:02d}:00 "
                 f"{worst.expired_share:.3f}")

    same = rides[rides["completed"] & (rides["zone"] == rides["drop_zone"])]
    lines.append(f"same-zone completed rides: {same['zone'].value_counts().to_dict()}")
    speeds = hourly.groupby("zone")["median_speed_kmh"].agg(["min", "median", "max"])
    lines.append("median speed km/h by zone (min / median / max over hours):")
    lines += [f"  {z:<10} {r['min']:5.1f} {r['median']:5.1f} {r['max']:5.1f}" for z, r in speeds.iterrows()]
    lines.append("speed source by zone (hour = that hour's rides, day = zone's all-day median):")
    lines += [f"  {z:<10} {sources[z].value_counts().to_dict()}" for z in sources]
    return "\n".join(lines)


def plot_zones(rides, zones, path, sample=30_000):
    """Pickup scatter with the zone boxes, to check them by eye (not committed)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    points = rides.sample(min(sample, len(rides)), random_state=0)
    fig, ax = plt.subplots(figsize=(8, 9))
    ax.scatter(points["pickup_lng"], points["pickup_lat"], s=1, alpha=0.3, color="0.3")
    for (name, (lat_min, lat_max, lon_min, lon_max)), colour in zip(
            zones.items(), ["tab:blue", "tab:red", "tab:green"]):
        ax.add_patch(Rectangle((lon_min, lat_min), lon_max - lon_min, lat_max - lat_min,
                               fill=False, edgecolor=colour, linewidth=1.5, label=name))
    ax.set_xlim(73.48, 73.57)
    ax.set_ylim(4.15, 4.26)
    ax.set_aspect("equal")
    ax.legend(loc="upper left")
    ax.set_title("Avas pickups (sample) and zone boxes")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main(cfg=None, plot_path=None):
    """Avas requests -> data/processed/avas_hourly.csv (zone x hour: unserved share, median speed).

    Steps: load Sun-Thu requests, assign pickup and dropoff zones, build the
    hourly table with fallbacks for thin zone-hours, check it, write it.
    """
    if cfg is None:
        from kaafu import config as cfg
    rides = load_rides(cfg.AVAS_RIDES_CSV, cfg.AVAS_WEEKDAYS)
    if plot_path:
        plot_zones(rides, cfg.AVAS_ZONES, plot_path)

    rides["zone"] = assign_zones(rides["pickup_lat"], rides["pickup_lng"], cfg.AVAS_ZONES)
    rides["drop_zone"] = assign_zones(rides["dropoff_lat"], rides["dropoff_lng"],
                                      cfg.AVAS_ZONES).fillna("none")
    dropped = int(rides["zone"].isna().sum())
    rides = rides[rides["zone"].notna()]

    zone_names = list(cfg.AVAS_ZONES)
    hourly, sources = hourly_table(rides, zone_names, cfg.AVAS_MIN_RIDES, cfg.AVAS_SPEED_SAME_ZONE)
    check_hourly(hourly, zone_names)
    cfg.AVAS_HOURLY_CSV.parent.mkdir(parents=True, exist_ok=True)
    hourly.to_csv(cfg.AVAS_HOURLY_CSV, index=False, encoding=cfg.WRITE_ENCODING)

    print(summary(rides, hourly, sources, dropped, cfg.AVAS_MIN_RIDES))
    print(f"wrote {cfg.AVAS_HOURLY_CSV.relative_to(cfg.ROOT)} ({len(hourly)} rows)")
    return hourly


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plot", help="save a pickup scatter with the zone boxes to this PNG")
    main(plot_path=parser.parse_args().plot)
