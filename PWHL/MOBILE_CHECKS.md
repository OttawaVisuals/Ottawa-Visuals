# Mobile review — October 23, 2026

Checked the published site, then verified the fixes on a local HTTP server in
the browser. This uses resized browser viewports, not a physical phone or iOS
Safari. Native touch gestures, phone performance and a full accessibility audit
remain unverified.

## Coverage

- Eleven page types: Home, Teams, Players, Superlatives, Movement, Travel,
  Season replay, Player origins, How it works, Ottawa's team profile and
  Marie-Philip Poulin's player profile.
- Published layouts checked at 320, 360, 390 and 768 CSS pixels wide.
- Updated layouts checked at 320, 390, 768 and 1280 pixels: all 44 page/width
  combinations had no document-wide horizontal overflow or zero-size visible
  charts. Wide tables, brackets and schematic maps scroll within their panels.
- Visually inspected the dashboard, player controls/profile, travel map,
  replay and birthplace map; checked light and dark themes on representative
  views.

## Findings and fixes

| Finding | Change | Verification |
|---|---|---|
| A long birthplace popup exceeded the phone map's width, clipping its close control. | Limit popup text width to leave room for page gutters, popup margins and panning padding. Update open popups when the map resizes. | Popup and close control stayed inside the map at 320 and 390 pixels and after rotating through 844-pixel landscape. Closing the popup worked. |
| Form controls were generally 32–36 pixels tall, sorting buttons 23 pixels and playback sliders 16 pixels. | Give form fields, tab/sort/more buttons and sliders 44-pixel minimum heights on phone layouts; use 16-pixel field text. Preserve compact navigation. | Browser measurements confirmed 44-pixel controls and 16-pixel field text. The layout checks above include these changes. |

## Interaction checks

- Accent-insensitive name filtering found Vanišová; column sorting changed the
  selected sort heading.
- Goalie view and minimum-games filtering worked, including setting the minimum
  to zero.
- Theme selection changed the page theme.
- Travel's Next button advanced the displayed leg and slider value.
- Replay seeking to the end displayed final regular-season leaders; seeking back
  reset the slider to the start.
- Birthplace zoom, opening a marker popup, resizing with the popup open and
  closing it worked.
- No browser warnings or errors were captured during the final local checks;
  the updated origins JavaScript also passed a syntax check.

The dense statistics tables still require horizontal scrolling on phones.
Navigation is compact; this review does not claim that every link meets a
44-pixel target or that every possible filter/data combination was tested.
