# Education: funding & class sizes

Page: [education.html](education.html). Static, buildless Ottawa Visuals report. Built locally November 2, 2026; publication pending. Shares the healthcare page layout and site themes. School artwork is an original decorative SVG in the existing navy/teal/amber palette.

## Measures

- **Provincial funding:** StatCan 37-10-0067-01, direct provincial-government source across Ontario elementary/secondary education. It is not a Ministry-budget-only measure or a public/private-recipient split.
- **Public/private financing:** same table; all-government funding versus fees plus other private-sector sources. These sources can fund either school sector.
- **Public/private expenditure:** StatCan 37-10-0066-01. The public series includes public school boards, direct government expenditure, federal schools and other public components. Private-school spending is estimated from enrolment changes from 2006–07 onward, following StatCan's published note. The Ministry says it does not fund private schools; private-school expenditure must not be labelled a provincial subsidy.
- **Price adjustment:** Ontario all-items annual CPI (18-10-0005-01). Average the start/end calendar-year indices and rebase to 2023–24: nominal CAD × (CPI2023+CPI2024)/(CPIstart+CPIend). This is an approximate school-year consumer-price adjustment, not an education cost index. CPI history starts in 1979. Financial methodology changes in 2012–13; chart lines break there. Funding/expenditure accounting totals differ and must not be interchanged.
- **Class sizes:** Ontario Elementary Class Size September records, 2007–08 to 2025–26. Import only one language copy of each workbook (both copies cover all board languages). Sum JK, K, grades 1, 2, 3 and 4–8 cells per row. Average = aggregate enrolment / count of non-empty class rows. Do not average school means or call this a teacher ratio, staffing level or physical-room occupancy.

## Class coverage and privacy

The early workbook has no grades-4–8-only rows before 2014–15. The all-class and upper-grade views therefore start in 2014–15. Earlier kindergarten/primary/mixed rows remain available. Grade groups depend on the presence of students: JK/K-only; grades 1–3-only (including within-band splits); grades 4–8-only; and across-band mixtures.

Recent `<5` cells are interpreted as positive counts below five because zeros are separately published as 0. This suppression-convention assumption gives 1–4 bounds; never substitute a midpoint or inferred exact value. Sum low/high inputs and divide by the same class count. For the descriptive share above 25 students, count certainly-above and possibly-above classes separately. These are suppression bounds, not confidence intervals or legal-compliance judgments. Entirely zero rows are excluded with counts in `class-coverage.csv`; unexpected blank/text cells make the builder fail rather than becoming zero.

Source rows have no school IDs or special-education/class-property fields. Repeated board/school-name/class-number keys are retained in board totals because the release does not distinguish duplicate names/sites. Affected school-year names are flagged `ambiguous_name` and omitted from school lines; they remain in exports and tables for audit. This is conservative: repeated keys may have other causes. Exact-name histories are not stitched across renames. Missing years stay disconnected. Province/board summaries include all source rows, not a verified regulatory-compliance population.

## Ottawa-area scope

OCDSB, OCSB, CEPEO and CECCE are whole board territories; French-language boards span a wider eastern Ontario area. These are not City-of-Ottawa-resident totals. Source long/abbreviated board aliases are retained in `source_board_names` in the JSON. The school selector is a source-name explorer, not a verified stable-ID directory.

Secondary/private-school class sizes, teachers by school and matched spending-per-student denominators are not established in this release. No proxy is substituted. Kindergarten changes, pandemic remote arrangements, reporting coverage and student needs can affect comparisons; the report makes no causal claim about funding and class size.

## Rebuild

Python 3; `check_data.py` also uses `openpyxl` for an independent read-only source import. No workbook is authored or changed.

```powershell
python Education/scripts/fetch_sources.py
python Education/scripts/build_data.py
python Education/scripts/check_data.py
node --check Education/education.js
```

Large originals stay in ignored `data/raw/`; `source-manifest.json` retains URLs, sizes and SHA-256 hashes. To refresh a source, remove only that cached file explicitly and fetch again; catalogue refresh requires removing its cached metadata too. Commit the rebuilt outputs and review changes.

Exports: financial source rows with vectors/coordinates/status; class aggregates with both student bounds and class counts; school-name aggregates; original-row coverage. `education.json` and `page-data.js` contain identical data for HTTP/local-file use. See [QA.md](QA.md) for verification and limitations.
