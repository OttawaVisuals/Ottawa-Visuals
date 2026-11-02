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

## Classes above references

The threshold section counts source rows above seven provincial/ETFO references and two OECD averages from 2019–20 to 2025–26 for Ontario and the four boards. These are **screening flags, not confirmed violations**. Provincial individual caps, conditional/share rules and dated ETFO proposals stay separate. Numeric references are held constant across the graph; this is not a reconstruction of each year's official compliance findings. Categories overlap and must not be summed.

- Primary eligibility: grades 1–3 present, optionally with JK/K, and no grades 4–8. Count strictly above 20 and strictly above 23 separately. At least 90% at/below 20 permits some classes of 21–23.
- Mixed primary/upper eligibility: JK/K or grades 1–3 present together with grades 4–8; compare the entire class with 23. JK/K is part of the primary division for this screening population.
- Kindergarten-only: compare with 29 and the 32-student exception ceiling separately. Above 29 can be permitted within the board-share rule under specified conditions. Exception approvals/class-property fields are missing.
- ETFO proposals: count JK/K-only classes above 26 and grades-4–8-only classes above 24. These are recommendations in the [2025–26 submission](https://www.etfo.ca/getmedia/84a55402-86e9-46d8-a372-44e9cfaa422b/241112_EducationFundingSubmission.pdf#page=19), not legal individual caps.

OECD comparisons use the published rounded **2024 averages: 21 primary, 23 lower secondary**, from [Education at a Glance 2026, Table D2.3](https://www.oecd.org/en/publications/education-at-a-glance-2026_b4968bbc-en/full-report/how-do-student-teacher-ratios-and-class-sizes-vary-across-education-levels_30c0e06c.html). These are observed averages, not recommended maxima. They remain fixed across the Ontario history. Choose grades 1–8, grades 1–3 only, or grades 4–8 only; all classes containing JK/K are excluded. Count strictly above 21 or 23 using the same suppression bounds. The [Canadian mapping](https://gpseducation.oecd.org/Content/EAGCountryNotes/EAG2023_CN_CAN_pdf.pdf#page=9) places primary in grades 1–6 and lower secondary in grades 7–9. Ontario combines grades 4–8, so no exact grade-level match is claimed. OECD excludes special-needs programmes; unavailable Ontario class-property fields prevent fully matching that population.

Average references (26 for kindergarten; 24.5 for grades 4–8) are a separate table. The upper population includes every class with a grades-4–8 student, including mixed classes. Kindergarten uses all classes with JK/K: numerator = JK/K pupils; denominator = sum of each class's JK/K fraction. For a suppressed mixed class with K in [kl,kh] and other pupils in [ol,oh], its fraction lies in [kl/(kl+oh), kh/(kh+ol)]. The combined mean is conservatively bounded by total K-low / denominator-high and total K-high / denominator-low. No midpoint is imputed. Formal reporting rounds averages to one decimal and uses unavailable class-property fields; no compliance verdict is calculated. Ontario combined averages/shares do not establish board-level compliance.

References: [O. Reg. 132/12, ss. 2–10](https://www.ontario.ca/laws/regulation/120132), [2018–19 reporting requirements](https://efis.fma.csc.gov.on.ca/faab/Memos/SB2018/SB14_EN.pdf) (documents the 29/32, 20/23 and average structure), and the [2025–26 reporting guide](https://efis.fma.csc.gov.on.ca/faab/Memos/SB2025/SB04_Attach_EN_1.pdf). Exception details and historical board provisions can vary. The public file cannot support a legal audit or secondary-school screening.

`thresholds.json` / `threshold-data.js` retain rule definitions, 455 area/year/reference/scope count rows, 70 average rows, input bounds, workbook URLs and source hashes. The count CSV includes the reference label/type and strict-greater-than comparison; average inputs are separate. Existing financial/class-size datasets are unchanged by this extension.

## Rebuild

Python 3; `check_data.py` also uses `openpyxl` for an independent read-only source import. No workbook is authored or changed.

```powershell
python Education/scripts/fetch_sources.py
python Education/scripts/build_data.py
python Education/scripts/check_data.py
python Education/scripts/build_thresholds.py
python Education/scripts/check_thresholds.py
node --check Education/education.js
```

Large originals stay in ignored `data/raw/`; `source-manifest.json` retains URLs, sizes and SHA-256 hashes. To refresh a source, remove only that cached file explicitly and fetch again; catalogue refresh requires removing its cached metadata too. Commit the rebuilt outputs and review changes.

Exports: financial source rows with vectors/coordinates/status; class aggregates with both student bounds and class counts; school-name aggregates; original-row coverage. `education.json` and `page-data.js` contain identical data for HTTP/local-file use. See [QA.md](QA.md) for verification and limitations.
