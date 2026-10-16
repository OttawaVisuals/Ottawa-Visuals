# PWHL image fallback

`pwhl-logo.svg` contains the official white league lockup, downloaded on
2026-10-16 from the logo asset used by https://www.thepwhl.com/en/:

https://res.cloudinary.com/pwhl-low/image/upload/PWHL_Logo_Lockup_White_z8mr75.svg

The original paths are unchanged. The local version adds a purple square
background and padding so the mark stays legible in photo and logo slots in
all themes. The league owns the PWHL name and logo.

`PWHL.image()` and `PWHL.svgImage()` in `pwhl-core.js` use this local file when a
media URL is missing. A shared error handler also replaces failed downloads,
with a guard against retry loops. Existing adjacent player/team names remain
the identifying labels; the placeholder does not identify a specific player
or team. Decorative action-photo backgrounds and site branding are unaffected.
