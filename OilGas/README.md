# OilGas — Canada's oil & gas industry: profits, tax, jobs

Page: [`oilgas.html`](oilgas.html). Net profit, dividends, federal + provincial corporate
income tax and payroll employment for Canada's oil & gas extraction industry, 2002–2025,
in inflation-adjusted dollars.

**Scope note:** national data (like `Tax/` and `GovContracts/`), with Alberta and the other
producing provinces broken out for jobs.

## Layout

```
OilGas/
  oilgas.html               the page (reads data/oilgas.json)
  data/oilgas.json          everything the page draws (~20 KB, committed)
  data/raw/                 cached StatCan API responses, gitignored
  scripts/build_data.py     StatCan WDS API → data/oilgas.json
```

## Rebuild

```
python OilGas/scripts/build_data.py
```

Pulls from the StatCan Web Data Service (no key). Responses are cached in `data/raw/`;
delete that folder to force a fresh pull.

| Series | StatCan table | Notes |
|---|---|---|
| Revenue, net income, dividends, payroll cost, corporate income tax | 33-10-0500-01 (annual, 2002–latest) | NAICS "Oil and gas extraction and support services" |
| Latest year(s) not yet in the annual table | 33-10-0225-01 (quarterly) | Only full years are used, flagged `from_quarterly` |
| Employees | 14-10-0202-01 (SEPH, annual) | NAICS 211 extraction + 213 support activities |
| Inflation | 18-10-0005-01 (CPI all-items, Canada) | Page converts to latest-year dollars |

## Method notes and traps

- **Quarterly vs annual.** The quarterly table's yearly sums run 1–5% above the annual
  table (2022–2024: revenue +3 to +5%, net income −1 to +5%). Both are in
  `finance_overlap_check` in the JSON. The quarterly figure is used only for years the annual
  table doesn't cover yet.
- **Losses are mostly write-downs.** 2015–16 and 2020 net losses are mostly impairment
  charges on asset book values, not cash losses.
- **Royalties aren't in "tax".** Provincial royalties are a business expense in these
  statistics, so they're subtracted before profit and don't appear in the corporate income
  tax series. They're the main government take, which is why the page says so.
- **NAICS 213 includes mining support.** SEPH doesn't split support activities between oil &
  gas and mining. In Alberta it's almost all oil & gas; nationally it's a slight overcount.
- **Pipelines (NAICS 486)** are suppressed in SEPH after 2002, so they're left out.
- **Industry boundary.** StatCan classifies each enterprise by its main activity. An
  integrated company's refining may sit in "Petroleum and coal product manufacturing".

## Still to do

Government money in and out, as sourced and labelled estimates: provincial royalties,
federal support (Trans Mountain, CCUS tax credit, EDC financing, 2020 site-rehab program),
Alberta support (Keystone XL, Sturgeon refinery, orphan wells), and independent tallies
(Environmental Defence, IISD, Auditor General 2023).
