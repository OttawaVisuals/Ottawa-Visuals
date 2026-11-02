# BC election consolidation

Open [2026 preliminary](BCelections.html), the default, or [2024 final](BCelections-2024.html).

## 2026 preliminary snapshot

The source is Elections BC's initial count for October 24, 2026, with its **“As of October 26, 2026 10:34 PST”** timestamp, retrieved November 1. Final count is scheduled November 6–10 and will add mail-in and absentee ballots. Leads are not certified seats. The page is a saved snapshot, not a live feed.

| NDP/Green transfer | Conservative leads | NDP leads | Green leads | Changed leads |
|---|---:|---:|---:|---:|
| Initial count / 0% | 63 | 28 | 2 | 0 |
| 65% illustrative | 56 | 35 | 2 | 7 |
| 100% | 51 | 40 | 2 | 12 |

Conservatives and every other candidate stay fixed. This is not a ranked-ballot forecast. Outstanding votes can change both the baseline and scenario.

Sources: [party report](https://results.elections.bc.ca/) and [candidate report](https://results.elections.bc.ca/Results_11684_GE-2026-10-24_Candidate.html). Both HTML snapshots are retained. All 353 candidate sums match all 93 riding totals and provincial party totals/leads: 1,795,133 valid votes + 4,417 rejected ballots = 1,799,550 ballots considered. Preliminary turnout is 48.14% using 3,738,182 registered voters as of October 14. Riding registration denominators are unavailable and not inferred. Historical turnout through 2024 is final; the 2026 endpoint is preliminary and the page avoids a completed-election turnout-change claim.

Candidate and scenario CSVs carry year, preliminary status and source timestamp. `data/audit.json` includes the retrieval date, reconciliation and raw-source hashes. To refresh, download both reports together, inspect their timestamp/status, update the explicit snapshot assertions and metadata in `build_preliminary.py`, then run `python BC_Elections/build_preliminary.py` and `node BC_Elections/check_model.cjs`. Do not treat final count as the same initial-count dataset.

2026 verification: all 93 baseline leaders recovered at 0%; all 9,393 whole-percent scenarios, exact boundary ties and separate independent candidates checked. Nine phone/desktop/theme combinations had no marker overlaps or page-width overflow. Browser slider endpoints, missing riding turnout, 2024/2026 navigation and CSV metadata were checked; the 100% scenario export contains 93 preliminary rows and twelve changed leads. Observations are retained in `data/ui-checks-2026.json`.

## 2024 final archive

The October 19, 2024 baseline remains separate, using the published Statement of Votes. The `*-2024.js`, `data/*-2024.json` and `data/candidates-2024.csv` files feed `BCelections-2024.html`. The 2024 builder now writes those archive files, preserving the current 2026 default.

## 2024 method and findings

In each riding, the leading NDP or Green candidate keeps their actual votes and receives the selected share of the other party's votes. Conservatives, independents, unaffiliated candidates and other parties stay fixed. No Liberal/BC United pool is invented. Untransferred votes are unallocated; turnout responses, candidate effects and later preferences are unknown. The 65% default is illustrative. This is not a ranked-ballot simulation or forecast.

| Transfer assumption | NDP seats | Conservative seats | Green seats | Changed seats |
|---|---:|---:|---:|---:|
| Actual / 0% | 47 | 44 | 2 | 0 |
| 65% | 55 | 36 | 2 | 8 |
| 100% | 58 | 33 | 2 | 11 |

A majority is 47 of 93 seats. The eleven reachable Conservative-held seats and exact boundaries are in `data/scenario-checks.json`. Cards show the smallest whole-percent slider value that wins; the table shows the strict boundary to two decimal places. Ties have no assigned winner. Other candidates compete individually, even though the table combines their votes for display. All 93 actual winners are recovered at zero transfer, and both Green-held seats remain Green throughout.

## 2024 sources and reconciliation

- [DataBC voting-place results](https://catalogue.data.gov.bc.ca/dataset/44914a35-de9a-4830-ac48-870001ef8935): retained source CSV, filtered to the 2024 general election. Includes all voting opportunities, including out-of-district and mail voting.
- [Elections BC Statement of Votes](https://elections.bc.ca/docs/rpt/statement-of-votes-2024-provincial-election.pdf): retained original PDF. All 322 candidate counts reconcile to printed pages 5–12. All 93 district party totals, valid/rejected ballots, ballots cast, registered electors and turnout reconcile to pages 13–15. Party totals match page 4. Provincial valid votes: 2,105,341; rejected: 4,317; ballots: 2,109,658.
- [2023 boundary set](https://catalogue.data.gov.bc.ca/dataset/1cba4b16-263f-4d42-8d84-f5fecaa03d1a): all 93 district codes match results. BC Albers / EPSG:3005, simplified by 60 metres with topology preserved. Metro Vancouver and Victoria-area insets show selected districts from the same geometry. Display simplification is not suitable for locating an address.
- [Official turnout history](https://elections.bc.ca/resources/results/voter-turnout/): all eight general elections from 1996–2024. The denominator is registered voters, not all eligible residents. 2024: 2,109,658 / 3,609,288 = 58.45%. Riding turnout is 2024 only; no earlier district values are estimated.

Source URLs, retrieval date and file hashes are in `data/audit.json`. The large original boundary snapshot is kept locally in an ignored gzip; tracked `geo.js` supplies the page without network requests. A fresh fetch may contain different server-generated metadata; original retrieval hashes identify this snapshot.

## Rebuild

1. Fresh clone only: `python BC_Elections/fetch_boundaries.py`.
2. `python BC_Elections/build_data.py` (pypdf, beautifulsoup4, shapely).
3. `node BC_Elections/check_model.cjs`.

The 2024 builder regenerates suffixed archive data/turnout, shared maps, candidate CSV, results JSON and source audit. The preliminary builder updates the default files. Both years are checked by the model checker. For each year, the model check extracts its actual page function and independently checks all 9,393 whole-percent riding scenarios, zero-transfer leaders, exact boundary ties, Green seats and separate independents (18,786 scenarios across both years). No build step is needed to view the page.

Layout uses the shared colour-key component from Ontario/Alberta. Browser checks passed at 320/390/1280 CSS pixels in light/dark/colour-blind themes: no shared marker overlaps or page-width overflow, 93 table rows and 93 map districts. The insets contain 42 Metro Vancouver and six Victoria-area districts. Slider endpoints recover the checked seat totals; flips-only returns zero/eleven rows at 0%/100%; riding selection/reset and name search work. Both 65% and 100% CSV downloads were inspected (93 rows, eight/eleven flips). Browser console had no reported errors. Nine layout/theme observations are in `data/ui-checks.json`. Published November 1, 2026.
