# Ottawa election source reconciliation

Checked October 17, 2026. Scope: the mayor and councillor data used by this page for 2010, 2014, 2018 and 2022. School-board races and by-elections are outside the page's scope.

## Result

The original CSV contains **93 ward-year rows**. Comparison with the City workbooks covers **736 populated fields** across **184 available ward/office/year records**:

| Comparison | Fields | Finding |
|---|---:|---|
| Match | 640 | Registered counts, leading candidate names/counts and some valid-vote totals match the City download |
| Ballots used where valid votes were needed | 94 | The input mixed ballots cast with valid candidate votes; derived candidate shares and historical participation were inconsistent |
| Incorrect registered count | 2 | Mayor and council both repeat the same Ward 4, 2014 typo: **22,548 → 22,578** |

These are field counts, not 96 independent transcription errors. The 94 cases mainly reflect a definition/denominator problem. The mayor count discrepancy is also a coverage problem: special polls were absent from ward-coded mayor counts. They must not be interpreted as non-voters.

The normalized extract contains the 184 available ward races, **three unallocated mayor special-poll buckets**, and four citywide mayor controls. Two 2010 council races remain missing. The existing citywide winner and runner-up counts match the City workbooks in every year. All original ward leading-candidate names and vote counts match after normalizing whitespace/apostrophes.

## Primary sources and retained evidence

All workbooks are published by the City's `open.ouvert@ottawa.ca` account. Download URLs, original filenames, SHA-256 hashes, byte lengths, publisher descriptions and retrieval dates are retained in [`reconciliation/source_results.json`](reconciliation/source_results.json).

| Year | City source | Status in this audit |
|---|---|---|
| 2010 | [Elections 2010 results poll by poll](https://open.ottawa.ca/documents/a777b47502a246f79f51daa41c7a542d) | City-published. Its metadata explicitly says it should **not** be considered the official result. Not independently certified here. |
| 2014 | [Statement of votes cast, October 30](https://open.ottawa.ca/documents/1281bd2bdd26477397aad7f2b71d6c0a) | Workbook marked Official Results |
| 2018 | [Ottawa 2018 Election Results](https://open.ottawa.ca/documents/8cb37c0751dc4ce2ae5d92fb5d85cd0a) | Workbook marked Official Results |
| 2022 | [2022 Elections Official Results](https://open.ottawa.ca/documents/ec1423ac43254bff8692fabd5d47772b) | Final workbook, October 28 |

The original project CSV is retained as [`reconciliation/legacy_ward_results.csv`](reconciliation/legacy_ward_results.csv). The full field-by-field comparison, including matching fields and source sheet/total-row references, is [`reconciliation/field_comparison.csv`](reconciliation/field_comparison.csv). This baseline came from repository commit `64afda9e` and is never overwritten on reruns.

Downloaded workbooks are cached outside the repository; they are not rewritten or committed. Re-fetching verifies the original bytes against the retained hashes. A changed publisher file is a new source vintage and requires review.

## Citywide controls

| Year | Registered | Ballots cast | Valid mayor votes | Ballot turnout | Winner votes | Runner-up votes |
|---|---:|---:|---:|---:|---:|---:|
| 2010 | 607,357 | Unavailable | 269,640 | Unavailable | Jim Watson: 131,323 | Larry O’Brien: 64,862 |
| 2014 | 632,385 | 252,464 | 248,369 | 39.92% | Jim Watson: 189,253 | Mike Maguire: 46,341 |
| 2018 | 633,946 | 269,772 | 266,024 | 42.55% | Jim Watson: 188,960 | Clive Doucet: 59,156 |
| 2022 | 722,227 | 316,254 | 314,754 | 43.79% | Mark Sutcliffe: 161,677 | Catherine McKenney: 119,235 |

2010 counts above reproduce the City download's published ward totals and retain its uncertified status. The former chart treated 269,640 valid mayor votes as ballots cast; **44.4% is valid mayor votes / registered, not a verified ballot-turnout figure**.

For 2014, the city summary controls are `summary!A578` and `mayor!A602`. For 2018 they are `Summary!A658` and `Mayor!A649`. For 2022 they are `Summary_résumé!A694` and `Mayor_Maire!A688`. Source references identify row labels; values extend across the row.

## Mayor results by ward: special-vote coverage

The mayor sheets identify polling places, including special polls with precinct code **99**. They do not identify the home ward of every special-poll mayor voter. The council sheets do identify which council race those special votes belong to, but that does not reveal which mayoral candidate those voters selected.

| Year | Ballots in ward-coded mayor polls | Ballots in unallocated 99 polls | Citywide ballots | Valid votes in 99 polls |
|---|---:|---:|---:|---:|
| 2014 | 244,831 | 7,633 | 252,464 | 7,556 |
| 2018 | 253,915 | 15,857 | 269,772 | 15,653 |
| 2022 | 288,694 | 27,560 | 316,254 | 27,376 |

This resolves the apparent 2022 mismatch: **288,694 + 27,560 = 316,254 ballots**. The ward-coded valid candidate votes are **287,378**, and **287,378 + 27,376 = 314,754 valid votes**. Comparing the original 288,694 directly with 314,754 mixed ballots and valid votes.

The revised page:

- Preserves all special votes in citywide totals and an explicit unallocated bucket.
- Labels ward mayor results as **leaders in ward-coded polls**, with percentages of valid votes in those polls.
- Does not claim those are complete home-ward winners.
- Removes the “largest group / didn't vote” mayor map. The incomplete ward mayor counts cannot establish abstention.
- Does not estimate or proportionally allocate the missing mayor votes.

## Denominators and the councillor data

Use these separate definitions:

1. **Candidate share** = candidate votes / sum of valid candidate votes for that race.
2. **Ballot turnout** = ballots cast / registered voters.
3. **Valid council vote participation** = valid councillor votes / registered voters. This is not ballot turnout.

Example, Ward 1 in 2022 (`Ward_quartier_1!A71`): Matthew Luloff received **11,918 / 16,069 = 74.17%** of valid councillor votes (74.2% at the page's one-decimal precision). The former **11,918 / 16,426 = 72.6%** used all ballots, including 352 undervotes and five overvotes. Ballot turnout remains **16,426 / 38,618 = 42.53%**, displayed as 42.5%.

The 2018/2022 council workbooks provide full ward ballot totals, including special votes. Their ward ballots and registered counts reconcile to city totals. The 2014 council sheet gives full valid candidate totals but no full ward ballot count. The 2010 download gives candidate votes, not verified ballots cast. Those older ward ballot-turnout values are now unavailable, rather than silently substituting valid votes.

For 2010/2014 the page initially selects the explicitly labelled valid-vote participation metric. Its history chart keeps that series separate from ballot turnout. An equal-weight ward average remains labelled **Ward average**; it is not citywide turnout.

## Historical boundaries and Ward 24

The [City's ward boundary review](https://ottawa.ca/en/city-hall/public-engagement/projects/ottawa-ward-boundary-review-2020) and [2021-3 by-law](https://ottawa.ca/en/living-ottawa/laws-licences-and-permits/laws/laws-z/ward-boundaries-and-council-composition-law-no-2021-3) establish the ward structure for the 2022 election. The page uses a **2022 locator map**, while historical observations remain attached to original election-year ward numbers.

The former Ward 24 series used 60/40 weights from old wards 3 and 22 without a documented spatial/voter crosswalk. These are not source election results. All pre-2022 Ward 24 vote counts, participation figures and candidate entries are now **null**. No synthetic councillor history is retained.

The contradictory Stonebridge transfer narratives and unsupported direct/minor/renamed classifications have been removed. This audit does **not** certify a historical boundary crosswalk or prove which wards retained identical boundaries. Accordingly, the page withholds **all 2018→2022 ward changes**, including wards that may in fact be comparable. This is a conservative display rule, not a claim that every ward changed. The chart has a break before 2022. A future spatial reconciliation is needed to restore comparable-territory changes.

The map asset has all 24 distinct 2022 ward numbers. No geometry reaggregation or cadastral/vertex-level boundary audit was performed; supporting federal electoral-district files are not election-result inputs.

## Unresolved source gaps

| Gap | Evidence and treatment |
|---|---|
| 2010 official certification | City metadata disclaims official status. Results remain explicitly labelled City-published, not certified. No replacement counts are invented. |
| 2010 wards 7 and 15 council races | Their source tabs contain only mayor data. Council results remain missing. |
| 2010 Ward 6 council source conflict | In `Ward-6`, Shad Qadri's precinct detail sums to **6,571**, but the published total row (`A29`, candidate in column E) is **7,185**. The other candidate and total-valid-vote sums reconcile. The page retains the published total and flags the conflict. It does not choose a corrected candidate count. |
| Older ward ballot counts | Full ballot counts are unavailable for 2010/2014; candidate-vote totals are not used as substitutes. |
| Home-ward mayor votes in special polls | Unallocatable in the supplied workbooks for 2014/2018/2022. Preserved at city level, excluded and disclosed in ward-coded views. |
| Population and under-18 figures | Both [17-10-0155](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1710015501) and [17-10-0152](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1710015201) returned the Statistics Canada “website unavailable” HTML page, even for CSV-download requests. The eight old figures are retained in `reconciliation/legacy_population_estimates.csv` as **unverified**, removed from chart inputs, and the All residents view is withheld. This does not establish that the old values were wrong. |
| Population/list overlap | Even with verified population, subtracting under-18 and registered counts cannot directly measure adults absent from the voters' list, because the dates and populations differ and the list may include non-resident electors. That residual must not be presented as an observed demographic group. |

## Method and reproduction

The reconciliation uses workbook headers and original sheet labels. It checks each modern candidate column and valid-vote/ballot/under-/overvote column by summing actual precinct rows against the independent published total row, skipping cumulative subtotals. It then checks:

- Candidate sums = valid votes for each race.
- 2018/2022 valid votes + undervotes + overvotes = ballots.
- Every mayor candidate's ward-coded votes + unallocated special votes = their city total.
- Mayor ballot buckets = city ballot total; summary precinct registered/ballot counts = summary controls.
- Full 2018/2022 council ward ballots/registered voters = city controls.
- Every available 2010 precinct/candidate column = its published ward total, with the single documented exception above.
- Expected coverage: 23 wards in 2010/2014/2018, 24 in 2022, with two missing 2010 council races.

`assert` failures stop the importer for conflicting official controls; the uncertified 2010 source conflict is recorded explicitly. The importer is a reconciliation tool, not a data collector scheduled elsewhere.

```powershell
python -m pip install openpyxl xlrd
python Ottawa_Elections/ReconcileSources.py
python Ottawa_Elections/BuildWardData.py
python -m unittest discover -s Ottawa_Elections -p "test_*.py"
```

Use `--refresh` to re-download source files. Use `--cache PATH` to select the workbook cache. The retained legacy baseline stays unchanged. `BuildWardData.py` reads the normalized source extract and deterministically rebuilds `ward_results.csv`, `ward_data.json`, `mayor_history.json`, `Ottawa_Summary.csv`, and the two embedded page datasets. It does not regenerate the geometry-only map files.

**Audit completeness:** all available election-result inputs and page calculations have been reconciled to the retrieved City downloads. The gaps above remain unresolved; this is not certification of the missing records, population values, or historical geography.

Validation completed: workbook control checks, six regression tests, inline JavaScript syntax checks, and browser checks of corrected shares, year changes, special-poll warnings, missing Ward 24 history and the 2010 source conflict. The corrected page was visually checked on desktop and at 390 px width. These edits are local until published.
