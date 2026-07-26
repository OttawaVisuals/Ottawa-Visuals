# RTO4 — the return-to-office page

The external-data half of [`/rto.html`](../rto.html) ("Ottawa RTO Watch"). Our own
live collection lives in [`Traffic/`](../Traffic/README.md) and
[`OC_Transpo/`](../OC_Transpo/README.md); this folder holds the fetchers for
everything published by somebody else, plus the small aggregate JSON the page loads.

**Context:** on Mon Jul 6, 2026 the federal public service went to four days a week
in the office, phased to Sep 15. See [`../RTO4_PLAN.md`](../RTO4_PLAN.md) for the
policy timeline and the full data inventory.

## Layout

```
RTO4/
  scripts/
    common.py         shared fetch/aggregate helpers + a minimal stdlib xlsx reader
    fetch_311.py      311 service requests   -> 311_weekly.json
    fetch_ieso.py     IESO Ottawa-zone load  -> ieso_ottawa_weekly.json
    fetch_bikes.py    bicycle counters       -> bike_weekly.json
    fetch_ghg.py      GHG inventory          -> ghg_inventory.json
    fetch_context.py  volumes + collisions   -> context_annual.json
    refresh_all.py    runs all of the above
  data/               the committed aggregates the page fetches
```

Everything is stdlib-only, matching `Traffic/scripts/poll_traffic.py` — no
`pip install`, so it runs identically on a laptop and on the Pi.

## Refreshing

```bash
python RTO4/scripts/refresh_all.py
```

Or one at a time: `python RTO4/scripts/refresh_all.py 311 ieso`.

Fetchers are independent and a failure never aborts the batch — the City renames
and retypes its ArcGIS layers between vintages often enough that partial success
is normal. Suggested cadence:

| Fetcher | Cadence | Why |
|---|---|---|
| `311` | weekly | Daily source, and the one series with a real 2025 baseline |
| `ieso` | weekly | Current-year CSV grows hourly |
| `bikes` | monthly | Coverage currently ends Mar 2026; re-run to catch an extension |
| `ghg` | yearly | Annual publication |
| `context` | yearly | Annual publication, or when a 2025/2026 volume edition appears |

**The aggregates are committed.** They are small, and committing them means the
static page needs no build step and no server. Never commit the raw sources — the
two 311 CSVs alone are 70 MB.

## What each dataset can and cannot prove

The page states these limits inline; they are repeated here because they are the
reason to trust or distrust each chart.

| Dataset | Resolution | History | Speaks to RTO4? |
|---|---|---|---|
| 311 service requests | daily → weekly | 2025 + 2026 | **Yes** — the only external series with a genuine same-week 2025 control |
| IESO Ottawa-zone demand | hourly → weekly | 2003+ (we pull 2023+) | **Yes**, weakly — whole zone and weather-dominated, so read the weekday÷weekend ratio, not MW |
| Bicycle counters | daily → weekly | 2010–**Mar 2026** | **No** — coverage ends before Jul 6, and only ADAWE still reports in 2026 |
| Intersection / midblock volumes | annual | 2018, 2022, 2023, 2024 | **No** — no 2025 or 2026 edition published |
| COVID-19 intersection monitoring | monthly, % of normal | 2020–22, closed | **No** — included as the yardstick for what a real step change looks like |
| Collisions | annual | 2017–2024, **2023 missing** | **No** — context only |
| GHG inventory | annual, city-wide | 2012–2024 | **No** — latest year predates RTO4 by 18 months |

Two traps worth restating:

- **Volume counts:** the surveyed site list changes every edition, so compare
  *median per site*, never totals. 553 sites in 2018 vs 703 in 2024 is a survey
  change, not traffic growth.
- **Bike counters:** the reporting counter set shrinks each year, so the
  cross-year `total` is meaningless. `fetch_bikes.py` emits `counters_reporting`
  and `coverage_end` so the page can say this rather than draw a false decline.

## Datasets checked and rejected

Recorded so the absences stay deliberate:

- **Park & Ride occupancy** — the feed publishes `capacity` but no occupancy
  field (verified 2026-07-25). Would have been an excellent indicator.
- **Ottawa GHG, monthly or by geography** — does not exist; annual city-wide only.
- **Traffic Services webcams** — need a per-request certificate, and images would
  require vehicle counting to become data.

Still outstanding and genuinely valuable: TBS federal headcount for the NCR (the
denominator — how many people RTO4 moves), StatCan work-from-home rates by CMA,
and downtown office vacancy from brokerage reports.

## Related collection

`Traffic/scripts/poll_parking.py` (added with this page) logs municipal
parking-garage occupancy — the most direct office-occupancy proxy available.
It lives in `Traffic/` because `pi_poll.sh`/`pi_push.sh` already carry that
folder's cron and push wiring. Only 5 of 15 lots publish live space counts,
4 of them downtown.
