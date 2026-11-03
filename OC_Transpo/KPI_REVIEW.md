# OC Transpo KPI review — November 3, 2026

The three unusual Line 1 monthly figures are confirmed in staff presentations.
The historic values remain unchanged. Snapshot provenance now correctly names
`.xlsx` files, rather than nonexistent `.pdf` files. Newer bus measures are shown
separately because their definitions differ.

## Scope and checks

- Rebuilt the archive: **1,218 observations → 932 series points**, byte-for-byte
  reproducible after the provenance fix. Unique keys, nonnegative levels and
  percentage-share ranges checked; the negative ridership change is legitimate.
- Independently reconciled **all 104 snapshot values** to workbook cells, with
  period, metric, unit and million/thousand scaling checks.
- Checked all source pages for the **six differing series keys**, including
  table-column context and the explicit meeting-count correction below.
- Compared the three unusual Line 1 cells with separately published slides;
  visually inspected each endpoint and its month label.
- Extracted **43 printed observations** from the October staff PDF; inspected
  month alignment and preserved printed totals, including rounding differences.
- This is a targeted source review, **not** a fresh cell-by-cell audit of all
  historical PDF observations. Deterministic reproduction alone cannot establish
  that every original extraction is correct.

Reproduce (requires `openpyxl`, `pypdf`, the scraper's retained PDF/text/table
archive, and the committed spreadsheets):

```sh
python OC_Transpo/scripts/extract_kpis.py
python OC_Transpo/scripts/review_kpis.py --check-current
```

The review downloads four hash-pinned staff PDFs to ignored `data/kpi_review/`.
If a source hash changes, it stops for review. It writes
`kpi_history/source_review.json`, `recent_publications.csv` and, with
`--check-current`, `workbook_source_check.json`. The first JSON contains original
document URLs, page numbers, values and SHA-256 hashes for the differing figures.
The CSV uses separate metric names and is not merged into the historical series.

## Line 1

| Month | Trips delivered | Corroborating staff presentation | PDF page |
|---|---:|---|---:|
| Jan 2026 | 87.8% | [February 12](https://glengower.ca/wp-content/uploads/2026/02/5.1-OC-Transpo-Update-Feb-12-2026-TC_EN.pdf#page=28) | 28 |
| Feb 2026 | 67.2% | [March 12](https://glengower.ca/wp-content/uploads/2026/03/4.1-OC-Transpo-Update-March-12-2026-TC_EN.pdf#page=31) | 31 |
| Mar 2026 | 61.8% | [April 9](https://glengower.ca/wp-content/uploads/2026/04/6.1-OC-Transpo-Update-EN.pdf#page=42) | 42 |

These are printed monthly values, not estimates from curve heights. They measure
delivery of planned service; they do not directly measure passenger waiting time.
The slides provide corroboration of publication, not an independent operational
measurement or a quantified causal explanation.

Workbook sheet `05_otrain_service_delivery`, cells C11:C13, matches these values.
Its E2 summary says 98.5% while F2 refers to March 2025. That narrative appears
stale and should not be used to invalidate the monthly cells. The three staff
slides instead print rolling averages of 98.2%, 95.7% and 92.9%, respectively.

The current [Open Ottawa service workbook](https://www.arcgis.com/sharing/rest/content/items/31d7a151c8394d1a8656ea3d08f00f46/data)
download on November 3 was byte-identical to the July 11 retained copy, covering
April 2025–April 2026. SHA-256:
`cde2dda2bc5d2af9ae678a47d647ff63c8ce83dc71a631efb72c11f2f536b481`.
This says nothing about collector health or whether other publications are newer.

## Six differing historical figures

| Measure / period | Retained | Other published value | Finding |
|---|---:|---:|---|
| Bus operator availability, 2024 | 85% | 88% | Both scorecards say 85%; September 2025 reliability narrative says 88%. Latest scorecard retained; disagreement unresolved. |
| Open-data API calls, Dec 2020 | 62,736,000 | 60,736,000 | Later table retained. Reason for change not stated. |
| Website pageviews, Jan 2021 | 200,000 | 198,000 | Later table retained. Reason for change not stated. |
| Line 1 service availability, 2020 | 95.2% | 95.6% | Same-report chart/table disagree. Later rounded 95% agrees with 95.2% under the existing rounding rule; unresolved. |
| System service availability, 2020 | 98.2% | 98.3% | Same-report table/chart disagree. Existing table priority retained; unresolved. |
| Staff survey review meetings, 2023 | 32 | 132 | Explicitly corrected: 2025 scorecard p2 footnote says the earlier 132 was erroneous and 32 is correct. |

Page-level links and every observed value are in the page's expandable source
table and `source_review.json`. These selection rules preserve provenance; they
do not adjudicate unresolved source contradictions. The rounded 95% observation
is retained in the evidence but is not labelled a conflicting value because it
agrees within published rounding.

## Newer publication and definition break

[October 14 staff KPI PDF](https://glengower.ca/wp-content/uploads/2026/10/Transit-KPIs-October-2026.pdf),
hosted on Councillor Glen Gower's site:

- Page 1: scheduled bus **trip starts** within −1/+5 minutes, with missed trips
  counted as not on time. Only September 2025 and September 2026 endpoint labels
  are extracted; the intervening curve has no exact labels.
- Page 2: 13 months of printed missed-trip totals and two components, September
  2025–September 2026. This broader measure includes trips not run, no origin
  departure, over 20 minutes late, and started but incomplete service.
- Page 4: two labelled Para eligible-pickup endpoints using a 30-minute window.
  Kept in this recent-publication snapshot, without filling intervening months.

The new bus trip-start measure cannot extend the older less-frequent-route
major-stop punctuality curve. The broad missed-trip measure cannot be converted
to the legacy trips-delivered percentage by subtracting it from 100. Printed
totals differ from the sum of components by up to 0.1 percentage point; no totals
were silently recalculated. The source's component labels are preserved.

## Remaining limits

Historical gaps remain blank, and annual totals are still withheld unless all
12 months or an official annual total are available. Service hours, trips,
on-time definitions and our live prediction samples remain separate. This review
does not claim that September is the latest result available anywhere, nor that
all subsequent committee attachments have been ingested. Future source decks
need reviewed extraction specs; unlabeled curves cannot supply exact values.

## Page verification

Six browser cases passed: 320px and 1280px in light, dark and colourblind themes.
The updated project tracker passed the same six cases (12 cases total).
No page errors, horizontal page overflow or automated WCAG A/AA violations were
detected. Local file links resolved; the shared skip-link target is generated at
runtime and was verified in the DOM. New source-table links carry PDF page anchors.
Phone and desktop screenshots of the new section were visually inspected.

Browser assertions checked all 13 new missed-trip totals, both distinct September
2025 punctuality definitions, the latest displayed endpoint values, six expanded
source rows, preserved missing-month nulls and `spanGaps: false`, theme redraws,
and the new CSV download. A numerical comparison with the previous committed
historical CSVs confirmed that only the 104 snapshot source-file extensions
changed in each file. No actual screen-reader application was tested.
