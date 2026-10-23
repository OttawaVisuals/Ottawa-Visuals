# Review of all 133 s.53 search candidates

Reviewed October 23, 2026. Decision-date window: January 1, 2016–December 31, 2025.
This completes the [pilot's](S53_PILOT.md) **retained candidate list**, not a complete
inventory of published judgments or of Ottawa suspended-driving cases.

## Result

**No document in the 133-candidate set establishes an Ottawa HTA s.53 trial verdict.**
This is a finding about these search results, not proof that no such judgments exist.

| Classification | Documents |
|---|---:|
| Explicit s.53 trial conviction — Toronto | 1 |
| Explicit s.53 guilty plea — Pembroke area | 1 |
| S.53 procedural ruling without a verdict — Pembroke | 1 |
| Vehicle-impoundment appeals, not charge dispositions | 7 |
| Suspended-driving references without a present s.53 verdict | 25 |
| Other proceedings | 98 |
| **Total reviewed** | **133** |

These are document counts, not charge counts or unique-case counts. No conviction
rate or estimate of publication coverage can be calculated from them.

## The three direct s.53 decisions

- **[R. v. Bell, 2024 ONCJ 692](https://www.canlii.org/en/on/oncj/doc/2024/2024oncj692/2024oncj692.html)** — Toronto.
  Paragraph 8 lists the HTA s.53(1) charge alongside firearm charges. Paragraph 104
  records conviction on all charges following admission of the evidence. Ottawa
  appears in a cited police policy, not as the prosecution's location. Candidate 29.
- **[R. v. Godin, 2024 ONCJ 492](https://www.canlii.org/en/on/oncj/doc/2024/2024oncj492/2024oncj492.html)** — Pembroke area.
  Paragraph 1 records a guilty plea to s.53(1); paragraphs 15–18 locate the incident.
  The sentence includes 30 concurrent jail days for that charge. It is a plea, not
  a trial verdict. Ottawa references concern treatment. Candidate 9.
- **[R. v. Haaima, 2023 ONCJ 625](https://www.canlii.org/en/on/oncj/doc/2023/2023oncj625/2023oncj625.html)** — Pembroke.
  Paragraph 1 lists two s.53(1) charges. Paragraphs 38–39 dispose of a request to
  attend trial by video, not the charges. Candidate 26.

The supplemental Toronto trial dismissal in **[Toronto (City) v. Minichiello,
2019 ONCJ 409](https://www.canlii.org/en/on/oncj/doc/2019/2019oncj409/2019oncj409.html)**
remains a valid comparison example from the pilot, but it was not one of the
133 Ottawa-keyword candidates and is not included in this table's denominator.

## Files and review method

- [CSV: all 133 classifications](s53-reviewed-2026-10-23.csv)
- [JSON: classifications, provenance, methods and search queries](s53-reviewed-2026-10-23.json)
- [Original pilot search catalogue](s53-search-2026-10-23.json), preserved as the earlier snapshot.

Each of the 133 CanLII pages was opened. The relevance review checked the proceeding
and charges, explicit section references, suspended-driving wording and the relevant
outcome passages. Surrounding text was checked to distinguish actual charges from
historical records, cited authorities and other legislation. This was not a full
legal analysis of every issue in each case.

**131 documents received a full-text relevance screen.** Long texts were retrieved
in chunks when the initial body extract was truncated. **Two documents were excluded
by their opening and proceeding scope** after repeated long-page retrieval failures:

- Candidate 126, *Toronto (City) v Toronto Professional Firefighters' Association*,
  2020 CanLII 31921: arbitration about health/dental/benefit-carrier entitlements.
- Candidate 132, *Barker v. Barker*, 2020 ONSC 3746: civil litigation over historical
  hospital treatment.

Those two are explicitly marked `opening_and_proceeding_scope` rather than
`full_text_relevance_screen`. Their classification does not assert that no passage
anywhere in them mentions a suspended-driving case; they do not themselves adjudicate
an HTA suspended-driving prosecution.

Every row has a source URL, decision date, evidence locator, reviewer-written reason,
geographic relationship and review method. Hashes identify the retrieved display-text
extracts (including metadata), not official source files. Cached texts remain local
and ignored by Git; the published audit contains metadata and paraphrased findings.

## What this means for the Ottawa chart

The [OCJ says CanLII is not exhaustive](https://www.ontariocourts.ca/ocj/decisions/).
The search may miss wording variants, OCR failures, or decisions that do not mention
Ottawa. A trial judgment, guilty-plea sentencing decision, bail decision, appeal and
vehicle-release decision are different kinds of records. A historical conviction
mentioned in one is not a new trial outcome.

The statistical dataset has no case identifiers or individual trial dates. **No
judgments were matched to annual charge totals, and no trial counts were reclassified.**
The reviewed set does not provide the missing Ottawa trial-outcome breakdown.
