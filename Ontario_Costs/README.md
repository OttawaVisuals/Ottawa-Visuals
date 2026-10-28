# Ontario_Costs — Ontario's costly decisions, by the watchdogs' numbers

Page: [`ontario_costs.html`](ontario_costs.html). A short, sourced list of Ontario
decisions that the **Auditor General** or the **Financial Accountability Office (FAO)**
put a price on or criticized, under the Liberal (McGuinty, Wynne) and PC (Ford)
governments, plus two large policy choices for scale ($200 rebate, licence-fee removal).

**Scope note:** provincial, like `Ontario_Elections/`. Not Ottawa-specific.

## Layout

```
Ontario_Costs/
  ontario_costs.html      the page (reads data/decisions.json; no build step)
  data/decisions.json     the list, hand-curated
```

## Adding or editing an entry

Each decision in `data/decisions.json`:

| Field | Meaning |
|---|---|
| `government`, `premier`, `year` | `PC` or `Liberal`; year the decision was made |
| `kind` | what the number is: `spending`, `cancellation`, `financing`, `revenue`, `court`, `value`, `deal`, `transfer` |
| `flag` | `criticized` (watchdog faulted the decision or process), `costed` (watchdog priced it, no verdict), `choice` (policy choice, for scale) |
| `amount_m` | headline figure in $ millions, for sorting and the bar; `low_m` if a range |
| `amount_label` | how the figure is shown, e.g. `$950M–$1.1B` |
| `per_year` | true if the figure is per year (drawn grey, like `value`) |
| `measures` | plain-language description of what the number measures |
| `verdict`, `response` | the watchdog's finding (or context) and the government's response |
| `sources` | name + URL; prefer the watchdog's own report |

Rules: use the official estimate as published; say what it measures; keep one
government's spin out of the `measures` line; add the government's response.

## Method notes and traps

- **Different kinds of numbers.** Spending, revenue given up, extra financing cost and
  value to private owners aren't additive. The page never totals them.
- **Nominal dollars**, over different time spans; several are projections or ranges.
- **Sources checked 2026-10-10; Bill 124 and licence fees re-sourced 2026-10-28.**
  Bill 124's $13.7B is from the FAO Winter 2024 outlook itself. For licence fees the
  FAO has no standalone costing of ending them, so the card uses the FAO's own 2018-19
  fee revenue ($849.1M, Southern Ontario passenger-car validation) as a floor; the
  "around a billion" remark and refund count remain news-relayed (CTV). The renewable-contracts $231M is
  from the Public Accounts (found by NDP researchers), not a watchdog report.
- **Gas plants:** $950M–$1.1B gross includes future ratepayer costs; net of $437M
  future savings it's about $675M (Auditor General 2013).

## Still to do

- Licence fees: look for an FAO costing of ending renewal fees (none in the Spring 2022 outlook or the service-fees report).
- Candidates to add: Ornge air ambulance (AG 2012), smart meters (AG 2014),
  Science Centre closure (AG 2024, partly covered under Ontario Place),
  Skills Development Fund, Highway 413.
