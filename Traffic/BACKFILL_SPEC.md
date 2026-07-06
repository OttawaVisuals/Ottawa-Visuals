# Historical backfill spec — TomTom MOVE / Traffic Stats 30-day trial

**Goal:** pull historical average commute times for the *same 5 corridors* the live
poller tracks, as a baseline that predates live collection, then let the live
pipeline extend the series so we can chart the return-to-office commute trend.

This is a **one-time export** from a *different* TomTom product than the live APIs:
[MOVE / Traffic Stats](https://www.tomtom.com/products/traffic-stats/), **Route Analysis** tool.
Trial registered at <https://move.tomtom.com/register>.

---

## ⚠️ Actual trial limits (confirmed on this account)

- **Expires 2026-08-05** (~30 days).
- **20 reports** total, **max 3 in progress** at once.
- **Date window is August 2024 ONLY** (2024-08-01 → 2024-08-31). The full 10-year
  archive is a paid feature; the trial exposes just this one recent month.
- Route length ≤ 200 km.

**So the multi-year 2019→2025 plan is not possible on the trial.** Instead we pull
**August 2024** as a single baseline and compare it to **August 2026** live data
(same month = seasonality controlled; brackets the Sept 2024 3-day RTO mandate).

⚠️ **August is a vacation month** (light traffic, esp. Ottawa's federal workforce).
Always frame this as *August-to-August*, never "August 2024 = typical 2024."

**How reports map to our plan:** a Route Analysis report should accept multiple
routes/date-ranges/time-sets (the API allows ≤20 routes, ≤24 date ranges, ≤24 time
sets per job). Try **one report with all 10 routes**; if the UI restricts to one
route per report, submit **10 reports** (still within the 20-report budget, 3 at a
time). Either way this uses ≤10 of 20 reports — plenty of headroom to re-run.

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

## 2. Date range (August 2024 — the only window the trial exposes)

| Range name | From | To | Notes |
|---|---|---|---|
| 2024_aug | 2024-08-06 | 2024-08-30 | Skips the **Aug 5 Civic Holiday** (Ontario stat holiday); 4 clean weekday weeks |

Weekend filtering is handled by the weekday time sets below. Using Aug 6–30 (rather
than the full month) drops the holiday Monday so it doesn't drag the Monday average.

**Comparison target:** aggregate **August 2026** live data the same way (weekdays,
same hours, exclude the 2026 Aug Civic Holiday = Aug 3) and compare Aug-to-Aug.

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
  "jobName": "ottawa_aug2024_baseline",
  "distanceUnit": "KILOMETERS",
  "mapVersion": "current",
  "routes": [
    { "name": "kanata_to_downtown", "start": {"latitude": 45.3088, "longitude": -75.8987},
      "end": {"latitude": 45.4215, "longitude": -75.6972}, "followRoads": true, "zoneId": "America/Toronto" }
    /* ... the other 9 routes from the table above ... */
  ],
  "dateRanges": [
    { "name": "2024_aug", "from": "2024-08-06", "to": "2024-08-30" }
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
`route_analysis_2024_aug.csv` plus the raw JSON response.

To compare baseline vs live cleanly, aggregate the **live** CSVs the same way
Traffic Stats reports — average `travel_time_s` per **route × weekday × hour**,
restricted to **August 2026 weekdays** — and join on those keys. Comparing a single
live ping to a monthly average is misleading; **average-to-average by hour-of-day,
August-to-August is the valid comparison.** A future `build_json.py` will emit both
series (2024 baseline + 2026 live) on one hour-of-day axis per corridor.

---

## Deep history (2019–2023) needs paid access

The trial caps at August 2024. To reach the pre-COVID / peak-WFH years, either a
**paid Traffic Stats plan** (ask movesupport@tomtom.com about research / non-commercial
pricing) or **coarser free fallbacks** — City of Ottawa open-data traffic counts,
StatCan — which give *volume*, not travel time (different metric). Not blocking; the
Aug-2024-vs-Aug-2026 comparison stands on its own.

---

## Quick checklist

- [x] Register trial (done). Limits: 20 reports, Aug 2024 only, expires 2026-08-05.
- [ ] Create Route Analysis report(s): 10 routes, date range 2024-08-06→30, 14 time sets.
- [ ] Export CSV + JSON → `Traffic/data/historical/`.
- [ ] Keep the live poller running through **August 2026** for the same-month comparison.
- [ ] Tell me it's exported; I'll wire the aggregator to plot 2024-baseline-vs-2026-live.
