# Prompt: Kaafu Connect datathon deck

Make a slide deck for **Kaafu Connect** (Maldives Datathon 2026). Team:
- Zayan: GIS and last mile;
- Eish: boat GPS and taxi data;
- Al: network and indicators;
- Saroof: lead and dashboard.

## Rules
- **Use my design system** for layout, type and colour. Don't restyle the attached charts.
- **No more than 8 slides.** The deck is exported as a PDF, which is the official copy, so no animation should carry meaning.
- **The slides must cover:** the problem, our data and method, our findings, and what they mean for transport policy.
- **One message per slide.** Put that message in the title as a full sentence, with at most 3–4 short supporting points. The visuals must be readable from the back of a room.
- **Use only the numbers below, exactly as written.** Don't round them differently or invent any.
- **Speaker notes:** 1–2 sentences per slide, starting with who presents it. All four members speak.
- **Be honest about scope.** "Speedboats" means boat movements observed in 2025 GPS data, not a published schedule.

## How we're judged (shape the deck around this)

| Criterion | Weight | Where the deck answers it |
|---|---|---|
| Technical execution | 20% | Slide 4 (validated method), slide 7 (limits named), live demo |
| Data utilization | 15% | Slide 3: right data, correctly used, sourced |
| Impact | 15% | Slide 6: named decision-makers and what they could do differently |
| Scalability and readiness | 15% | Slide 8: updated data, maintainable tools, named user, realistic plan |
| Relevance | 10% | Slides 1–2: a real Maldives transport question |
| Innovation | 10% | Slides 1, 4, 5: what's new in the idea and the method, not the dashboard |
| Teamwork | 10% | Roles on slide 2, a presenter on every slide |
| Clarity | 5% | One message per slide, readable charts |

## Fixed definitions (use these words everywhere)
- **Within 2 h:** door to door, from leaving home to the hospital door. It's the chance that someone who needs a hospital at a random moment between 06:00 and 18:00 gets there within 2 h: each island's population × the share of its daytime departures that make it.
- **The setting:** the Wednesday public ferry timetable (MTCC/RTL CFN). The trip home to the harbour takes 5 min, and changing boats takes 10 min.
- **An island with no boat in time:** call it **"no scheduled boat until the weekend"**. Don't use "unreachable".
- **Chart colours already used:**
  - orange = public ferries;
  - blue = with observed speedboats;
  - grey = HDX.
- **Map colours:**
  - blue = within 1 h;
  - amber = 1–2 h;
  - red = over 2 h;
  - grey = no scheduled boat.

## Slides

**1. The problem** (Saroof)
- Title idea: *"Global estimates say 77% of Kaafu is within 2 hours of a hospital. Islanders don't drive; they wait for a boat."*
- HDX's car-only estimate puts 77.4% of Kaafu and 45.9% of the Maldives within 2 h of a hospital.
- **What's new:** we measure access using real departure times. Someone leaving at 14:00 waits for the next actual boat, which may be tomorrow's.
- Visual: `m3_within_vs_hdx.png`.

**2. Question, users and team** (Saroof)
- The question: from each of 23 islands (31,414 people), how long does reaching a hospital really take, door to door, at any time of day? Which islands are worst served, and which ferry change helps most?
- The islands: the 9 inhabited Kaafu islands, plus 14 in Alif Alif, Alif Dhaalu and Vaavu with boats to Malé.
- Users:
  - **MTCC / Ministry of Transport:** where to add or retime ferries.
  - **MBS:** two NSDS indicators that have no base year.
- Team roles, as one line each (names above).

**3. Data** (Zayan)
- **Only organiser-provided and open data:**
  - MTCC/RTL ferry and bus timetables (2026);
  - Census 2022 (MBS Statistical Yearbook 2026, table 3.3);
  - FollowMe boat GPS: 9.8 M pings, 997 boats, Aug 2025;
  - Avas taxi requests: 266,410, Aug–Sep 2026;
  - OpenStreetMap island outlines and hospitals;
  - HDX accessibility indicators.
- **Handled correctly:**
  - The FollowMe clock is shifted from UTC to Malé time, and its speed column is in knots.
  - Device IDs are hashed, and no raw data is published.
- Credit line: © OpenStreetMap contributors (ODbL), route geometry by OSRM; MBS and shared datasets via Team Kandu; MTCC/RTL; FollowMe and Avas data from the organisers; HDX.
- Visual: `map_male_boat_days.png`. It shows 16 of 23 islands with a boat to Malé on 3 days a week or fewer, and no ferry on Fridays.

**4. Method, and why it holds up** (Al and Eish)
- **Network (Al):**
  - The timetable becomes boat legs.
  - We find the earliest arrival from every island, every 15 min of the day: 23 islands × 96 departures × 2 hospital targets.
  - Then we add the fastest walk, bus or taxi from the terminal to the hospital, which gives a door-to-door time.
- **Boat GPS (Eish):**
  - Pings become island stops (10 min still inside the island outline + 300 m), and stops become trips: 10,975 trips.
  - Trips split into ferry or speedboat at 26 km/h.
- **Checks:**
  - Observed ferry legs match the timetable to a median of 5 min, over 28 legs.
  - Results match a hand-checked reference for all 23 islands.
  - A second, independent implementation reproduces all 4,416 journeys to within 0.15 min.
  - Automated tests cover the routing rules.
- **AI use:** the code was written with Claude Code, and team members directed and reviewed it.
- Visual: a simple pipeline diagram, or `map_greater_male.png`.

**5. Findings** (Al and Eish)
- Title idea: *"Need a hospital during the day in Kaafu? By public ferry, there's a 2.4% chance you get there within 2 hours."*
- **Headline:**
  - HDX: 77.4%.
  - Public ferries: **2.4%**.
  - With the speedboats people actually use: **22.6%**.
- **Miss the morning boat and you wait a day:**
  - The only daytime departures that make it are a short window around a few islands' morning boat (e.g. Himmafushi 07:00–07:45, Thulusdhoo 07:00 only).
  - Leaving at 07:00, 30.8% are within 2 h; at 08:00, 0%.
  - Leaving at 09:00, 8,847 people on 8 islands (28%) have no scheduled boat until the weekend.
- **The ferry isn't slow, it's rare:**
  - Re-timing ferries to observed speeds changes nothing.
  - Re-timing the ferries moves the share only from 2.4% to 2.8%; adding the observed speedboats lifts it to 22.6%.
  - From the islands near Malé, 74–88% of boat trips are speedboats. Maafushi → Malé takes 84–90 min by ferry and 41 by speedboat.
- **The last mile isn't the problem:** every ferry terminal is a 7–11 min walk from a hospital.
- Visuals: `m3_within_2h_through_day.png` and `m3_last_departure.png`. `map_access_wed_0900.png` is optional.

**6. What it means for transport policy** (Al)
- **For MTCC, one extra evening ferry:**
  - Route 307 at 22:00 saves Kaashidhoo and Gaafaru 13.2 h per person (3,822 people).
  - Route 303 at 20:00 saves the Alif Alif islands 11.2 h (4,490 people).
  - Route 308 at 18:00 helps the most people (6,737).
- **Frequency, not speed:** doubling runs within the same hours doesn't help, because the gaps are overnight and between days.
- **For MBS:**
  - We have a repeatable base-year method for two NSDS indicators.
  - 100% of people are within 30 min of a health centre, but only 2.4% of Kaafu can reach a hospital within 2 h by public boat.
- **Who benefits:** islanders who miss the morning boat; the planners who set ferry times.
- Visual: `m3_best_ferry_change.png`.

**7. Limits** (Eish and Zayan)
- **Timetable:** one service day (Wednesday) with a Wed–Thu horizon. The Malé jetty is assumed to be Jetty NO5.
- **Speedboats:**
  - They are modelled from 2025 trackers, not a schedule, and some may be private or resort boats.
  - Airport-bound speedboats aren't modelled.
- **GPS:** "slow" boats include cargo dhonis, and the data counts boats, not passengers.
- **Mixed years:** FollowMe is from 2025; the timetable and Avas are from 2026.
- **Walks:** straight-line distances.
- **The nearest hospital may be private** (ADK).
- **Out of scope:** ambulance boats, charters and flights.

**8. Built to keep going** (Saroof)
- **Updated data:**
  - Every assumption is in one config file.
  - When the timetable changes, the whole pipeline reruns from CSVs in about 2 minutes.
- **Maintainable tools:** open-source Python (pandas, DuckDB, Streamlit), with a public repo and tests.
- **Named user:** MTCC can rerun it each timetable season. The dashboard has live sliders for ferry frequency, an extra evening run, and the new Thulusdhoo hospital.
- **Next steps:**
  - Cover all 20 atolls and all 7 days.
  - Add a GTFS feed for CFN, and live FollowMe for real-time speedboat availability.
  - Add public-hospital-only and ambulance-boat scenarios.
- Closing line: *"The boats and routes exist. The gaps are in when they run."*

## Attached images (in `docs/figures/`)
`m3_within_vs_hdx.png`, `m3_within_2h_through_day.png`, `m3_last_departure.png`, `m3_worst_served.png` (alternative to the last-departure chart), `m3_scheduled_vs_observed.png` (optional, slide 5), `m3_best_ferry_change.png`, `map_male_boat_days.png`, `map_greater_male.png`, `map_access_wed_0900.png`

---

## Separate deliverable: one-page methods note (not a slide)
If you can, also make a one-page document in the same design. Its sections:
1. **Question and scope:** 23 islands; hospitals; the Wednesday timetable.
2. **Data:** the slide 3 list, with its credits.
3. **Method:** the network, last mile and boat GPS steps from slide 4. Include the fixed assumptions (5 min to the harbour, 10 min to change boats, walking at 80 m/min) and the 1.5× cap on re-timed ferry legs.
4. **Validation:** the checks from slide 4.
5. **Limits:** slide 7.
6. **How AI tools were used:**
   - All code was written with Claude Code, directed and reviewed by each member.
   - Claude Code also ran the data checks: GPS jitter and tracker sleeps, colour-blind-safe palettes, and the cross-check between the two implementations.
   - It drafted the handovers and slide text.
   - The DuckDB prep queries were AI-assisted.
   - Every number was checked against the committed outputs.
