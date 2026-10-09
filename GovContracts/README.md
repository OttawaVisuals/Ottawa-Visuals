# GovContracts — federal consulting spend

Explores the Government of Canada's Proactive Disclosure of Contracts dataset for
consulting/professional-services spend that's plausibly duplicative of in-house
public-service capacity, or tied to the federal return-to-office push — a
federal-level companion angle to [`rto.html`](../rto.html) ("Ottawa RTO Watch"),
since NCR federal headcount is a big share of Ottawa's downtown workforce.

**Scope note:** this dataset is *federal*, not City of Ottawa — a departure from
this repo's usual municipal focus. Keeping it in its own folder rather than
folding into `RTO4/` for that reason.

## Why this is tractable despite "manually written descriptions"

The dataset's `description_en`/`description_fr` fields are **not** free-text
summaries of the work — they just spell out the `economic_object_code` (a
Treasury Board accounting category). The real categorization signal is two
*structured* code fields, not prose:

- **`commodity_code`** — a GSIN-derived product/service code (e.g. `R019F` =
  "Consulting Services"). This is the primary axis for "what kind of work."
- **`economic_object_code`** — broader financial chart-of-accounts category.

`comments_en`/`additional_comments_en` are mostly short standardized remarks
(contract amendment amounts, etc.) rather than rich narrative, but do
occasionally carry real text worth a keyword pass (e.g. "return to office").

GSIN code descriptions come from PSPC's own reference table (see Sources below)
— joined in, not re-derived.

**Caveat:** GSIN was officially superseded by UNSPSC starting ~2021 for federal
procurement classification. `commodity_code` values in this dataset may be
either scheme depending on contract date; the GSIN lookup table only resolves
pre-2021-style codes. This turned out to matter a lot: `commodity_code` is
**blank on 35% of rows** ($137.9B worth). `description_en` — despite being
just the `economic_object_code` label, not a real narrative — is blank on
only **0.08% of rows**, making it the far better categorization axis. Both
are kept as two separate category outputs (see Layout below); `commodity_code`
is worth keeping only as a secondary cross-check where present.

`description_en` has its own problem: it's extremely inconsistently
formatted — leading numeric `economic_object_code` prefixes ("1231 Office
furniture and furnishings, incl. Parts"), mixed case, mojibake dash
characters, and free text appended after a second dash ("Engineering
consultants - construction - Highways, roads and streets"). Matching
requires normalizing first (strip the numeric prefix, unify case/dashes),
then a *prefix* match against a curated whitelist — not a bare substring
search, which would wrongly catch e.g. "IT Architect" job titles under
"Architectural services." See `categorize_by_description()` in
`scripts/build_aggregates.py`.

## Layout

```
GovContracts/
  scripts/
    build_aggregates.py   reads local raw CSVs -> writes data/*.json
  data/
    category_definitions.json          commodity_code -> plain-English label
    spend_by_year_category.json        commodity_code axis: spend + count, year x category
    spend_by_department_category.json  commodity_code axis: spend by department x category (top 500)
    top_vendors.json                   commodity_code axis: top 200 vendors by flagged spend
    office_footprint_categories.json   description_en normalize+match rules -> plain-English label
    office_footprint_by_year.json      description_en axis: spend + count, year x category
    office_footprint_by_month.json     description_en axis: spend + count, month x category
                                        (for spotting an RTO-mandate-driven spike)
    office_footprint_by_year_procurement.json  description_en axis: spend + count,
                                        year x category x procurement_type (competitive /
                                        non-competitive / ACAN / unspecified)
    office_footprint_top_vendors.json  description_en axis: top vendor spend, per category
    data_coverage.json                 row counts by month + last_reliable_month --
                                        proactive disclosure lags real contract dates by
                                        a quarter+, check this before trusting recent months
    rto_candidates.json                top 500 contracts matching RTO/workplace keywords
```

Two separate, parallel category axes: `commodity_code`-based (broader
consulting/IT categories, `category_definitions.json`) and `description_en`-
based (the specific RTO office-footprint categories — engineering/architectural/
construction consultants, office buildings, repair & maintenance, building
cleaning, furniture, other office equipment — `office_footprint_categories.json`).
The second axis has far better field coverage; see above.

## Refreshing (raw sources are NEVER committed — 600+ MB)

1. Download the current contracts CSV (quarterly refresh, matching the
   dataset's own cadence) from the "Contracts over $10,000" resource on
   <https://open.canada.ca/data/en/dataset/d8f85d91-7dec-4fd1-8055-483b77225d8b>.
2. Download the GSIN code table from
   <https://open.canada.ca/data/en/dataset/2ce347e5-02fd-4487-975d-67a435efdf9b>
   (`nibs-gsin.csv`).
3. Run:
   ```bash
   python GovContracts/scripts/build_aggregates.py <path-to-contracts.csv> <path-to-gsin.csv>
   ```
4. Commit the regenerated `data/*.json` only.

Stdlib-only (`csv`/`json`), no `pip install`, matching the rest of the repo's
collector scripts.

## Contracts under $10,000

There's a separate, much smaller resource on the same dataset page for
sub-$10K contracts ("Contracts $10K and Under (Aggregated)"). Checked
2026-08-01: it's a dead end for category-level detail. The entire schema is
`year, owner_org, owner_org_title` plus three buckets (Goods / Services /
Construction), each just a count + dollar total, and a separate
`acquisition_card_transactions` count + total — no vendor, no description, no
commodity code. Small purchases (a $500 office chair, e.g.) are aggregated
away at the point of publication, not just messy like the >$10K data. The
acquisition-card (P-card) line alone runs ~$700–850M/year across 1.6–2M
transactions government-wide — almost certainly where a lot of real small
office-supply/furniture spend lives — and it's completely opaque. This is a
structural ceiling on what this dataset can show, not something a better
script can work around.

## Sources

- Contracts: <https://open.canada.ca/data/en/dataset/d8f85d91-7dec-4fd1-8055-483b77225d8b>
  (quarterly updates; ~600 MB CSV, all federal departments, roughly 2017–present,
  plus a separate "legacy" resource for older records)
- GSIN codes: <https://open.canada.ca/data/en/dataset/2ce347e5-02fd-4487-975d-67a435efdf9b>

## Status / open questions

First pass ran 2026-08-01 against the full contracts.csv (1,313,348 line items,
2007–2026). Three iterations were needed to get a defensible category signal
— each one a real false lead, kept here so they aren't repeated:

- **v1 (rejected):** categorized by bare `commodity_code` *prefix* (e.g. any
  code starting `R199`). Pulled in BGIS's ~$5.7B national real-property
  management contract and VF Worldwide's ~$24.6M overseas logistics support as
  "consulting" — those 4-character prefixes also cover unrelated
  multi-billion-dollar operational contracts. Top-vendor totals were garbage.
- **v2:** categorized by an *exact* whitelist of GSIN codes found by grepping
  the GSIN table's own descriptions for consulting/advisory/change-management
  language, hand-pruned to drop unrelated matches (naval architecture, marine
  consulting, citizen engagement, medical advisory). Added a second category
  for the *physical* office footprint (furniture, fit-up, leasing, moving —
  the `N7110*` prefix, verified clean this time by checking every code in
  that family) since a single word like "office" is too noisy for text search
  but precise as a commodity-code family.
- **v3:** dropped `V502A` ("Relocation Services") from the office-footprint
  category after it turned out to be dominated by the government's Integrated
  Relocation Program — employee household moves between postings (biggest
  payers Global Affairs/National Defence) — not office space moves. A single
  Jan 2023 cluster of household-mover contracts (United Van Lines, Atlas,
  Sirva, Brookfield) totalled >$700M and would have swamped the category the
  same way R123/R199 did in v1.
- **v4 (current):** switched to `description_en` as a second, primary
  category axis (see caveat above — far better field coverage than
  `commodity_code`), scoped to seven specific RTO-relevant categories:
  engineering consultants (construction), architectural services, office
  buildings, repair & maintenance of office buildings, contracted building
  cleaning, office furniture & furnishings, other office equipment. Also
  added a **month-level** series (`office_footprint_by_month.json`) and a
  **data-coverage check** (`data_coverage.json`) specifically to catch a
  future spike around the Jul 2026 RTO4 mandate — see finding below.

**commodity_code-axis categories and totals** (2007–2026, all federal departments):

| Category | Spend | Contracts |
|---|---:|---:|
| Management & business consulting | $4.73B | 9,116 |
| IT / informatics consulting | $541M | 906 |
| Office furniture & fit-up | $386M | 9,299 |
| Office space leasing & moves | $129M | 999 |
| Real estate / workplace advisory | $61K | 2 |

Consulting-code spend runs from single-digit millions (2007–2013) up to
$500M–$800M/year from 2020 onward. Top vendors are recognizable
consultancies/IT staffing firms (PwC/Accenture joint venture, IBM, ADGA
Group, Ernst & Young, S.I. Systems, Randstad).

**description_en-axis categories and totals** (2007–2026, all federal departments):

| Category | Spend | Contracts |
|---|---:|---:|
| Engineering consultants – construction | $32.3B | 14,964 |
| Office buildings | $23.6B | 14,329 |
| Architectural services | $19.3B | 5,498 |
| Repair and maintenance – Office buildings | $10.0B | 1,571 |
| Contracted building cleaning | $2.7B | 8,407 |
| Office furniture and furnishings, incl. parts | $1.3B | 22,740 |
| Other Office Equipment and Parts | $0.4B | 3,029 |

Substantially larger and better-covered than the commodity_code-axis
categories, as expected given the coverage gap. "Office buildings" is broad —
likely mixes capital construction of new buildings with straightforward
leasing (`Rental of office buildings` is folded in) — worth splitting further
if isolating "we pay rent" from "we built a building" matters later.

**Data-coverage finding (checked 2026-08-01):** this dataset's proactive
disclosure has a real reporting lag. Monthly row counts run 5,000–7,000
through **June 2026**, then collapse to 17 rows in July, 1 in September, 1 in
December — clearly not real activity, just contracts not yet disclosed.
`data_coverage.json`'s `last_reliable_month` (`2026-06` as of this run) is
computed automatically each refresh (any month with less than half the
dataset's median monthly row count is excluded) rather than hardcoded, so
this doesn't need to be re-derived by hand next time.

**This means the RTO-mandate-spike check cannot be done yet.** The Jul 6,
2026 RTO4 mandate date isn't covered by this data at all — the dataset simply
hasn't caught up. `office_footprint_by_month.json` is built and ready; the
next quarterly refresh (this dataset updates quarterly) should be checked
against `data_coverage.json.last_reliable_month` first, and only compared
against pre-mandate months once it actually covers Jul 2026 onward.

**Contracts under $10,000 are a dead end for category detail.** See the
"Contracts under $10,000" section below — the companion resource for small
contracts is aggregated down to Goods/Services/Construction totals per
department per year, with no vendor/description/code, so this pipeline can
only ever speak to the >$10K population.

**Competitive vs. non-competitive split** (added 2026-08-01, in
`office_footprint_by_year_procurement.json`): joined `solicitation_procedure`
onto the 7 office-footprint categories, by year. Per the Treasury Board
"Guide to the Proactive Publication of Contracts": `TC`/`OB`/`ST` are the
three competitive procedures (Traditional, Open Bidding via GETS, Selective
Tendering), `TN` is non-competitive, `AC` is an Advance Contract Award Notice
— kept as its own bucket rather than folded into either side, since it's a
notice-based process that's only nominally competitive (a contract becomes
genuinely competitive under ACAN only if a challenger's capability
statement succeeds). **This field is unreliable before 2017** (90–100% blank
2005–2015, still 61% blank in 2016) and only fully clean from 2019 onward —
scope any competitive-share analysis to 2019+. Across all 7 categories
combined, competitive spend dominates every reliable year (e.g. 2023: $6.97B
competitive vs. $110M non-competitive vs. $6.9M ACAN) — **not yet checked
per-category**, which matters more: architectural/engineering services likely
carry a higher sole-source share than furniture or building cleaning, and
that's the more interesting number for an accountability narrative than the
combined total.

**Presentation idea (not yet built):** a stacked bar chart, one bar per year,
segments = procurement type, with a category filter/dropdown to switch
between "all 7 combined" and any single category. Pair with a 100%-stacked
(normalized) version to isolate the competitive-share *trend* from raw
dollar growth — a dollar-stacked chart can look alarming purely because
total spend grew, while the normalized one answers the sharper question ("is
competition eroding?") directly. Small multiples (one mini chart per
category) would be the natural next view if the single-chart-plus-filter
version doesn't surface the per-category differences clearly enough.

- **RTO-keyword pass:** 106 contracts matched a broadened phrase list (added
  "office relocation," "office renovation," "workstation reconfiguration,"
  "workplace densification," etc. — still phrase-based, not single words like
  "lease" or "office," which are too common in unrelated text/GSIN labels).
  This dataset's `comments_en` field is mostly boilerplate ("this contract was
  competitively sourced," amendment amounts), not narrative, so free-text RTO
  signal stays genuinely thin. The hits include real movers/fit-up vendors
  (SLBL Déménagement, Simplex Industries, an architecture firm doing
  "Architectural & Engineering Services - Office..." work) alongside noise.
  **Read this as "what little explicit RTO language exists in this dataset,"
  not a complete picture** — most RTO-adjacent spend, if any, likely hides
  inside the structured categories above without RTO-specific wording, which
  is exactly why the `Office furniture & fit-up` / `Office space leasing &
  moves` categories matter more than the keyword hits do.

**Takeaway so far:** the "in-house duplication" angle (consulting + IT spend
trending toward $500–800M/year, plus $32B+ in construction/engineering/
architectural consulting and $23.6B in office-building spend on the
description_en axis) is well supported by structured data. The specific
"RTO-driven" angle remains unproven — not because the categories are wrong,
but because **the data doesn't reach the mandate date yet** (see coverage
finding above). This is a "come back next quarter" gap, not a dead end.

**Not yet checked:** GSIN vs UNSPSC coverage split by year for the
commodity_code axis — moot for now since the description_en axis is the
primary one, but worth revisiting if commodity_code is ever leaned on again.

## Next steps to pick this back up

Tracked in [`../tracker.html`](../tracker.html#todo) and
[`../PROJECTS.md`](../PROJECTS.md) too — kept here as the authoritative
detail so a future session doesn't have to re-derive it:

1. **Watch for the next quarterly refresh.** Re-download `contracts.csv`,
   check `data_coverage.json.last_reliable_month` reaches past Jul 2026, then
   compare `office_footprint_by_month.json` pre- vs. post-RTO4-mandate. This
   is the single most promising untested lead in the whole project.
2. **Build the actual chart(s).** Stacked bar per year × procurement type
   with a category filter, plus a 100%-stacked version — see "Presentation
   idea" above. Data is ready (`office_footprint_by_year_procurement.json`);
   pull in the `dataviz` skill for styling/palette work when building it.
3. **Check the competitive/non-competitive split *per category*, not just
   combined** — architectural/engineering services are the most likely to
   show a materially different sole-source rate than furniture or cleaning,
   and that's the sharper accountability number.
4. **Split "Office buildings"** (capital construction mixed with plain
   leasing) if isolating "we pay rent" from "we built a building" turns out
   to matter for the narrative.
5. **Second human read** of `rto_candidates.json`,
   `office_footprint_top_vendors.json`, and `top_vendors.json` — the
   category/keyword lists in `scripts/build_aggregates.py` are still a first
   pass — before any of this becomes a public-facing page.
