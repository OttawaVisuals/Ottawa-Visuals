# Mortgage / Housing Affordability Calculator

**Live:** [`mortgage.html`](mortgage.html) (embedded on the homepage as report *Can we afford it?*)

A Canadian mortgage affordability calculator: enter income, down payment and
rate to see your CMHC/OSFI B-20 stress-tested maximum, monthly costs, and
where it lands against Ottawa's benchmark home prices.

## Layout

| Path | Purpose |
|---|---|
| `mortgage.html` | The self-contained calculator page (loads JSON from `JSON/`, no backend) |
| `Static/` | Raw source CSVs/JSON (StatCan census, CREA benchmarks, tax rates, household spending) |
| `Pipeline/build_json.py` | Converts `Static/` inputs into the compact `JSON/` files the page fetches |
| `JSON/` | Committed build output — what `mortgage.html` actually reads (`DATA_BASE = 'JSON/'`) |

## Rebuilding the data

```bash
python Mortgage/Pipeline/build_json.py
```

Run from the repo root; it reads `Static/` and (re)writes `JSON/`.

## Method

Qualifying uses OSFI B-20 rules: GDS ≤ 39% and TDS ≤ 44% at the greater of your
rate + 2% or 5.25%. Ottawa MLS benchmark prices (CREA HPI) run 2005–present,
inflation-adjusted with Statistics Canada CPI.
