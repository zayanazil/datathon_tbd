-- Kaafu Connect: FollowMe extract (prep, 23 Oct 2026). AI-assisted (Claude Code); listed in README.
--
-- What it does: reads the organisers' raw FollowMe files (one CSV per day, Aug 2025), keeps pings
-- inside Kaafu, Alif Alif, Alif Dhaalu and Vaavu (lat 3.40-5.05, lon 72.70-73.80), replaces the
-- IMEI with its md5 hash (no IMEI leaves this step) and writes the parquet that followme.py reads.
-- The C1-C3 queries below are the quick checks behind the build decisions: speed is in knots,
-- which devices are boats, and how many island-to-Malé trips a day there are.
--
-- How to run: from the organisers' dataset folder (the one containing FollowMe/), with the DuckDB
-- CLI:   duckdb.exe < followme_queries.sql
-- then copy data_pack/raw/followme_kaafu_aug2025.parquet to this repo's data/raw/.
-- Timestamps stay in UTC here; followme.py adds +5 h (Maldives time).
-- FollowMe subset + check (Parts B and C of "Kaafu Connect: finishing the data pack"). Run inside duckdb.exe from the repo root. AI-assisted: list in README.
CREATE TABLE fm AS
SELECT md5(CAST(imei AS VARCHAR))                         AS device_id,
       CAST(device_date AS TIMESTAMP)                     AS ts,
       latitude AS lat, longitude AS lon, speed, heading,
       CAST(regexp_extract(filename, '(\d+)\.csv$', 1) AS INTEGER) AS day
FROM read_csv('FollowMe/FollowMe_august_2025/*.csv', filename = true, union_by_name = true)
WHERE latitude  BETWEEN 3.40 AND 5.05
  AND longitude BETWEEN 72.70 AND 73.80;
COPY fm TO 'data_pack/raw/followme_kaafu_aug2025.parquet' (FORMAT parquet);
-- C1
CREATE TABLE seg AS
SELECT *, 2*6371*asin(sqrt(pow(sin(radians(lat-plat)/2),2)
          + cos(radians(plat))*cos(radians(lat))*pow(sin(radians(lon-plon)/2),2))) AS km,
       epoch(ts - pts)/3600.0 AS hrs
FROM (SELECT *, lag(lat) OVER w AS plat, lag(lon) OVER w AS plon, lag(ts) OVER w AS pts
      FROM fm WINDOW w AS (PARTITION BY device_id ORDER BY ts));
SELECT count(*) AS n,
       round(median(speed / (km/hrs)), 3) AS ratio,
       round(median(km/hrs), 1) AS median_kmh
FROM seg
WHERE hrs BETWEEN 30/3600.0 AND 300/3600.0
  AND km/hrs BETWEEN 5 AND 60 AND speed > 0;
-- C2
CREATE TABLE isl AS
SELECT island_key, harbour_lat AS ilat, harbour_lon AS ilon
FROM read_csv('data_pack/sheets/islands.csv');
CREATE TABLE z AS
SELECT device_id, ts, day, arg_min(island_key, d) AS near_key, min(d) AS near_km
FROM (SELECT f.device_id, f.ts, f.day, i.island_key,
             2*6371*asin(sqrt(pow(sin(radians(i.ilat-f.lat)/2),2)
               + cos(radians(f.lat))*cos(radians(i.ilat))*pow(sin(radians(i.ilon-f.lon)/2),2))) AS d
      FROM fm f CROSS JOIN isl i)
GROUP BY device_id, ts, day;
CREATE TABLE dev AS
SELECT device_id, count(*) AS pings,
       avg(CASE WHEN near_km > 2.5 THEN 1 ELSE 0 END) AS sea_share,
       count(DISTINCT CASE WHEN near_km < 1.2 THEN near_key END) AS n_islands
FROM z GROUP BY device_id;
SELECT CASE WHEN sea_share >= 0.05 AND n_islands >= 2 THEN 'boat'
            WHEN sea_share <  0.01                    THEN 'land or moored'
            ELSE 'unclear' END AS kind,
       count(*) AS devices, sum(pings) AS pings
FROM dev GROUP BY 1 ORDER BY 2 DESC;
-- C3
CREATE TABLE visits AS
WITH p AS (
  SELECT device_id, ts, CASE WHEN near_km < 1.2 THEN near_key ELSE 'SEA' END AS zone
  FROM z WHERE device_id IN (SELECT device_id FROM dev WHERE sea_share >= 0.05 AND n_islands >= 2)),
r AS (
  SELECT *, row_number() OVER (PARTITION BY device_id ORDER BY ts)
          - row_number() OVER (PARTITION BY device_id, zone ORDER BY ts) AS grp
  FROM p)
SELECT device_id, zone, min(ts) AS arrive_ts, max(ts) AS leave_ts
FROM r GROUP BY device_id, zone, grp;
CREATE TABLE trips AS
SELECT * FROM (
  SELECT device_id, zone AS from_key, leave_ts AS dep_ts,
         lead(zone)      OVER w AS to_key,
         lead(arrive_ts) OVER w AS arr_ts
  FROM visits WHERE zone <> 'SEA'
  WINDOW w AS (PARTITION BY device_id ORDER BY arrive_ts))
WHERE to_key IS NOT NULL AND from_key <> to_key
  AND epoch(arr_ts - dep_ts) BETWEEN 600 AND 6*3600;
CREATE TABLE to_male AS
SELECT * FROM trips
WHERE to_key   IN ('K.Malé','K.Hulhumalé','K.Villimalé')
  AND from_key NOT IN ('K.Malé','K.Hulhumalé','K.Villimalé','K.Hulhulé');
SELECT CAST(dep_ts AS DATE) AS day, count(*) AS trips FROM to_male GROUP BY 1 ORDER BY 1;
SELECT from_key, count(*) AS trips, round(count(*)/31.0, 1) AS per_day,
       round(median(epoch(arr_ts - dep_ts)/60)) AS median_min
FROM to_male GROUP BY 1 ORDER BY trips DESC;
