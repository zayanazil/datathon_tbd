"""Last mile in Greater Malé: from stepping off the boat to the hospital door (M1).

One row per stop x hospital x hour (0-23) x mode (walk, bus, taxi), following
BUILD_PLAN 6.3 and docs/members/M1_gis.md step 3. Stops are the four ferry
terminals (to the Greater Malé hospitals) plus the three islands with their own
atoll hospital (walk only). Modes that can't run are kept with available = no
and the reason in `detail`.

Run `python -m kaafu.lastmile` to write data/processed/last_mile.csv.
"""

import numpy as np
import pandas as pd

from kaafu import config, geo

COLUMNS = ["stop_id", "facility_id", "hour", "mode", "minutes", "available", "detail"]
HOURS = range(24)
COMPLETED = ("ride_completed", "payment_completed")


def haversine_m(lat1, lon1, lat2, lon2):
    """Straight-line distance in metres; works on scalars or arrays."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6_371_000 * np.arcsin(np.sqrt(a))


def walk_min(metres: float) -> float:
    return metres / config.WALK_M_PER_MIN


def load_hospitals() -> pd.DataFrame:
    fac = pd.read_csv(config.FACILITIES_CSV, encoding=config.READ_ENCODING)
    ids = list(config.GM_HOSPITALS) + list(config.ATOLL_HOSPITALS.values())
    if not config.INCLUDE_SENAHIYA:
        ids.remove(config.SENAHIYA_ID)
    return fac[fac.facility_id.isin(ids)].set_index("facility_id")


# ---------------------------------------------------------------------------
# Walk
# ---------------------------------------------------------------------------
def walk_option(terminal, hospital) -> dict:
    if terminal.island_key != hospital.island_key:
        return {"available": "no", "detail": "different island"}
    metres = haversine_m(terminal.lat, terminal.lon, hospital.lat, hospital.lon)
    return {"available": "yes", "minutes": config.TERMINAL_EXIT_MIN + walk_min(metres),
            "detail": f"walk {metres / 1000:.1f} km"}


# ---------------------------------------------------------------------------
# Bus
# ---------------------------------------------------------------------------
def to_min(hhmm: str) -> int:
    h, m = str(hhmm).split(":")[:2]
    return int(h) * 60 + int(m)


class BusNetwork:
    """Greater Malé bus routes: stops in order, service hours, headways, ride times."""

    def __init__(self):
        hours = pd.read_csv(config.BUS_SERVICE_HOURS_CSV, encoding=config.READ_ENCODING)
        self.hours = hours[hours.day_type == config.BUS_DAY_TYPE].set_index("route_number")
        bands = pd.read_csv(config.BUS_HEADWAYS_CSV, encoding=config.READ_ENCODING)
        self.bands = bands[bands.day_type == config.BUS_DAY_TYPE]

        stops = pd.read_csv(config.RTL_BUS_STOPS_CSV, encoding=config.READ_ENCODING)
        self.stops = stops[stops.route_number.isin(self.hours.index)].sort_values(
            ["route_number", "order"])

        deps = pd.read_csv(config.RTL_BUS_DEPARTURES_CSV, encoding=config.READ_ENCODING)
        deps = deps[deps.route_number.isin(self.hours.index)].copy()
        deps["minute"] = deps.time.map(to_min)
        self.departures = deps

    def candidates(self, route: str, terminal, hospital):
        """Best (board, alight) stop pair on one route, or None.

        Board within BUS_STOP_RADIUS_M of the terminal, alight within it of the
        hospital, at a later stop in the route's order.
        """
        stops = self.stops[self.stops.route_number == route]
        d_board = haversine_m(terminal.lat, terminal.lon, stops.lat.values, stops.lon.values)
        d_alight = haversine_m(hospital.lat, hospital.lon, stops.lat.values, stops.lon.values)
        best = None
        for i in np.flatnonzero(d_board <= config.BUS_STOP_RADIUS_M):
            for j in np.flatnonzero(d_alight <= config.BUS_STOP_RADIUS_M):
                if stops.order.iat[j] <= stops.order.iat[i]:
                    continue
                ride, estimated = self.ride_minutes(route, stops, i, j)
                walk = walk_min(d_board[i]) + walk_min(d_alight[j])
                if best is None or walk + ride < best["walk"] + best["ride"]:
                    best = {"board": stops.iloc[i], "alight": stops.iloc[j],
                            "walk": walk, "ride": ride, "estimated": estimated}
        return best

    def ride_minutes(self, route, stops, i, j):
        """Median timetabled gap between two stops on the same trip.

        Falls back to distance along the route at MINIBUS_SPEED_KMH where the
        departures file has no trips (minibuses) or no trip serves both stops.
        """
        board, alight = stops.stop.iat[i], stops.stop.iat[j]
        deps = self.departures[self.departures.route_number == route]
        gaps = []
        for _, trip in deps.groupby("trip"):
            # Minutes since the trip's first listed time, so trips that cross
            # midnight still go forward.
            rel = (trip.minute - trip.minute.min()) % config.MINUTES_PER_DAY
            t_board = rel[trip.stop == board]
            if t_board.empty:
                continue
            after = rel[(trip.stop == alight) & (rel > t_board.min())]
            if not after.empty:
                gaps.append(after.min() - t_board.min())
        if gaps:
            return float(np.median(gaps)), False

        seg = stops.iloc[i:j + 1]
        metres = haversine_m(seg.lat.values[:-1], seg.lon.values[:-1],
                             seg.lat.values[1:], seg.lon.values[1:]).sum()
        return metres / 1000 / config.MINIBUS_SPEED_KMH * 60, True

    def wait_at(self, route: str, hour: int):
        """Wait in minutes for a bus at the start of `hour`, or None if not running.

        Service runs first_min..last_min (last_min can pass 1440, e.g. 1470 =
        00:30), so early hours are also tried as next-day minutes.
        """
        first, last = self.hours.loc[route, ["first_min", "last_min"]]
        for t in (hour * 60, hour * 60 + config.MINUTES_PER_DAY):
            if first <= t <= last:
                band = self.bands[(self.bands.route_number == route)
                                  & (self.bands.start_min <= t) & (self.bands.end_min >= t)]
                if not band.empty:
                    return float(band.wait_min.iloc[0])
                # No band covers t: half the average gap over the service day.
                trips = self.hours.loc[route, "trips_per_day"]
                return (last - first) / trips / 2
        return None


def bus_routes(bus: BusNetwork, terminal, hospital) -> list[dict]:
    """Every route that can carry someone from this terminal to this hospital."""
    if config.ROAD_NETWORK.get(terminal.island_key) != config.ROAD_NETWORK.get(hospital.island_key):
        return []
    found = []
    for route in bus.hours.index:
        best = bus.candidates(route, terminal, hospital)
        if best is not None:
            found.append({"route": route, **best})
    return found


def bus_option(bus: BusNetwork, routes: list[dict], hour: int) -> dict:
    if not routes:
        return {"available": "no", "detail": "no route links terminal and hospital"}
    best = None
    for r in routes:
        wait = bus.wait_at(r["route"], hour)
        if wait is None:
            continue
        minutes = config.TERMINAL_EXIT_MIN + r["walk"] + wait + r["ride"]
        if best is None or minutes < best["minutes"]:
            est = ", estimated" if r["estimated"] else ""
            detail = (f"{r['route']} from {r['board'].stop} to {r['alight'].stop}, "
                      f"wait {wait:g}, ride {r['ride']:.0f}{est}, walk {r['walk']:.0f}")
            best = {"available": "yes", "minutes": minutes, "detail": detail}
    return best or {"available": "no", "detail": "outside service hours"}


# ---------------------------------------------------------------------------
# Taxi
# ---------------------------------------------------------------------------
def load_taxi_hourly() -> tuple[pd.DataFrame, bool]:
    """M2's avas_hourly.csv by (zone, hour), or a flagged placeholder."""
    if config.AVAS_HOURLY_CSV.exists():
        hourly = pd.read_csv(config.AVAS_HOURLY_CSV, encoding=config.READ_ENCODING)
        return hourly.set_index(["zone", "hour"]), False
    zones = sorted(set(config.TAXI_ZONE.values()))
    index = pd.MultiIndex.from_product([zones, HOURS], names=["zone", "hour"])
    placeholder = pd.DataFrame({"expired_share": config.TAXI_PLACEHOLDER_EXPIRED,
                                "median_speed_kmh": config.TAXI_PLACEHOLDER_KMH}, index=index)
    return placeholder, True


def load_avas_rides() -> pd.DataFrame:
    """Completed Avas rides: pickup, dropoff, hour, drive time in minutes."""
    import duckdb

    if not config.AVAS_RIDES_CSV.exists():
        return pd.DataFrame(columns=["pickup_lat", "pickup_lng", "dropoff_lat",
                                     "dropoff_lng", "hour", "drive_min"])
    return duckdb.sql(f"""
        select pickup_lat, pickup_lng, dropoff_lat, dropoff_lng,
               hour(date_started) as hour, time_sec / 60.0 as drive_min
        from read_csv_auto('{config.AVAS_RIDES_CSV.as_posix()}')
        where status in {COMPLETED}
    """).df()


def observed_drives(rides: pd.DataFrame, terminal, hospital) -> pd.DataFrame:
    """Avas rides from near the terminal to near the hospital, by hour."""
    near_start = haversine_m(terminal.lat, terminal.lon, rides.pickup_lat.values,
                             rides.pickup_lng.values) <= config.TAXI_MATCH_RADIUS_M
    near_end = haversine_m(hospital.lat, hospital.lon, rides.dropoff_lat.values,
                           rides.dropoff_lng.values) <= config.TAXI_MATCH_RADIUS_M
    matched = rides[near_start & near_end]
    return matched.groupby("hour").drive_min.agg(["size", "median"])


def taxi_option(terminal, hospital, hour, hourly, placeholder, drives) -> dict:
    zone = config.TAXI_ZONE.get(terminal.island_key)
    if zone is None:
        return {"available": "no", "detail": "no taxis from this terminal"}
    if config.ROAD_NETWORK.get(terminal.island_key) != config.ROAD_NETWORK.get(hospital.island_key):
        return {"available": "no", "detail": "no road link"}

    row = hourly.loc[(zone, hour)]
    flag = ", placeholder speed and wait" if placeholder else ""
    if hour in drives.index and drives.loc[hour, "size"] >= config.TAXI_MIN_RIDES:
        drive = drives.loc[hour, "median"]
        how = f"Avas median of {int(drives.loc[hour, 'size'])} rides"
    else:
        km = haversine_m(terminal.lat, terminal.lon, hospital.lat, hospital.lon) / 1000
        drive = km * config.TAXI_DETOUR / row.median_speed_kmh * 60
        how = f"{km * config.TAXI_DETOUR:.1f} km at {row.median_speed_kmh:.0f} km/h"
    wait = config.TAXI_BASE_WAIT_MIN + row.expired_share * config.TAXI_RETRY_MIN
    return {"available": "yes", "minutes": config.TERMINAL_EXIT_MIN + wait + drive,
            "detail": f"taxi, {how}, wait {wait:.1f}{flag}"}


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------
def build_last_mile() -> pd.DataFrame:
    terminals = geo.build_terminals()
    hospitals = load_hospitals()
    bus = BusNetwork()
    hourly, placeholder = load_taxi_hourly()
    rides = load_avas_rides()

    rows = []
    gm = hospitals[hospitals.index.isin(config.GM_HOSPITALS)]
    for terminal in terminals.itertuples():
        for facility_id, hospital in gm.iterrows():
            walk = walk_option(terminal, hospital)
            routes = bus_routes(bus, terminal, hospital)
            drives = observed_drives(rides, terminal, hospital)
            for hour in HOURS:
                options = {
                    "walk": walk,
                    "bus": bus_option(bus, routes, hour),
                    "taxi": taxi_option(terminal, hospital, hour, hourly, placeholder, drives),
                }
                for mode, opt in options.items():
                    rows.append({"stop_id": terminal.terminal_id, "facility_id": facility_id,
                                 "hour": hour, "mode": mode, **opt})

    # Islands with their own atoll hospital: harbour to hospital on foot.
    for island_key, facility_id in config.ATOLL_HOSPITALS.items():
        hospital = hospitals.loc[facility_id]
        minutes = config.TERMINAL_EXIT_MIN + hospital.walk_minutes
        for hour in HOURS:
            rows.append({"stop_id": island_key, "facility_id": facility_id, "hour": hour,
                         "mode": "walk", "minutes": minutes, "available": "yes",
                         "detail": f"walk {hospital.access_distance_m / 1000:.1f} km from harbour"})

    table = pd.DataFrame(rows, columns=COLUMNS)
    table["minutes"] = table.minutes.astype(float).round(1)
    return table


# Walk minutes from docs/members/M1_gis.md (5 min exit + straight-line walk).
EXPECTED_WALK = {
    ("T_MALE_NORTH", "H01"): 23, ("T_MALE_NORTH", "H02"): 11, ("T_MALE_NORTH", "H03"): 16,
    ("T_MALE_WEST", "H01"): 7, ("T_MALE_WEST", "H02"): 24, ("T_MALE_WEST", "H03"): 25,
    ("T_HULHUMALE", "H04"): 12, ("T_HULHUMALE", "H05"): 11, ("T_VILLIMALE", "H06"): 7,
}


def check_last_mile(table: pd.DataFrame) -> None:
    """The "done when" checks from BUILD_PLAN section 7 (M1)."""
    walk = table[table["mode"] == "walk"].set_index(["stop_id", "facility_id", "hour"]).sort_index()
    for (stop, fac), expected in EXPECTED_WALK.items():
        if (stop, fac, 0) not in walk.index:
            continue    # Senahiya dropped by INCLUDE_SENAHIYA = False
        got = walk.loc[(stop, fac), "minutes"]
        if (walk.loc[(stop, fac), "available"] != "yes").any() or (got.round() != expected).any():
            raise ValueError(f"walk {stop} -> {fac}: expected {expected} min every hour")

    if table[table.available == "yes"].minutes.isna().any():
        raise ValueError("available rows without minutes")

    bus = BusNetwork()
    used = table[(table["mode"] == "bus") & (table.available == "yes")]
    for row in used.itertuples():
        route = row.detail.split(" ")[0]
        if bus.wait_at(route, row.hour) is None:
            raise ValueError(f"bus {route} available outside service hours at {row.hour}:00")

    to_villimale = table[(table.facility_id == "H06") & (table.stop_id != "T_VILLIMALE")]
    from_villimale = table[(table.stop_id == "T_VILLIMALE") & (table.facility_id != "H06")]
    if (pd.concat([to_villimale, from_villimale]).available == "yes").any():
        raise ValueError("Villimalé <-> Malé/Hulhumalé hospitals must be unavailable by road")

    hm = walk.loc[("T_HULHUMALE", "H04"), "minutes"]
    if (hm >= 15).any():
        raise ValueError("Hulhumalé terminal -> Hulhumalé Hospital walk should be under 15 min")


def write_last_mile() -> pd.DataFrame:
    table = build_last_mile()
    check_last_mile(table)
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    table.to_csv(config.LAST_MILE_CSV, index=False, encoding=config.WRITE_ENCODING)
    return table


if __name__ == "__main__":
    table = write_last_mile()
    print(f"wrote {config.LAST_MILE_CSV.relative_to(config.ROOT)} ({len(table)} rows)\n")
    print("fastest minutes by mode over the day (blank = never available):")
    print(table[table.available == "yes"]
          .pivot_table(index=["stop_id", "facility_id"], columns="mode",
                       values="minutes", aggfunc="min").round(0).to_string())
