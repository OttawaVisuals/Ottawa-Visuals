# Ontario Votes by mandate

**Page:** [`mpp_mandates.html`](../mpp_mandates.html). Every recorded division (317, Aug 2022 – Oct 2026) weighted by the ballots that elected each MPP.

| File | Purpose |
|---|---|
| `collect_votes_in_browser.js` | Paste into the console on ola.org (Votes search). ola.org returns 403 to scripts, so this runs in your own browser, one request every 2 s, and downloads `ontario_votes.json` |
| `ontario_votes.json.gz` | Collected divisions: title, date, outcome, and every MPP's vote with party and riding. Gzipped (5 MB raw) |
| `mandates.py` | Joins the votes to `Ontario_Elections/Explorer_*.csv` (2022 for votes before 2025-02-27, else 2025) → `mandates.json` |
| `mandates.json` | Page data |

Refresh: re-run the browser script, `gzip` the download over `ontario_votes.json.gz`, then `python Ontario_Votes/mandates.py`.

**Known gaps:** MPPs elected in by-elections have no mandate (results not in the repo), so 132 of 317 divisions are marked partial and their ballots are left out of the sums. Result so far: no division was won by the side with fewer ballots behind it.
