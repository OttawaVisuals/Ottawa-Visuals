# Federal election consolidation

Open `FedElections.html`. Adapted from the Ontario, Alberta and BC pages; a historical April 28, 2025 snapshot, excluding later by-elections.

## Method

In each riding, combine a user-selected share of the dropped candidates' votes behind whichever party in the selected group led. Groupings: Liberal + NDP, Liberal + NDP + Green, Conservative + People's Party. Every party outside the group, including the Bloc Québécois, independents and minor parties, keeps its votes and can still win. The 65% starting setting is illustrative, with no federal calibration. Untransferred votes remain unallocated; no turnout response is estimated. Ties have no assigned winner. This is a one-step transfer share, not a ranked-ballot simulation or forecast.

At 65% Liberal + NDP transfer 19 of 343 ridings change winner (Liberal 184, Conservative 127); at 100%, 29 (Liberal 193, Conservative 117). Liberal + NDP + Green: 24 at 65%, 36 at 100%. Conservative + PPC: 1 at 65%, 3 at 100%.

## Sources and gaps

- [Official voting results](https://www.elections.ca/content.aspx?section=res&dir=rep/off/45gedata&document=summary&lang=e): Table 12 (1,959 candidates), Table 11 (343 districts), Table 4 (turnout 2015–2025 by province). Retained in `data/`. Candidate votes sum to each district's valid ballots; Table 11's elected candidate is the top vote-getter in every riding; seats reconcile to Lib 169 / CPC 144 / BQ 22 / NDP 7 / Green 1. Party is parsed from the candidate string; `**` marks incumbents, not winners.
- [Boundaries](https://open.canada.ca/data/en/dataset/18bf3ea7-1940-46ec-af52-9ba3f77ed708): 2023 representation order, 343 districts, original Lambert conformal conic projection, joined by district number. National view simplified by 2.5 km with islands under 40 km² omitted; city insets (Ottawa, Toronto, Montréal, Vancouver) use 60 m simplification and select ridings by centroid distance from an anchor riding.
- Turnout 2015/2019/2021 is the sum of provincial totals in Table 4. Those elections used the previous 338-seat boundaries, so only national turnout is compared; riding turnout is 2025 only.

## Rebuild and checks

Run `python Federal_Elections/build_data.py` from the repository root (pyshp, shapely). It downloads the ~9 MB boundary zip if missing (git-ignored), reads the retained CSVs without modification, asserts the reconciliations above, and regenerates `data.js`, `geo.js`, `turnout.js`, `data/candidates.csv`, `data/results.json` and `data/audit.json`.

## Canadian Election Study layer

The page's survey section uses the campaign wave of the 2025 CES (Harvard Dataverse, DOI 10.7910/DVN/2YAQ8D, licence CC BY-NC 4.0, 11,577 weighted respondents who named a party). For each party's intended voters it reports the share who would absolutely not vote for another party, the share rating it 50+ on a 0–100 slider, and "open to" (neither ruled out nor rated below 50), nationally and for Ontario, Quebec, BC, the Prairies and Atlantic Canada. Nationally about 60% of NDP voters are open to the Liberals and 63% of Liberal voters to the NDP; 64% of PPC voters are open to the Conservatives (n=140). Postal code is not public, so there is no riding or Ottawa cut; groups under 100 respondents are hidden. These are stated attitudes from an online panel, not observed vote transfers.

Six further tables use the same file (code in `ces_extra.py`): (1) why people chose their party, including "didn't want another party to win" as the survey's stated-motive measure of tactical voting, and when they decided; (2) campaign-wave intended vote against post-election-wave actual vote (about 26% of people who said NDP voted Liberal); (3) who switches or is open, by age, income, education, gender, housing tenure and union membership (age is the only clear gradient: 33% of NDP supporters 18-34 voted Liberal vs 20% of those 55+); (4) why people rule a party out (leader / policies / supporters; only Liberal and Conservative have 100+ single-party respondents); (5) most important issue by intended party, from free text sorted by keyword, so "Other" is large; (6) why people did not vote. Tables 1-2 are by region; the rest are national. Post-election tables use `pes25_weight_general_restricted`. No Ottawa cut exists.

Rebuild: download the `.dta` from Dataverse (not stored here), then `python Federal_Elections/ces_tables.py "<path to 2025 Canadian Election Study v1.dta>"` (pandas). It writes `data/ces_tables.json` and `ces.js` and records the input file's SHA-256. Weight: `cps25_weight_general_restricted`. Variables: `cps25_votechoice`, `cps25_not_vote_for_*`, `cps25_party_rating_*`, `cps25_province`; names and value labels checked in the final v1 file; the technical report was only searched for the party-rating and not-vote-for items.

Built November 6, 2026.
