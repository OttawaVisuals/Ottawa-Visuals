# Ottawa Police: complaints and discipline

Page: [ops.html](ops.html). Source snapshot reviewed **October 23, 2026**.

## What is counted

- **23 unique named OPS respondents** in published disciplinary decisions.
- **18 officers** with at least one reviewed finding/admission of misconduct.
- **20 proceedings** with decisions; **24 officer–case entries**.
- **2 additional officers** on OPS's upcoming-hearing schedule, shown separately.
- **6 officer–case entries** ended without a misconduct finding. Kirk Batson appears in both a not-guilty proceeding and a separate proceeding with a finding, so outcome officer counts overlap.

These are counts of this collection, **not all OPS complaints, all discipline, currently employed officers, or a misconduct rate**. A proceeding may cover several incidents or counts. Do not describe the 23 officers as “officers disciplined.”

## Sources and method

The manually curated [data/records.json](data/records.json) is the page's source of truth. Each officer–case entry has stable officer/case IDs, latest substantive decision date, outcome, broad subject, penalty, incident period when established, appeal caveat, original links and page/paragraph references.

Reviewed sources:

1. [LECA legacy hearing directory](https://leca.ca/results-hearings/?wbdisable=true): 17 OPS rows, 16 named officers. LECA describes this as public-complaint hearings under the former Police Services Act, including pre-April 2024 incidents. Linked PDFs reviewed for findings and penalties; scanned operative sections visually checked.
2. [OPAAC discipline](https://www.policearbitration.gov.on.ca/police-discipline-decisions-rights-2/): four Ottawa matters, 25-007 (Jay), 25-008 (Fortin), 26-013 (Rabiha-Stevens), 26-028 (Hart). Official decision summaries reviewed. Hart cross-checked with OPS's published settlement and consent order.
3. [OPAAC PSA appeals](https://www.policearbitration.gov.on.ca/en/): Fournier (25-009) and Beric (26-019). Official summaries reviewed; motion and appeal consolidated by proceeding.
4. [OPS decisions and schedule](https://www.ottawapolice.ca/en/newsroom/disciplinary-hearings-and-decisions/): Hart (duplicate), Grus disposition, Reesor and Patterson scheduled matters. Upcoming dates are as listed on the review date; no unverified allegation details assigned to scheduled matters.

OPAAC pages/PDFs were reviewed using web access. Direct Python requests to its directory returned HTTP 403 during this session. The source-discovery helper therefore may require manual browser follow-up. No access failure was interpreted as zero cases.

Names in comparator citations, witnesses, prosecutors and adjudicators are excluded. We do not expand cited historical cases into new entries without reviewing their actual source documents. No independent archive/news inventory is used as evidence for findings. Preserve redactions and omit complainant identities and unnecessary personal/medical details.

## Reconciliation decisions

- Robertson/Thebault share one proceeding and were both found not guilty (signed September 18, 2018; filename differs).
- Batson/Lafreniere's shared 2016 unlawful-arrest proceeding is separate from Batson's 2014 rooftop-force acquittal. LECA's Batson rows cross-link those documents; document contents control grouping.
- Svidran/Wilson/Plomp form one proceeding; dismissals confirmed on appeal. Appeal PDF released December 29, 2017, not directory date June 15. Svidran's signed hearing decision is July 11, 2016, despite directory/filename April date. “Katharine” Plomp in LECA is normalized to “Katherine” from the decisions.
- Alden appeal dated November 18, 2013, not directory date October 23.
- Thomson signed decision dated May 24, 2018, not directory date March 24.
- Fournier penalty appeal decision June 6, 2025, not April 11 (the hearing date in the directory). The official summary and decision filename agree. Underlying misconduct finding January 22, 2024; penalty March 21, 2024. Appeal is not a new case.
- Belanger and Michael Bond dates come from the LECA directory because their decision dates were not established from PDF text. Do not imply all dates were independently verified.
- Grus: finding March 25, 2025 as described in the August 18, 2026 disposition; page uses the later disposition date. Later appeal status not established from the reviewed official directories. Do not call this unappealable or a confirmed final court outcome.

## Visual and filters

Headline cards cover the full collection. Search, outcome and latest-decision-year filters affect the annual chart, table and CSV only. Filters are shareable through URL parameters. The chart counts unique officers per outcome/year using the latest substantive decision in each officer's case, including appeals; it **does not** show first-finding years, incident years, complaint volume or all disciplinary activity. Annual counts cannot be summed for a unique-officer total. Empty years are labelled collection gaps rather than zero misconduct. Scheduled hearings have no decision year and are excluded.

## Updating

Manual snapshot; no scheduled publication or automatic classification.

```text
python OPS/scripts/discover_records.py
node --test OPS/scripts/test_records.cjs
```

Discovery writes ignored `.cache/discovery.json`, never the curated dataset. Errors remain explicit and return a nonzero exit code. Check all four sources, including later appeals affecting older cases. Read the underlying decision or official summary, establish officer identity and case linkage, record source/page evidence, and then edit `records.json`. Keep unknown dates/appeals explicit. Increment `checked_on` only after completing the manual review, and update documentation counts and homepage takeaways if changed.

Serve the repository over HTTP; `file://` cannot load the JSON. No chart/map library or backend is required. Shared typography/theme uses the existing site assets and Google Fonts.

## Validation

Six Node checks cover unique officers/proceedings, shared cases and separate outcomes, corrected appeal dates, annual deduplication and gaps, combined filtering/CSV evidence, and source/date invariants. Python discovery script and browser JavaScript pass syntax checks. Browser checks confirmed the homepage tile, search, combined filters/no-match state, query-string restoration and all three theme modes. Layout visually checked at approximately 804px and in a 390px iframe viewport (header, totals and filters). Phone table horizontal scrolling is provided by a labelled container; no real-device test was performed.
