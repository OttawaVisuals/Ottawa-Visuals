# Historical backfill spec — TomTom MOVE / Traffic Stats 30-day trial

**Goal:** pull historical average commute times for the *same 5 corridors* the live
poller tracks, for representative windows across the RTO era (2019 → 2025), so we
can chart "Ottawa commute times before / during WFH / through return-to-office"
and let the live pipeline extend the line from 2026 on.

This is a **one-time export** from a *different* TomTom product than the live APIs:
[MOVE / Traffic Stats](https://www.tomtom.com/products/traffic-stats/), **Route Analysis** tool.
Register the 30-day trial at <https://move.tomtom.com/register>.

---

## ⚠️ Read before starting the trial clock

- The trial is **30 days** and the **credit allotment is not published** — check it on
  registration; Traffic Stats bills by job size (≈ routes × days × analysis).
- **Pack everything into ONE job.** The plan below (10 routes × 6 date ranges × 14
  time sets) fits inside the per-job limits, so it should be a single submission.
- **Priority order if credits run short:** run **2019 and 2025 first** (the endpoints of
  the story). 2021–2024 just smooth the trend and can be dropped.
- Traffic Stats data lags ~72 h (3 days), irrelevant for historical windows.

**Per-job limits** (from the Route Analysis API reference): ≤20 routes · ≤24 date
ranges (each ≤366 days) · ≤24 time sets · ≤200 km/route · ≤732 unique days total.
Our plan: 10 routes, 6 date ranges, 14 time sets — all within limits.

---

## What we get back

Per **route** *and* per **segment**, for every date-range × time-set combination:
harmonic-mean speed, average/median/percentile travel time, and **sample size**
(GPS probe count — use it to judge confidence). Export as CSV.

---

## 1. Routes (10 = 5 corridors × 2 directions)

Downtown anchor: **45.4215, -75.6972** (Parliament / City Hall). Let MOVE snap the
fastest route between start and end (`followRoads: true`), same as the live poller.

| Route name | Start (lat, lon) | End (lat, lon) |
|---|---|---|
| kanata_to_downtown    | 45.3088, -75.8987 | 45.4215, -75.6972 |
| kanata_from_downtown  | 45.4215, -75.6972 | 45.3088, -75.8987 |
| orleans_to_downtown   | 45.4682, -75.5185 | 45.4215, -75.6972 |
| orleans_from_downtown | 45.4215, -75.6972 | 45.4682, -75.5185 |
| barrhaven_to_downtown | 45.2723, -75.7392 | 45.4215, -75.6972 |
| barrhaven_from_downtown | 45.4215, -75.6972 | 45.2723, -75.7392 |
| gatineau_to_downtown  | 45.4765, -75.7013 | 45.4215, -75.6972 |
| gatineau_from_downtown | 45.4215, -75.6972 | 45.4765, -75.7013 |
| riverside_to_downtown | 45.2907, -75.6710 | 45.4215, -75.6972 |
| riverside_from_downtown | 45.4215, -75.6972 | 45.2907, -75.6710 |

(Coordinates match `corridors.json`, so live and historical align on the same O/D pairs.)

## 2. Date ranges (6 — same calendar window each year for comparability)

Use **early–mid November** every year: no Ontario stat holiday, school in session,
no March break / summer distortion — a clean "typical commuting month." Weekday
filtering is handled by the time sets (below), so a plain date span is fine.

| Range name | From | To | RTO context |
|---|---|---|---|
| 2019_nov | 2019-11-04 | 2019-11-22 | Pre-pandemic baseline |
| 2021_nov | 2021-11-01 | 2021-11-19 | Peak WFH (federal public service remote) |
| 2022_nov | 2022-11-07 | 2022-11-25 | Early/partial return |
| 2023_nov | 2023-11-06 | 2023-11-24 | TB 2-day/week mandate era |
| 2024_nov | 2024-11-04 | 2024-11-22 | Ramp toward 3-day mandate (Sept 2024) |
| 2025_nov | 2025-11-03 | 2025-11-21 | Full 3-day RTO |

*(Drop 2022/2024 first if credits are tight; keep 2019 + 2021 + 2023 + 2025.)*

## 3. Time sets (14 — weekday hourly commute curve + a free-flow reference)

All **Mon–Fri**. Hourly bins across the commuting day give a curve that matches the
live poller's hourly/peak resolution; the overnight bin is the free-flow baseline.

```
wk_0600_0700, wk_0700_0800, wk_0800_0900, wk_0900_1000, wk_1000_1100,
wk_1100_1200, wk_1200_1300, wk_1300_1400, wk_1400_1500, wk_1500_1600,
wk_1600_1700, wk_1700_1800, wk_1800_1900,
wk_0200_0300   (overnight free-flow reference)
```

Each time set = days `MON,TUE,WED,THU,FRI`, one 1-hour window, zone `America/Toronto`.

---

## 4. API job body (shape — verify field names against the current Route Analysis reference)

If you use the API instead of the MOVE UI, one Route Analysis job POST covers the
whole plan. Field names below follow the documented structure but **confirm exact
keys** in the [Route Analysis reference](https://developer.tomtom.com/traffic-stats/documentation/api/route-analysis)
before submitting.

```json
{
  "jobName": "ottawa_rto_backfill_2019_2025",
  "distanceUnit": "KILOMETERS",
  "mapVersion": "current",
  "routes": [
    { "name": "kanata_to_downtown", "start": {"latitude": 45.3088, "longitude": -75.8987},
      "end": {"latitude": 45.4215, "longitude": -75.6972}, "followRoads": true, "zoneId": "America/Toronto" }
    /* ... the other 9 routes from the table above ... */
  ],
  "dateRanges": [
    { "name": "2019_nov", "from": "2019-11-04", "to": "2019-11-22" }
    /* ... 2021_nov ... 2025_nov ... */
  ],
  "timeSets": [
    { "name": "wk_0700_0800",
      "timeGroups": [ { "days": ["MON","TUE","WED","THU","FRI"], "times": ["07:00-08:00"] } ] }
    /* ... the other 13 time sets ... */
  ]
}
```

---

## 5. Where the export goes & how it aligns with live data

Save exports under **`Traffic/data/historical/`** (create it), e.g.
`route_analysis_2019_2025.csv` plus the raw JSON response.

To compare historical vs live cleanly, aggregate the **live** CSVs the same way
Traffic Stats reports — average `travel_time_s` per **route × weekday × hour** — and
join on those keys. Comparing a single live ping to a multi-year average is
misleading; **average-to-average by hour-of-day is the valid comparison.** A future
`build_json.py` will emit both series (historical baseline + live) on one time axis.

---

## Quick checklist

- [ ] Register trial at move.tomtom.com/register; note the credit allotment shown.
- [ ] Create one Route Analysis job: 10 routes, 6 date ranges, 14 time sets (above).
- [ ] (Low credits? Submit 2019 + 2025 first.)
- [ ] Export CSV + JSON → `Traffic/data/historical/`.
- [ ] Tell me it's exported; I'll wire the aggregator to plot baseline-vs-live.
