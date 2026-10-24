"""Paths and parameters for Kaafu Connect.

Every assumption lives here, never hard-coded elsewhere, and every one goes on
the limits slide. Defaults and reasons follow docs/BUILD_PLAN.md section 5.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]

DATA = ROOT / "data"
SHEETS = DATA / "sheets"          # input sheets, committed, read-only
RAW = DATA / "raw"                # never committed
PROCESSED = DATA / "processed"    # outputs, committed (no IMEIs)
FIGURES = ROOT / "docs" / "figures"

# Input sheets (data_pack, read-only)
ISLANDS_CSV = SHEETS / "islands.csv"
ISLAND_NAMES_CSV = SHEETS / "island_names.csv"
FACILITIES_CSV = SHEETS / "facilities.csv"
FERRY_TIMETABLE_CSV = SHEETS / "ferry_timetable.csv"
BUS_SERVICE_HOURS_CSV = SHEETS / "bus_service_hours.csv"
BUS_HEADWAYS_CSV = SHEETS / "bus_headways.csv"
HDX_BENCHMARK_CSV = SHEETS / "hdx_benchmark.csv"

# Raw files (organisers and Team Kandu)
FOLLOWME_PARQUET = RAW / "followme_kaafu_aug2025.parquet"
AVAS_RIDES_CSV = RAW / "avas" / "avas_rides_aug_sep_2026.csv"
TEAM_KANDU = RAW / "team_kandu"
RTL_BUS_STOPS_CSV = TEAM_KANDU / "rtl_bus_stops.csv"
RTL_BUS_DEPARTURES_CSV = TEAM_KANDU / "rtl_bus_departures.csv"
OSM_CACHE = RAW / "osm"           # cached Overpass replies

# Processed outputs (file contracts, BUILD_PLAN section 4)
TERMINALS_CSV = PROCESSED / "terminals.csv"                  # M1
ISLAND_ZONES_GEOJSON = PROCESSED / "island_zones.geojson"    # M1
LAST_MILE_CSV = PROCESSED / "last_mile.csv"                  # M1
CONNECTIONS_CSV = PROCESSED / "connections.csv"              # M3
AVAS_HOURLY_CSV = PROCESSED / "avas_hourly.csv"              # M2
OBSERVED_TRIPS_CSV = PROCESSED / "observed_trips.csv"        # M2
OBSERVED_PAIRS_CSV = PROCESSED / "observed_pairs.csv"        # M2
ACCESS_RESULTS_CSV = PROCESSED / "access_results.csv"        # M3
ISLAND_SUMMARY_CSV = PROCESSED / "island_summary.csv"        # M3

# The sheets are UTF-8 with a BOM; outputs are plain UTF-8.
READ_ENCODING = "utf-8-sig"
WRITE_ENCODING = "utf-8"

# ---------------------------------------------------------------------------
# Service day
# ---------------------------------------------------------------------------
DAY = "Wed"          # keep ferry rows whose `days` contains it; bus day_type below
NEXT_DAY = "Thu"     # rows added at +1440 so late starts find the next morning's boat
BUS_DAY_TYPE = "weekday"   # Sun-Thu; "saturday" and "friday" also exist
MINUTES_PER_DAY = 1440

# ---------------------------------------------------------------------------
# Travel parameters (BUILD_PLAN section 5)
# ---------------------------------------------------------------------------
WALK_M_PER_MIN = 80        # prep guide; applied to straight-line distances
ACCESS_MIN = 5             # home to harbour on the origin island (islands < ~1 km across)
BOAT_TRANSFER_MIN = 10     # least time needed to change boats
TERMINAL_EXIT_MIN = 5      # getting off the boat and reaching the street
TAXI_BASE_WAIT_MIN = 5     # assumption: Avas has no pickup-wait field
TAXI_RETRY_MIN = 10        # added in proportion to the Avas unserved share that hour
TAXI_DETOUR = 1.4          # road / straight-line distance; taxi fallback only
VILLIMALE_FERRY_MIN = 8    # team figure; already applied in ferry_timetable.csv

# ---------------------------------------------------------------------------
# Last mile details (M1, BUILD_PLAN 6.3 and docs/members/M1_gis.md)
# ---------------------------------------------------------------------------
INCLUDE_SENAHIYA = True    # confirmed 23 Oct: public 24/7 ED, covered by Aasandha

GM_HOSPITALS = ["H01", "H02", "H03", "H04", "H05", "H06"]   # main measure
ATOLL_HOSPITALS = {"AA.Rasdhoo": "H07", "ADh.Mahibadhoo": "H08", "V.Felidhoo": "H09"}
SENAHIYA_ID = "H03"

# Road networks: walking needs the same island; bus and taxi need the same network.
# Malé, Hulhulé (airport) and Hulhumalé are linked by road; Villimalé is not.
ROAD_NETWORK = {
    "K.Malé": "greater_male",
    "K.Hulhulé": "greater_male",
    "K.Hulhumalé": "greater_male",
    "K.Villimalé": "villimale",
}

# Avas pickup zone for each terminal's island (taxi wait by zone and hour)
TAXI_ZONE = {"K.Malé": "male", "K.Hulhumalé": "hulhumale", "K.Hulhulé": "airport"}

# Max walk from terminal/hospital to a bus stop. 550 rather than the guide's
# 400 so the Malé terminals reach the routes that cross the bridge to
# Hulhumalé (R1/R3/R7 at 435 m from Maafannu, R2/R8 at 535 m from Jetty NO5).
BUS_STOP_RADIUS_M = 550
MINIBUS_SPEED_KMH = 12        # R10-R12, R15 have no departures data; "estimated"
TAXI_MATCH_RADIUS_M = 400     # Avas rides counted as terminal-to-hospital
TAXI_MIN_RIDES = 10           # fewer rides than this: use the distance fallback
TAXI_PLACEHOLDER_KMH = 20     # until avas_hourly.csv arrives; flagged in `detail`
TAXI_PLACEHOLDER_EXPIRED = 0.07

# ---------------------------------------------------------------------------
# Island zones (M1 Step 2)
# ---------------------------------------------------------------------------
UTM_CRS = "EPSG:32643"        # UTM 43N, metres
WGS84_CRS = "EPSG:4326"
ZONE_BUFFER_M = 300           # OSM outline buffer
ZONE_CIRCLE_M = 600           # fallback circle around the islands.csv point
ZONE_CIRCLE_LARGE_M = 1500    # long islands, or a point far from OSM's
LARGE_ZONE_ISLANDS = ["K.Malé", "K.Hulhumalé", "K.Hulhulé", "ADh.Dhigurah"]
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_USER_AGENT = "kaafu-connect/0.1 (Maldives Datathon 2026)"   # else 406
OVERPASS_SEARCH_M = 1500

# ---------------------------------------------------------------------------
# FollowMe and observed times (M2)
# ---------------------------------------------------------------------------
FOLLOWME_UTC_OFFSET_H = 5     # FollowMe timestamps are UTC; Malé is UTC+5
KNOTS_TO_KMH = 1.852          # FollowMe `speed` column is in knots
STOP_SPEED_KMH = 2            # guide's stop rule
STOP_MIN = 10
OBSERVED_MIN_TRIPS = 5        # observed time used only with at least 5 trips behind it
MAX_BOAT_KMH = 80             # faster legs or trips are dropped as errors
MAX_TRIP_HOURS = 6
PING_MAX_GAP_MIN = 30         # longer gaps between pings: no segment speed
SPEED_WINDOW_MIN = 5          # stop speed = displacement over +-2.5 min (ping-to-ping is GPS jitter)
BOAT_MIN_SEA_SHARE = 0.05     # boat = at least 5% of pings at sea...
BOAT_SEA_DIST_M = 2500        # ...more than 2.5 km from every island point...
BOAT_MIN_ISLANDS = 2          # ...and at least 2 islands visited
SPEED_CLASS_SPLIT_KMH = 28    # slow/fast split if the trip-speed histogram has no clear dip
DEVICE_HASH_LEN = 8           # output only this many characters of device_id
FOLLOWME_DAYS = 31            # August 2025, for trips_per_day
FOLLOWME_DEV_DAYS = (4, 10)   # one week for development (Step 2)

# ---------------------------------------------------------------------------
# Avas taxi table (M2)
# ---------------------------------------------------------------------------
AVAS_WEEKDAYS = [6, 0, 1, 2, 3]   # pandas dayofweek for Sun-Thu; the build day is Wednesday
AVAS_ZONES = {                     # pickup boxes: (lat_min, lat_max, lon_min, lon_max)
    "male": (4.165, 4.182, 73.500, 73.522),
    "airport": (4.182, 4.205, 73.520, 73.536),     # top 4.205, not 4.207: Hulhumalé's south tip
    "hulhumale": (4.200, 4.245, 73.525, 73.556),   # checked after airport
}
AVAS_MIN_RIDES = 20               # fewer rides in a zone-hour: use the zone's all-day speed
AVAS_SPEED_SAME_ZONE = True       # speed from rides that start and end in the pickup zone:
                                  # all rides are mostly Malé-Hulhumalé bridge trips (~39 km/h)

# ---------------------------------------------------------------------------
# Routing and indicators (M3)
# ---------------------------------------------------------------------------
STEP_MIN = 15                         # departure-time resolution
THRESHOLDS_MIN = [30, 60, 90, 120, 240]   # HDX format plus the guide's 4-hour band
DAYTIME_START_MIN = 6 * 60            # "day" = departures 06:00-18:00
DAYTIME_END_MIN = 18 * 60
EVENING_RUN_TIMES = ["18:00", "20:00", "22:00"]   # best ferry change candidates

# Population checks (Census 2022)
POP_KAAFU = 17_749
POP_INBOUND = 13_665
POP_TOTAL = 31_414
