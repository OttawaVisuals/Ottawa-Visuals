# Tax — taxing the top in Canada

Page: [`tax.html`](tax.html). A century of Canada's top income-tax rate (federal +
Ontario) set against three questions:

1. When the top rate was high, did the top 1% take a smaller share of income?
2. Did the bottom 50% / middle 40% do better in those years?
3. Who funds federal politics, by neighbourhood income? Can the top rate be linked to donations?

Plus a wealth section (no estate tax since 1972, capital-gains inclusion history, PBO
wealth-tax costing) and an Ottawa lens.

**Scope note:** national/federal data, like `GovContracts/`, with Ottawa pulled out
where the source allows (StatCan Ottawa CMA rows, Ottawa FSAs).

## Layout

```
Tax/
  tax.html                      the page (reads data/tax.json)
  data/tax.json                 everything the page draws (~70 KB, committed)
  data/sources/                 small hand-extracted tables (committed)
    saez_veall_F1_marginal_rates.csv   marginal rates by percentile, 1920–2000
    saez_veall_F2_average_rates.csv    average tax rates of top groups, 1920–2000
    top_rate_2001_2026.csv             statutory fed+ON top rate, 2001–2026
  data/raw/                     downloads, gitignored (~200 MB)
  scripts/aggregate_contributions.py   Elections Canada 2.2 GB CSV → year×party×FSA
  scripts/build_data.py                everything → data/tax.json
```

## Rebuild

Downloads go in `Tax/data/raw/`:

| File | From |
|---|---|
| `WID_data_CA.csv`, `WID_metadata_CA.csv` | WID.world bulk zip (`https://wid.world/bulk_download/wid_all_data.zip`, 880 MB). Only the two `_CA` files are needed; they were pulled with HTTP range requests rather than downloading the whole zip |
| `statcan_11100055.zip` | `https://www150.statcan.gc.ca/n1/tbl/csv/11100055-eng.zip` (high-income tax filers) |
| `ec_contributions.zip` | `https://www.elections.ca/fin/oda/od_cntrbtn_audt_e.zip` |
| `cra_fsa_2021_tbl1a.csv` | `https://www.canada.ca/content/dam/cra-arc/prog-policy/stats/individual-tax-stats-fsa/2021-tax-year/tbl1a-en.csv` |
| `saez_veall_oup07_canada.pdf` | `https://eml.berkeley.edu/~saez/canada-oup.pdf` (source of `data/sources/saez_veall_F*.csv`) |

Then:

1. Filter the 790 MB StatCan CSV to Canada / Ontario / Ottawa-Gatineau rows →
   `raw/statcan_11100055_canada_on_ott.csv` (pandas, chunked on `GEO`).
2. `python Tax/scripts/aggregate_contributions.py` (about 5 min).
3. `python Tax/scripts/build_data.py`.

## Method notes and traps

- **Statutory vs paid.** The famous 80–95% rates applied only around the top 0.001%.
  Saez & Veall Table F1 shows the 99th-percentile marginal rate was 22% in 1950. The page
  leads with the *average rate actually paid* (F2 to 2000, then StatCan 11-10-0055, top 1%
  ranked by total income incl. capital gains). The two sources agree within about 1 pt at
  the 2000/2001 splice but diverge by about 4 pts in the early 1980s (different ranking/income
  definitions), so the splice is at 2000, not 1982.
- **Before 1972** the federal rate already included provincial tax (tax-rental / abatement
  agreements). From 1972 it's federal + Ontario incl. surtax. The Ontario Health Premium is excluded.
- **WID bug:** `aptinci992` for `p50p90` (middle 40% average) is about 4× too high: it looks
  like a sum, not a mean. All group averages are derived as share × overall average ÷ group size.
- **WID pre-1980 bottom/middle split is modelled**: bottom-50 and middle-40 grow at
  identical rates 1950–80 by construction. Treat as indicative. Top shares (tax records) are solid.
- **WID wealth before 1980** is sparse and imputed, so it's dropped.
- **StatCan sub-national rows use the national thresholds.** "Ottawa top 1%" means Ottawa
  filers above Canada's top-1% line (1.12% of Ottawa filers in 2023), not Ottawa's own top 1%.
- **Donations:** individuals only; 2019–2023 (the audited file lags, so 2024+ is incomplete).
  Elections Canada itemizes donors only above $200. About 20% of dollars have no postal code
  and are excluded from the FSA join. Postal codes can be office addresses (K1P downtown Ottawa
  is an outlier for that reason). FSAs under 500 filers are dropped. Deciles are filer-weighted.
  "Gifts" counts itemized contribution rows, not unique people.
- **Correlations are descriptive.** One country, about 5–6 real policy regimes. The page says so.
