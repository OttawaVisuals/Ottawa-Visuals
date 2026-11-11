# Ottawa fatal crash sentencing pilot

**January 1–June 30, 2024 crash dates. Public sources checked November 11, 2026.**

| What the audit found | Count |
|---|---:|
| Fatal-injury rows in the City file | 17 |
| Crash entries after grouping three probable duplicate pairs | 14 |
| Crash entries matched to public reporting | 9 |
| Possible public-reporting match with a location discrepancy | 1 |
| Entries with only the City record located | 4 |
| Crash entries with charges reported | 2 |
| Crash entries with a court outcome verified | 0 |

[Crash-by-crash CSV](fatal-crashes-2024-h1.csv) · [City collision layer](https://services.arcgis.com/G6F8XLCl5KtAlZ2G/arcgis/rest/services/Traffic_Collisions_by_Location_2017-2024_(excluding_2023)/FeatureServer/0)

**Feasibility.** Published sources yielded two court-record leads. A tracker of documented sentences is feasible with case-by-case verification. This pilot gives no basis for a sentencing distribution or an estimate of how often crashes lead to charges. All 14 court outcomes are unknown in this audit. A single-vehicle crash may involve the death of a driver or passenger, and inclusion in the cohort establishes neither fault nor that another person caused the death.

## How cases were matched

- Started with all City rows dated January through June 2024 with `severity = Fatal injury` or a positive `fatalities` value in the [repo snapshot](../../Traffic/data/city/collisions/2024.csv). Chose the first half of 2024 because the City has incident-level records and there has been time for court proceedings. The repo's [police release archive](../../Traffic/data/ops_collision_releases.csv) starts too late to anchor this window.
- Grouped the two Jan. 2 Bank Street rows and the two Jan. 10 Regional Road 174 rows. Each pair shares a date, road segment, City location ID, impact type and injury counts, with coordinates within 20 metres. Also grouped a sparse April 28 fatal-injury row with the 8th Line Road collision. The two rows share a date, impact type and conditions and are within four metres. The sparse row has a blank fatality count. Kept all City record IDs in the CSV. The City or police occurrence numbers would be needed to confirm the three groupings.
- Searched each crash by date and street or interchange, including variants such as Hwy. 174, Regional Road 174 and Cumberland. Looked for follow-up using charge and sentencing terms. Where a charge report supplied a defendant's name, searched that name for a court result. Searches covered public web results, including indexed court decisions and reporting. Court counters and paid transcripts were outside this online audit.
- Classified public reports by agreement on date, place and crash details. The May 23 Strandherd report names a different cross street, so it stays a possible match. The May 31 match uses the date, Highway 417 corridor, multiple vehicles and one death. The City and reporting use different interchange references, so the occurrence number is worth checking when retrieving the file.
- Used police-attributed reporting as evidence that a charge was reported. A court outcome needs a disposition, court order, reasons for judgment, or reporting that explicitly describes the outcome in court. CanLII coverage is incomplete. [Ontario Court of Justice decision coverage](https://www.ontariocourts.ca/ocj/decisions/)

## Two court records to request

| Crash | Reported charge | What to verify |
|---|---|---|
| May 14, 2024 · Highway 417 near Kinburn Side Road | Careless driving causing death and one count of careless driving causing bodily harm | Public disposition and any sentencing or driving order. [Charge report](https://ottawa.citynews.ca/2024/11/01/charges-laid-in-head-on-crash-that-killed-1-injured-infant-on-hwy-417/) |
| May 31, 2024 · Highway 417 near Carp Road, as described in reporting | Careless driving causing death and two counts of careless driving causing bodily harm | Confirm the occurrence match and obtain the public disposition and any sentencing or driving order. [Charge report](https://ottawa.citynews.ca/2024/10/16/charges-laid-in-hwy-417-multi-vehicle-collision-that-killed-a-child/) |

Ask the [Ottawa Provincial Offences Court office](https://ottawa.ca/en/parking-roads-and-travel/tickets/court-locations-and-hours/provincial-offences-court-offices) whether it can identify these cases using the crash dates, locations and charges. Request the file numbers, current dispositions by count and any sentencing or driving orders available for public inspection. If more identifiers are needed, ask what will suffice and check with Ottawa OPP for an occurrence number or other public reference. Check for publication restrictions and any appeal before publishing an outcome. A [sentencing transcript](https://ottawa.ca/en/parking-roads-and-travel/tickets/provincial-offence-violations-other-tickets/trial-and-other-court-services-other-poa-tickets) is an option if the file lacks the terms. [Ontario public-access policy](https://www.ontario.ca/document/access-court-files-documents-and-exhibits/section-2-public-access-criminal-court-files-and-documents)

## What a sentencing table would show

Use one row per sentenced driver per crash. Show the offence of conviction, sentence date, custody, conditional sentence served in the community, probation, fine and driving prohibition or suspension. Link to the trial and appeal sources and indicate when a component is unknown. When a sentence covers multiple counts, show the combined sentence and identify the included offences.

An Ottawa case outside the pilot illustrates the appeal field. In *R. v. Precup*, the trial judge imposed a combined four years of imprisonment for dangerous driving causing death and failing to remain. The Court of Appeal reduced the custody term. The 2015 trial reasons alone would give an outdated figure. [Trial reasons](https://www.minicounsel.ca/scj/2015/2112) · [Court filing describing the appeal](https://www.scc-csc.ca/pdf/case-documents/42169/MM020_Intim%C3%A9_Patrick-Dussault.pdf)
