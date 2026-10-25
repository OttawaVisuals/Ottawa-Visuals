# Election recap image

`ottawa-election-recap.png` (2400 × 1840) is the shareable chart-only image. The SVG preserves editable text. Rebuild with `python Promises/scripts/build_recap_image.py` (requires Matplotlib).

Tax and bus values use the reviewed October 24, 2026 local snapshots. Housing now uses the direct CMHC portal export supplied by the user on October 25, 2026, covering January 2001–September 2026. No extrapolation. The detailed provenance and evidence limitations for tax and bus remain in `Promises/README.md` and the source JSON files. This is a recap of Mark Sutcliffe's 2022 promises and selected outcomes, not a 2026 campaign comparison or causal assessment.

- Tax: adopted overall municipal increases, not individual tax bills. The 2–2.5% pledge was firm for 2023–24 and a target for 2025–26. Inputs: `data/property-tax.json`. [Campaign coverage](https://ottawa.citynews.ca/2022/10/05/sutcliffe-reveals-plan-to-hold-property-tax-increase-between-two-and-25-per-cent-for-2023-and-2024-if-elected-mayor-5914445/); outcome source URLs are retained per year in the JSON.
- Housing: gross new-construction completions in Ottawa city, not permits, starts or net stock change. Full years 2023–25; 2026 is January–September only and visually hatched. 10,000/year is 100,000 divided by 10, an illustrative pace rather than a promised annual milestone; its line covers only full-year bars. No affordable-housing pledge score inferred. [Original campaign ad, p. 34](https://glebereport.ca/wp-content/uploads/2022/10/Glebe-Report-October-14-2022.pdf). Outcome input: `../data/cmhc-ottawa-completions-2026-09.csv`, an unchanged copy of the user's `TableExport (2).csv` from the [CMHC Housing Market Information Portal](https://www03.cmhc-schl.gc.ca/hmip-pimh/#TableMapChart/3506008/4/Ottawa%20(CV)%20(Ontario)). Title: **Ottawa (CV) — Historical Completions by Intended Market**; **Dwelling Types - All**; source footer: **CMHC Starts and Completions Survey**. The `All` column sums homeowner, rental, condo and co-op units, not permit records. Aggregate by calendar year; do not add the component columns again. CP1252 encoding retained. The website's older housing snapshot is not modified by this image-specific source replacement.
- Bus: published annual results, 2023–25. Missing 2023 regularity is labelled, never filled with zero. No monthly/annual averaging or mixing. Punctuality means major-stop departures between one minute early and five minutes late on less-frequent routes. Regularity measures spacing on frequent routes. Reference lines are official KPI targets from the 2026 scorecard, not numerical promises from the 2022 campaign. The 99.5% service target is due Q4 2027; a regularity target date is not established. Inputs: `data/bus-reliability.json`. [2026 scorecard, p. 4](https://pub-ottawa.escribemeetings.com/filestream.ashx?DocumentId=312626#page=4), [2025 roadmap, p. 4](https://pub-ottawa.escribemeetings.com/filestream.ashx?DocumentId=229827#page=4).

All bar charts start at zero. Data labels use the source precision. No overall promise score is assigned. Sources are kept here to preserve the requested titles-and-charts-only image.

## Direct CMHC reconciliation (October 25, 2026)

| Period | Direct CMHC completions | Previous image | Result |
|---|---:|---:|---|
| 2023 | 7,890 | 7,890 | Match |
| 2024 | 8,794 | 8,794 | Match |
| 2025 | 7,797 | 7,797 | Match |
| Jan–Aug 2026 | 5,559 | 5,559 | Match at the same cutoff |
| Sep 2026 | 274 | Not included | Newly supplied month |
| Jan–Sep 2026 | 5,833 | Not included | Updated image total |

Renderer validation: all 309 months from January 2001 to September 2026 are present exactly once; four market components reconcile to `All` in every month; annual and matched-cutoff figures above are checked before rendering.
