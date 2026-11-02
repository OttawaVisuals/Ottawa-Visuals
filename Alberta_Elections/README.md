# Alberta election consolidation

Open `ABelections.html`. Adapted from the Ontario page; a historical May 29, 2023 snapshot, excluding later by-elections.

## Method

In each riding, combine a user-selected share of the trailing Liberal/NDP/Green candidates' votes behind whichever of those three led. UCP and all other candidates stay fixed. The Alberta Party is excluded. The 65% starting setting is illustrative, with no Alberta-specific calibration. Untransferred votes remain unallocated; no turnout response is estimated. Ties have no assigned winner. This is not a ranked-ballot simulation or forecast.

Even at 100% transfer, no seat changes winner: UCP 49, NDP 38. Of 87 actual winners, 78 exceed 50% of valid votes. Rejected/declined ballots are excluded from vote shares.

## Sources and gaps

- [Official workbook](https://www.elections.ab.ca/uploads/2023-Provincial-General-Election-Statement-of-Vote.xlsx): all 349 candidates, 87 divisions. Candidate totals checked against voting-location rows; each division reconciles to valid ballots. Retained in `data/`.
- [Official boundaries](https://www.elections.ab.ca/resources/maps/): enacted in 2017, effective in 2019; original projected coordinates, simplified by 60 metres. Division 17's old Calgary-McCall label is updated to Calgary-Bhullar-McCall, joined by number.
- [Historical turnout](https://www.elections.ab.ca/elections/election-results/historical-results/): 1975–2019 reported provincial rates. For 2023 use the workbook's 1,777,315 ballots / 2,939,762 electors = 60.5%. The web table reports conflicting totals and 59.5%; `data/audit.json` retains every detected difference. List-cleaning methods changed, limiting historical comparisons. Riding turnout is included for 2023 only.

## Rebuild and checks

Run `python Alberta_Elections/build_data.py` from the repository root (openpyxl, beautifulsoup4, pyshp, shapely). Sources are retained, hashed and read without modification. Regenerates bundled JS, CSV, JSON and audit. Run `node Alberta_Elections/check_model.cjs` for model and inline-script checks.

## Colour keys and layout

Election pages share `.ov-key`, `.ov-swatch` and `.ov-key-label` in `assets/site-theme.css`. Markers have a fixed, non-shrinking box; text occupies a separate box. Use this pattern for future HTML chart legends rather than positioning a marker over a label. Keep line/dashed keys in other chart systems intact.

Nov 1, 2026: Alberta and Ontario checked at 320/390/1280 CSS pixels in light/dark/colour-blind themes. All rendered shared keys had nonzero marker widths and at least 6 px separation, with no page-width overflow. Recent-turnout endpoint labels anchor inward. Budget, courts and wealth received limited phone-width spot checks; this is not a site-wide audit. Model checks pass for all 87 ridings at each whole-percent transfer setting, including synthetic tie and independent-candidate cases.

Published November 1, 2026.
