"""Write a PLACEHOLDER ferry timetable to data/placeholder/ so the app runs before the real sheet arrives.

The routes, days and times below are invented (except route 309 leaving Maafushi 07:25 and
reaching Malé 09:05, from the model note). Never present results built on them as findings.
The loader prefers data/sheets/ferry_timetable.csv as soon as it exists.

    python tests/make_placeholders.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from kaafu import config as C  # noqa: E402
from kaafu.geo import haversine_m  # noqa: E402
from kaafu.load import load_islands  # noqa: E402

KMH, DETOUR, DWELL = 20, 1.15, 5
EXCEPT_FRI = "Sat-Thu"

# route_id, stops (towards Malé), inbound departures, outbound departures, inbound days, outbound days
ROUTES = [
    ("301", ["K.Dhiffushi", "K.Thulusdhoo", "K.Huraa", "K.Himmafushi", "K.Malé"], ["07:00", "15:30"], ["10:30", "18:00"],
     EXCEPT_FRI, EXCEPT_FRI),
    ("302", ["K.Kaashidhoo", "K.Gaafaru", "K.Malé"], ["06:30"], ["14:00"], EXCEPT_FRI, EXCEPT_FRI),
    ("304", ["AA.Mathiveri", "AA.Bodufolhudhoo", "AA.Ukulhas", "AA.Rasdhoo", "K.Malé"], ["06:00"], ["13:00"],
     "Sun Tue Wed Thu", "Sat Mon Wed"),
    ("305", ["AA.Thoddoo", "AA.Rasdhoo", "K.Malé"], ["07:00"], ["14:30"], "Sat Mon Wed", "Sun Tue Thu"),
    ("306", ["ADh.Dhigurah", "ADh.Dhangethi", "ADh.Omadhoo", "ADh.Mahibadhoo", "ADh.Hangnaameedhoo", "K.Malé"],
     ["06:00"], ["13:00"], "Sat Mon Thu", "Sun Tue Wed"),
    ("307", ["V.Felidhoo", "V.Keyodhoo", "V.Thinadhoo", "V.Fulidhoo", "K.Malé"], ["06:30"], ["14:00"],
     EXCEPT_FRI, EXCEPT_FRI),
    ("308", ["K.Guraidhoo", "K.Maafushi", "K.Gulhi", "K.Malé"], ["06:45"], ["15:00"], EXCEPT_FRI, EXCEPT_FRI),
    ("309", ["K.Maafushi", "K.Gulhi", "K.Malé"], ["07:25"], ["14:30"], "daily", "daily"),
]
FIXED = {("309", "K.Maafushi", "07:25"): [("07:25", "08:00"), ("08:05", "09:05")]}


def _fmt(m: int) -> str:
    return f"{m // 60 % 24:02d}:{m % 60:02d}"


def _minutes(a, b, pts) -> int:
    km = haversine_m([pts.loc[a]], [pts.loc[b]])[0] / 1000
    return max(10, int(round(km * DETOUR / KMH * 60 / 5)) * 5)


def build() -> pd.DataFrame:
    pts = load_islands().set_index("island_key")[["harbour_lat", "harbour_lon"]].to_numpy().tolist()
    pts = pd.Series(pts, index=load_islands()["island_key"])
    rows = []
    for rid, stops, inbound, outbound, in_days, out_days in ROUTES:
        for direction, seq, times, days in (("in", stops, inbound, in_days), ("out", stops[::-1], outbound, out_days)):
            for k, start in enumerate(times):
                fixed = FIXED.get((rid, seq[0], start))
                h, m = map(int, start.split(":"))
                t = h * 60 + m
                for i, (a, b) in enumerate(zip(seq, seq[1:])):
                    if fixed:
                        dep, arr = fixed[i]
                    else:
                        dep, arr = _fmt(t), _fmt(t + _minutes(a, b, pts))
                        t += _minutes(a, b, pts) + DWELL
                    rows.append({"route_id": rid, "trip_id": f"{direction}{k + 1}", "from": a, "to": b,
                                 "depart": dep, "arrive": arr, "days": days, "arrival_terminal": "",
                                 "departure_terminal": "", "operator": "MTCC/RTL (placeholder)",
                                 "source": "PLACEHOLDER"})
    # Villimalé ferry: Maafannu terminal <-> Villimalé every 15 minutes, 05:30-23:45, 10 minutes.
    for k, t in enumerate(range(5 * 60 + 30, 24 * 60, 15)):
        for d, (a, b, term_a) in enumerate((("K.Malé", "K.Villimalé", "T_MALE_WEST"),
                                            ("K.Villimalé", "K.Malé", ""))):
            rows.append({"route_id": "VLM", "trip_id": f"{'ab'[d]}{k}", "from": a, "to": b, "depart": _fmt(t),
                         "arrive": _fmt(t + 10), "days": "daily", "arrival_terminal": "T_MALE_WEST" if d else "",
                         "departure_terminal": term_a, "operator": "MTCC (placeholder)", "source": "PLACEHOLDER"})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    C.PLACEHOLDER.mkdir(parents=True, exist_ok=True)
    out = C.PLACEHOLDER / "ferry_timetable.csv"
    df = build()
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"wrote {out.relative_to(C.ROOT)}: {len(df)} PLACEHOLDER legs")
