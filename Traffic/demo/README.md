# Unlisted road safety form demo

Public URL: https://ottawavisuals.github.io/Ottawa-Visuals/Traffic/demo/

Independent concept for discussion with Vision Zero Ottawa; no affiliation implied.
Intentionally absent from homepage, report navigation and public tracker.
`noindex, nofollow, noarchive` requests exclusion from search engines. This is an
unlisted public page, not access control; the source is in the public repository.

Buildless HTML/CSS/JS. One scrolling form: choosing a report type reveals location,
time and structured details together, without Continue buttons or automatic scroll
jumps. One Preview report button opens the review, with Edit answers and Start over.
Validation appears beside the relevant question and receives keyboard focus.
Multi-select unknown values are exclusive. Optional note is limited to 500
characters and rendered with textContent.

Question coverage (2026-11-14): the form now asks every question on the Vision
Zero Ottawa close-call form (https://visionzeroottawa.ca/posts/closecall/), as
tap choices instead of free text or dropdowns: location, reporter's direction,
origin/destination (optional text), vehicle type (their six categories, single
choice), vehicle direction, driver movement, who took evasive action, reporter's
evasive action, driver's evasive action, poor driving behaviour, injured. Every
choice question has a "Not sure" option except injured (Yes/No, as on their form).
The two evasive-action follow-ups appear only when the "who" answer makes them
relevant. Additions beyond their form: report type, map pin, date/time, travel
mode, "both/neither" for evasive action, extra behaviour choices, optional note.
Witness reports omit the reporter's travel mode, direction, origin/destination,
evasive action and injury questions. Record `schema_version` is 2.

Entries exist only in memory; no submission endpoint, analytics, report storage,
upload or download. Start over clears the form and review; refresh clears entries.
The shared site theme stores only theme preference. Shared theme fonts use Google
Fonts. Leaflet assets use unpkg; map tiles use OpenStreetMap. Tile requests reveal
the viewed map area and ordinary request metadata to the tile provider. Device
location is requested only on button click; coordinates are not sent to a report
service, but centering the map requests tiles for that area. Location permission
denial/timeouts and missing map assets retain the typed-intersection fallback.

The page uses `strict-origin-when-cross-origin` so tile requests identify the
site origin, as required by the OSM tile policy, without sharing the page path
or form entries. Do not replace it with `no-referrer`: OSM may serve blocked
tile images. See https://operations.osmfoundation.org/policies/tiles/.

Map point requires confirmation because current device location may differ from
incident location. Typed locations are accepted as descriptions, not geocoded.
Device accuracy is retained separately from user-adjusted map points. Time is
optional, approximate, explicitly Ottawa local time; no UTC conversion. Categories
record the reporter's observations; perceived speeding is not a measured violation.
No aggregate results, danger ranking, measured speeds or collision linkage claimed.

Before real collection: agree categories and field meanings with partners, storage
and retention, consent, moderation, duplicate handling and public-map precision.

Initial validation (2026-10-30): JavaScript syntax and Git whitespace checks; browser close-call and witness flows through review, finish/reset, 390px mobile layout without horizontal overflow, map pin confirmation, exclusive unknown vehicle choice, light/dark themes, no browser warnings/errors. Actual device GPS permission/success/timeout and physical-phone interaction were not tested.

Continuous-form validation (2026-10-30): close-call and witness previews, edit preservation, type switching, reset, inline required-location error with keyboard focus, 390px layout without horizontal overflow, no Continue buttons and no browser errors. No live GPS test added.

Behaviour artwork (2026-11-14): all 13 driving-behaviour choices use the approved SVG scenes in icons/, displayed at 56 px with a light backing for theme contrast. Text labels and stored category values are unchanged. icon-proposals/ retains the comparison study. Verified desktop and 390 px mobile layout, all SVG loads, dark-theme rendering, unknown-choice exclusivity and report preview; no JavaScript page errors. External requests were blocked during this local icon check.

Matching artwork for the other questions (2026-11-14): report type, travel mode, vehicle type, directions, driver movement, evasive action and injury now use 30 more SVG scenes in icons/, drawn on the same 80-unit grid with the same navy line, pale fill and red accent, and reusing the behaviour set's car, walker and bike shapes. "Other" and "Not sure" reuse other-behaviour.svg and not-sure.svg. The inline line-icon paths were removed from demo.js; each answer row now names its icon file. Verified all 59 icon images load, close-call preview, desktop and 375 px layout without clipping or horizontal overflow, no console errors. Not tested on a physical phone or in the light theme.
