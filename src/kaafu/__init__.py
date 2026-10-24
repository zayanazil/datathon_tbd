"""Kaafu Connect: door-to-door island access to hospitals by scheduled boat.

Pipeline (each module runs with `python -m kaafu.<module>`; see README):
  geo        terminals, island zones, map layers, static maps            (M1)
  avas       taxi unserved share and speed by zone and hour              (M2)
  lastmile   terminal -> hospital by walk, bus, taxi, per hour           (M1)
  followme   boat GPS pings -> stops -> trips -> observed pair times     (M2)
  timetable  ferry timetable -> boat connections                         (M3)
  routing    connection scan: earliest arrival and trip breakdown        (M3)
  indicators base results, population within X min, HDX, NSDS            (M3)
  scenarios  what-if levers and the best ferry change                    (M3)
  dashboard  the Streamlit app's loaders and slider mapping              (M4)
All paths and parameters live in config.py.
"""
