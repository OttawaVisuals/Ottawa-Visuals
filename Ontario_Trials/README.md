# How Ottawa court cases end

Page: [courts.html](courts.html). Official-source snapshot reviewed **October 23, 2026**. Static HTML, CSS and JavaScript; no chart library or backend.

The [Traffic court tab in How Ottawa Really Moves](../Traffic/stops.html?section=court)
reuses this snapshot and `model.js` for calendar-year HTA offences, outcome filters
and camera-issued/completed context. It does not duplicate or independently refresh the data.

An [s.53 judgment-search pilot](research/S53_PILOT.md) records published-decision
searches, verified comparison cases and the limitations of linking judgments to
these aggregate statistics. It does not change the outcome totals.

## Coverage

[Ontario Court of Justice statistics](https://www.ontariocourts.ca/ocj/statistics/) are the sole data source. The importer discovers links from that page rather than inventing historical URLs.

| View | Publications | Unit and location |
|---|---|---|
| Criminal | 2012–2026; PDF 2012–2019, XLSX 2020 onward | All criminal cases, including youth, at the Ottawa OCJ location |
| Provincial and traffic offences | 2015–2026; PDF 2015–2019, XLSX 2020 onward | Charges under POA Parts I and III, Ottawa City; statute totals and Highway Traffic Act offence details |

**27 source publications, 903 extracted subject-period rows.** Each row preserves its URL, sheet/PDF page, table/worksheet row and source-file SHA-256. Source notices and exclusions are retained in the JSON audit. Original files are cached locally and excluded from Git; only the small prepared JSON is published with the page.

## Periods: filenames are not reliable year labels

- The default is **January–December 2025**, the latest indexed calendar year for both views.
- Criminal publication **2020** covers **October 2019–September 2020**. The default calendar chart therefore has an explicit 2020 gap; no substitute is relabelled as calendar 2020.
- Both **2026** publications cover **April 2025–March 2026**. These are complete non-calendar reporting windows, not 2026 YTD.
- Selecting a non-calendar period enables the overlapping-period chart view, with full dates and a warning. Turning that option off returns the chart to calendar periods; the detail cards still refer to the selected reporting period.
- No periods are summed: the non-calendar publications overlap other observations.

## Definitions and grouping

A criminal case is the charges on one Information for one accused, classified by the most serious charge. It is not one charge or necessarily a unique person. OCJ cases disposed include cases committed for trial in Superior Court; “completed” does not necessarily mean a final verdict. Superior Court outcomes are outside this dataset.

Provincial-offence data count individual charges, not cases or people. Part II parking matters are outside this series. Large traffic totals can include automated enforcement; volumes are not adjusted for camera rollout or changes in enforcement.

The chart categories are exhaustive partitions of each source row:

- **Criminal:** guilty pleas (before + at trial date); withdrawn/stayed before trial; withdrawn at trial date; other dispositions (before + at trial date); following a trial.
- **Provincial offences:** prepaid fines; guilty pleas (before + at trial date); guilt after failure to respond/attend; withdrawals (before + at trial date); other dispositions (before + at trial date); following a trial.

Trial-date resolutions can occur without a trial. “Following a trial” does not identify guilty or acquitted outcomes. Before-trial stays and withdrawals cannot be separated. The page does not calculate a full conviction/acquittal rate, reasons for stays, unique accused counts, or any measure of OPS officer conduct.

Percentages use **the published completed count for the same subject and period**. Received and pending are context only. A zero denominator has no percentage. The chart and accessible table share the same derived categories. CSV includes grouped counts and fractional shares, the original component counts, full reporting periods, availability and provenance.

## Reconciliation and actual source issues

The build checks each row in three independent stages: components against before-trial total; components against trial-date-without-trial total; stage totals plus following-trial against completed total. Every extracted row reconciles exactly. It also checks offence-to-group and group/statute-to-overall hierarchies.

**One verified source exception: 2016 POA, PDF page 36.** The printed statute subtotals sum to 76,875 received versus the printed 76,878 overall; 20,824 failure-to-respond findings versus 20,825; 70,785 before-trial completions versus 70,786; 78,535 completions versus 78,536; and 5,068 pending versus 5,070. The original page was rendered and visually checked. The Dog Owners' Liability Act row has blank count cells; the build does not allocate the unexplained residual to it. Overall displays use the printed overall row, with the discrepancy flagged. Unexpected new discrepancies abort the build before replacing output.

Some fully blank statute rows (including that 2016 row) are excluded as unavailable. A rounded “0.0%” received share does not establish zero charges. Within a structurally valid numeric row, omitted count cells are treated as zero only after all outcome totals reconcile; missing rows and periods remain unavailable.

Some XLSX header cells contain `#REF!` or obsolete French template text. The importer uses the English reporting-period cell A5 and the numeric data table; it does not repair source workbooks. Header errors are counted in source metadata. Errors inside a count cell cause extraction to fail.

Offence labels are normalized for whitespace and punctuation, not silently combined across changes in scope. For example, older “Other Federal Statutes” and newer labels explicitly including the Federal Cannabis Act remain separate subject keys. Use the broader group when a consistently named aggregation is needed, and retain the limitations of changing offence mix and legislation.

Pandemic-era source notes warn about ICON data accuracy/reliability. The Ministry collects these figures on behalf of the Court, which does not confirm their accuracy/completeness or endorse interpretations. Newer workbooks also contain reuse/audience language. This is a local build, not a verified public deployment or an assertion of an open-data licence; review that source wording before publishing/reusing beyond the stated audience.

## Reproduce and update

Dependencies: Python with `beautifulsoup4`, `openpyxl` (read only) and `pymupdf`; Node for checks. Original source files are never modified.

```text
python Ontario_Trials/scripts/build_court_data.py --refresh
node --test Ontario_Trials/scripts/test_outcomes.cjs
```

Omit `--refresh` to rebuild using ignored `.cache/` files. The script writes atomically only after all sources validate. Network/format failures remain errors, not zero rows. No automatic schedule is configured. Before refreshing the published snapshot, review changes in periods, source definitions, coverage, category names and hierarchy discrepancies. Update expected coverage checks and the homepage takeaways when the source changes.

Serve the repository over HTTP for preview: browser `fetch` cannot read the JSON through `file://`. Shareable query parameters preserve dataset, reporting period, subject, count/share mode and overlapping-period inclusion. A failed data load exposes a retry and official-source link. Light/dark/colour-blind controls use the shared site theme.

## Validation

Eight Node checks cover all row partitions/provenance, independently inspected 2025 totals, calendar/overlap separation, offence selection without subtotal duplication, absent rows versus zeros, the explicit 2016 exception, valid share denominators and source-linked CSV. Non-zero percentages below 0.1% display as `<0.1%`; zero denominators display as unavailable. The full Python extraction validates all 903 rows and the hierarchy checks described above.

Browser QA: both datasets, offence/period selection, share/count mode, selecting a chart year, overlapping-period labels, genuine zero completions versus unavailable rows, URL filter restoration, expandable source details, and light/dark/colour-blind themes. An actual downloaded provincial-offence CSV was parsed and its 2025 counts, grouped share and original-source URL checked. Layout visually checked in 320px, 390px and 1160px iframe viewports and the approximately 804px main preview. No real-device test was performed. Local links, HTML IDs and browser/homepage JavaScript syntax were checked.
