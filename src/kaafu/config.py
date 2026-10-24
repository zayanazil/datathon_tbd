"""Paths and every model parameter (BUILD_PLAN section 5). Nothing else hard-codes these."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
SHEETS = DATA / "sheets"            # committed hand-built sheets
RAW = DATA / "raw"                  # FollowMe, Avas, Team Kandu files (never committed)
PROCESSED = DATA / "processed"      # pipeline outputs (committed, no IMEIs)
PLACEHOLDER = DATA / "placeholder"  # stand-ins used until a real sheet arrives

# --- Journey legs -----------------------------------------------------------
WALK_M_PER_MIN = 80        # straight-line walking speed
ACCESS_MIN = 5             # home to harbour on the origin island
BOAT_TRANSFER_MIN = 10     # least time to change boats
TERMINAL_EXIT_MIN = 5      # boat to street
TAXI_BASE_WAIT_MIN = 5     # Avas has no pickup-wait field
TAXI_RETRY_MIN = 10        # added in proportion to the unserved share that hour
TAXI_DETOUR = 1.4          # road / straight-line distance, taxi fallback only
TAXI_PLACEHOLDER_KMH = 20  # flagged speed used until avas_hourly.csv exists
TAXI_MIN_RIDES = 10        # rides needed for a terminal-to-hospital median
TAXI_MATCH_M = 400         # pickup/dropoff radius for that median
MAX_BOAT_KMH = 80          # anything faster is a data error

# --- FollowMe ---------------------------------------------------------------
STOP_SPEED_KMH = 2
STOP_MIN = 10
ZONE_BUFFER_M = 300
ZONE_FALLBACK_RADIUS_M = 600
MAX_TRIP_HOURS = 6
OBSERVED_MIN_TRIPS = 5
FOLLOWME_UTC_OFFSET_H = 5  # device_date is UTC
FOLLOWME_BBOX = (3.40, 5.00, 72.70, 73.80)  # lat_min, lat_max, lon_min, lon_max
UTM_CRS = "EPSG:32643"

# --- Indicators -------------------------------------------------------------
STEP_MIN = 15
THRESHOLDS_MIN = [30, 60, 90, 120, 240]
HEADLINE_THRESHOLD_MIN = 120
DAY_START_MIN, DAY_END_MIN = 6 * 60, 18 * 60  # "day" = departures 06:00-18:00
EVENING_RUN_TIMES = [18 * 60, 20 * 60, 22 * 60]

# M4 brief sets True; BUILD_PLAN section 5 says False until public access is confirmed.
INCLUDE_SENAHIYA = True

DAYS = ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri"]
DAY, NEXT_DAY = "Wed", "Thu"

GREATER_MALE = ["K.Malé", "K.Hulhumalé", "K.Villimalé", "K.Hulhulé"]
# Islands joined by road (Sinamalé bridge + Hulhulé-Hulhumalé link). Villimalé is not.
ROAD_LINKED = {"K.Malé", "K.Hulhumalé", "K.Hulhulé"}
GM_HOSPITALS = ["H01", "H02", "H03", "H04", "H05", "H06"]
ATOLL_HOSPITALS = ["H07", "H08", "H09"]
THULUSDHOO_HOSPITAL_ID = "H10"
BUS_ROUTES = [f"R{i}" for i in range(1, 16)]  # all 15: only the minibuses serve Jetty NO5
DEFAULT_MALE_TERMINAL = "T_MALE_NORTH"

TARGETS = {"gm_hospital": "Nearest Greater Malé hospital", "any_hospital": "Any hospital"}


def gm_hospitals() -> list[str]:
    return [h for h in GM_HOSPITALS if INCLUDE_SENAHIYA or h != "H03"]
