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
Witness reports omit the reporter's travel mode/evasive action. No compass
direction questions. Multi-select unknown values are exclusive. Optional note is
limited to 500 characters and rendered with textContent.

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
