# Working in this repo

Static GitHub Pages site (no build step, no Jekyll — see `.nojekyll`). See
[`README.md`](README.md) for site structure, sub-project layout, and edit points —
don't duplicate that here; this file is about *how to work*, not *what's where*.

## Before touching pipeline/collector status

**Run `git pull` before drawing any conclusion from local commit timestamps, `git
log`, or file mtimes.** This local clone has gone stale (unpulled for days) and
produced false "outage" diagnoses at least twice — see the pipeline-status section
of [`PROJECTS.md`](PROJECTS.md) for both incidents. A quiet-looking `git log` on an
unpulled clone means nothing about whether the Pi is actually collecting.

Related traps specific to these collectors:
- `OC_Transpo/rt_data/kpi_snapshots/` only gets a new dated file when the city
  *republishes* — an unchanging directory is the expected steady state, not a
  stalled cron. Check the Pi's log, not file presence.
- Collector cadence is adaptive (denser around peak hours), not a flat interval —
  don't assume a fixed 30-min/hourly cadence when computing expected reading counts.

## Keeping status docs in sync

`PROJECTS.md` (pipeline table + narrative) and `tracker.html` (`#overview` banner)
both carry a "checked <date>" claim about collector health. When you verify
pipeline status, update **both** in the same pass — they've drifted out of sync
before. Prefer editing the existing narrative over replacing it wholesale; the
dated incident history is intentionally kept as a paper trail.

## Adding a new sub-project

Follow the existing pattern: its own folder with `README.md`, `data/`, any
scripts, and a `<name>.html` page. Then wire it in:
- `index.html` — add to the `REPORTS` array
- `README.md` — add a row to the sub-projects table
- `PROJECTS.md` — add an entry under the right status heading (✅/🔄/💡/☐)
- `tracker.html` — add to the progress-at-a-glance list and nav if it's a live page

## Conventions

- Keep large files out of the repo.
- Automated collector commits (`traffic: readings …`, `transit: readings …`,
  `Auto-update PWHL data …`, `Weekly data refresh …`) come from the Pi/Actions —
  don't hand-edit the data files they produce; fix the collector script instead.
- Progress percentages in `PROJECTS.md`/`tracker.html` are rough self-estimates,
  not hard metrics — don't over-index on precision when updating them.
