#!/usr/bin/env python3
"""Log Ottawa crash headlines from CTV News, as a second source beside OPS releases.

OPS only puts out releases for crashes it wants witnesses for. A check against CTV
(Mar-Oct 2026) found releases for 78% of fatal crashes but 29% of serious non-fatal
ones, and almost none for minor pedestrian hits or cars into buildings. CTV
covers many of those, so this logs CTV's crash headlines and links each one to the
matching OPS release where there is one.

Source: CTV's daily news sitemaps,
  https://www.ctvnews.ca/arc/outboundfeeds/sitemap/YYYY-MM-DD/?outputType=xml
(~340 URLs a day across Canada; public, no key). Only URLs under /ottawa/article/
whose slug has a crash word are kept. Everything is read from the slug (the
headline). Article text is never fetched or stored.

Most CTV Ottawa crash stories are elsewhere: eastern Ontario, Gatineau, and the
417/416/401, which the OPP patrols. `in_ottawa_ops` = 0 marks those. Rows are
kept anyway so the filter can be audited.

Outputs (Traffic/data/):
  * ctv_crash_headlines.csv -- one row per article. Rewritten each run (it's small)
                               so OPS matches that arrive later get filled in.
  * ctv_crashes_state.json  -- last poll time and the earliest backfilled day.

Runs from collect.yml every 5 min; self-gates to hourly and then re-reads today's
and yesterday's sitemaps. --since YYYY-MM-DD backfills. Stdlib only.
"""

import argparse
import csv
import json
import re
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
TZ = ZoneInfo("America/Toronto")

SITEMAP = "https://www.ctvnews.ca/arc/outboundfeeds/sitemap/{day}/?outputType=xml"
UA = "Mozilla/5.0 (compatible; ottawa-visuals-collector)"
PREFIX = "https://www.ctvnews.ca/ottawa/article/"

OUT = DATA / "ctv_crash_headlines.csv"
STATE = DATA / "ctv_crashes_state.json"
OPS = DATA / "ops_collision_releases.csv"

POLL_EVERY = timedelta(minutes=55)
DAY_PAUSE = 0.5           # seconds between sitemap days during a backfill
MATCH_DAYS = 3            # CTV story vs OPS incident/release date window

FIELDS = [
    "sitemap_date", "lastmod_utc", "in_ottawa_ops", "out_reason", "story_kind",
    "severity", "collision_type", "pedestrian", "cyclist", "motorcycle",
    "off_road", "building", "hit_and_run", "matched_ops_url", "match_basis",
    "slug", "url",
]

# "strikes" only with a vehicle on one side: not "clock strikes" or air strikes.
CRASH = re.compile(r"collision|crash|struck|pedestrian|cyclist|hit-and-run|motorcycl|"
                   r"rollover|e-bike|e-scooter|"
                   r"(?:vehicle|car|suv|truck|bus|train|driver|van)-strikes|strikes-(?:pedestrian|cyclist|vehicle)")

# Places outside OPS jurisdiction, as they appear in CTV slugs. OPP patrols the
# 400-series and provincial highways inside Ottawa too; Hwy 174 is a City road (OPS).
OUTSIDE = [
    "kingston", "pembroke", "brockville", "cornwall", "renfrew", "perth", "hawkesbury",
    "arnprior", "petawawa", "belleville", "napanee", "gananoque", "prescott",
    "smiths-falls", "carleton-place", "kemptville", "almonte", "mississippi-mills",
    "deep-river", "whitewater", "bancroft", "tweed", "trenton", "madoc", "frontenac",
    "glengarry", "stormont", "dundas", "prince-edward", "alexandria", "russell-ont",
    "near-russell", "rockland", "chesterville", "vankleek", "lanark", "montebello",
    "gatineau", "quebec", "que", "chelsea", "la-peche", "kazabazua", "pakenham",
    "wolfe-island", "eastern-ontario", "ottawa-valley", "casselman", "embrun",
    "winchester", "morrisburg", "merrickville", "kaladar", "johnstown", "odessa",
    "south-of-ottawa", "west-of-ottawa", "east-of-ottawa", "north-of-ottawa",
    "hwy-401", "highway-401", "hwy-7", "highway-7", "hwy-17", "highway-17", "hwy-15",
    "highway-41", "hwy-50", "county-road", "ny",
    "hwy-417", "highway-417", "hwy-416", "highway-416", "opp",
]

# Not a crash report: stats, safety messaging, infrastructure, planes.
CONTEXT = re.compile(r"crossing-button|ferry|air-gun|plane|air-traffic|infrastructure|"
                     r"lighting|drop-in-number|jump-in-collisions|-urge|urging|4-way-stop|"
                     r"raising-concerns|demand|call-for|calls-for|safety-review|-fined-|"
                     r"\d+-?kmh|km-h|going-\d+|move-over|safety-changes|e-scooters-(?:return|to-be)|"
                     r"scooting|cracking-down|data-shows|in-the-er|treating-more|grade-separation")
MONTH = (r"(?:january|february|march|april|may|june|july|august|september|october|november|"
         r"december|jan|feb|aug|sept?|oct|nov|dec)")
# A later story about a crash already reported (trial, charges months on, tributes).
FOLLOW_UP = re.compile(r"pleads|testifies|new-details|video-shows|mourns|family|"
                       r"special-day|reopens-after|earlier-this-month|-in-(?:january|"
                       r"february|march|april|may|june|july|august|september|october|"
                       r"november|december)$|last-spring|siu-finds|accused|lay-.*charges-following|"
                       rf"{MONTH}-(?:\d+-)?(?:crash|hit-and-run|collision)")


def has_place(slug, place):
    return re.search(rf"(?:^|-){re.escape(place)}(?:-|$)", slug) is not None


def classify(slug):
    t = set(slug.split("-"))
    out = next((p for p in OUTSIDE if has_place(slug, p)), "")
    kind = "context" if CONTEXT.search(slug) else "follow_up" if FOLLOW_UP.search(slug) else "incident"

    s = slug.replace("non-life-threatening", "nlt")
    if t & {"killed", "dies", "dead", "death", "fatal", "fatally", "died", "fatality"}:
        severity = "fatal"
    elif re.search(r"critical|life-threatening|trauma|airlifted|life-altering", s):
        severity = "critical"
    elif "serious" in s:
        severity = "serious"
    elif re.search(r"nlt|minor|stable|injur|hospital|hurt|extricat|treated", s):
        severity = "injury"
    elif re.search(r"no-injuries|unharmed|safe-after", s):
        severity = "none"
    else:
        severity = "unknown"

    # Whole hyphen tokens, so "motorcyclist" never counts as "cyclist".
    cyclist = int(bool(t & {"cyclist", "bicycle", "scooter"} or ("bike" in t and "dirt-bike" not in slug)))
    motorcycle = int(bool(t & {"motorcycle", "motorcyclist"}))
    # "woman struck by vehicle" means a pedestrian unless a rider is named.
    struck = re.search(r"(?:struck|hit)-by-(?:a-)?(?:vehicle|car|suv|truck|van|bus|driver)", slug)
    flags = {
        "pedestrian": int(bool(t & {"pedestrian", "pedestrians", "wheelchair"}
                               or "crossing-guard" in slug
                               or (struck and not (cyclist or motorcycle or "tractor" in t)))),
        "cyclist": cyclist,
        "motorcycle": motorcycle,
        "off_road": int(bool(t & {"atv", "snowmobile", "snowmobiler"} or "dirt-bike" in slug)),
        # "crash on Bank Street" is a road, not a bank.
        "building": int(bool(re.search(
            r"(?:crash(?:es|ed|ing)?|into|strikes|hits)-(?:[a-z0-9]+-){0,4}?(?:business|home|house|"
            r"building|store|shop|bakery|salon|clinic|office|mall|hotel|bank(?!-st)|gas-bar|"
            r"gas-station|wall|restaurant|cafe|schoolyard|school|daycare|church|pharmacy|plaza|"
            r"dealership|apartment|condo|townhouse|garage)(?:-|$)", slug))),
    }
    train = re.search(r"(?:^|-)(?:train|o-train|via-rail|lrt)(?:-|$)", slug)
    # Same order as poll_ops_news.collision_type, so the two sources compare.
    if flags["pedestrian"] or cyclist or motorcycle or flags["off_road"]:
        ctype = next(k for k in ("pedestrian", "cyclist", "motorcycle", "off_road") if flags[k])
    elif train:
        ctype = "train"
    elif flags["building"]:
        ctype = "building"
    elif re.search(r"two-vehicle|multi-vehicle|\d-vehicle|head-on|t-bone|rear-end|snowplow|"
                   r"sidewalk-plow|with-(?:a-)?(?:salt-|tow-)?truck|with-bus|"
                   r"crashing-into-(?:police|oncoming)", slug):
        ctype = "multi_vehicle"
    elif re.search(r"single-(?:vehicle|car)|rollover|(?:^|-)(?:tree|ditch|hydro-pole|barrier)(?:-|$)|"
                   r"into-(?:the-)?(?:mooneys-bay|river|canal|water|lake|bay)", slug):
        ctype = "single_vehicle"
    else:
        ctype = "unknown"
    return {
        "in_ottawa_ops": 0 if out else 1, "out_reason": out, "story_kind": kind,
        "severity": severity, "collision_type": ctype, **flags,
        "hit_and_run": int("hit-and-run" in slug),
    }


# --------------------------------------------------------------------------
# OPS matching
# --------------------------------------------------------------------------

STOP = {"road", "rd", "street", "st", "avenue", "ave", "drive", "dr", "boulevard", "blvd",
        "way", "block", "of", "the", "and", "at", "near", "hwy", "highway", "e", "w", "b",
        "east", "west", "north", "south", "eb", "wb"}


def road_words(location):
    """'700 block of Burton Road' -> {'burton'}; 'Hunt Club Road at Cahill Drive' -> {'hunt-club', 'cahill'}."""
    words = set()
    for part in re.split(r"\b(?:at|near|and)\b|[&/]", location, flags=re.I):
        w = [x for x in re.findall(r"[a-zà-ÿ0-9]+", part.lower()) if x not in STOP and not x.isdigit()]
        if w:
            words.add("-".join(w))
    return words


def load_ops():
    if not OPS.exists():
        return []
    rows = []
    with open(OPS, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["kind"] != "collision":
                continue
            r["_dates"] = {date.fromisoformat(d) for d in (r["incident_date"], r["release_utc"][:10]) if d}
            r["_roads"] = road_words(r["location"])
            rows.append(r)
    return rows


def sev_bucket(s):
    # CTV says "critical"/"serious" where OPS says "life-threatening"; treat them as one.
    return "fatal" if s == "fatal" else "grave" if s in ("critical", "serious") else ""


def match(row, ops):
    """Best OPS release within MATCH_DAYS: same road named (3), same road-user type (2),
    same severity bucket (1). Needs 3+ and a unique best -> (url, 'road' | 'type+date')."""
    if str(row["in_ottawa_ops"]) != "1" or row["story_kind"] == "context":
        return "", ""
    day = date.fromisoformat(row["sitemap_date"])
    best, best_score, best_road, tie = None, 0, False, False
    for r in ops:
        if not any(abs((day - d).days) <= MATCH_DAYS for d in r["_dates"]):
            continue
        road = any(has_place(row["slug"], w) for w in r["_roads"])
        # Without a shared road name, only trust a same-type match from a day apart:
        # "pedestrian dies in Sandy Hill" (Oct 16) is not the Strandherd release (Oct 14).
        if not road and not any(abs((day - d).days) <= 1 for d in r["_dates"]):
            continue
        score = 3 * road
        if row["collision_type"] == r["collision_type"] and row["collision_type"] != "unknown":
            score += 2
        if sev_bucket(row["severity"]) and sev_bucket(row["severity"]) == sev_bucket(r["severity"]):
            score += 1
        # Fatal on one side only: probably another crash on the same road
        # (West Hunt Club hit-and-run vs the Hunt Club motorcycle crash a day earlier).
        if row["severity"] in ("fatal", "critical", "serious") and \
                (row["severity"] == "fatal") != (r["severity"] == "fatal"):
            score -= 3
        if score > best_score:
            best, best_score, best_road, tie = r, score, road, False
        elif score == best_score and score:
            tie = True
    if best is None or best_score < 3 or tie:
        return "", ""
    return best["url"], "road" if best_road else "type+date"


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------

def fetch_day(day):
    req = urllib.request.Request(SITEMAP.format(day=day), headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode("utf-8", "replace")
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(3)
    return parse_sitemap(raw, day)


def parse_sitemap(raw, day):
    out = []
    for block in raw.split("<url>")[1:]:
        loc = re.search(r"<loc>([^<]+)</loc>", block)
        loc, rest = (loc[1].strip(), block) if loc else ("", "")
        if loc.startswith(PREFIX):
            slug = loc[len(PREFIX):].strip("/")
            if CRASH.search(slug):
                m = re.search(r"<lastmod>([^<]+)</lastmod>", rest)
                out.append({"url": loc, "slug": slug, "sitemap_date": str(day),
                            "lastmod_utc": m[1][:19] + "Z" if m else ""})
    return out


def load_rows():
    if not OUT.exists():
        return {}
    with open(OUT, encoding="utf-8") as fh:
        return {r["url"]: r for r in csv.DictReader(fh)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true", help="ignore the hourly gate")
    ap.add_argument("--since", type=date.fromisoformat, help="backfill from this day")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-run the slug rules on every stored row (no fetching)")
    args = ap.parse_args()

    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    now = datetime.now(timezone.utc)
    last = state.get("last_poll_utc")
    if not (args.force or args.since or args.reclassify) and last and \
            now - datetime.fromisoformat(last.replace("Z", "+00:00")) < POLL_EVERY:
        return

    rows, new, failed = load_rows(), 0, []
    if args.reclassify:
        rows = {u: {**r, **classify(r["slug"])} for u, r in rows.items() if CRASH.search(r["slug"])}
    else:
        today = now.astimezone(TZ).date()
        day = args.since or today - timedelta(days=1)
        while day <= today:
            try:
                for r in fetch_day(day):
                    if r["url"] not in rows:      # first sitemap day wins
                        rows[r["url"]] = {**r, **classify(r["slug"])}
                        new += 1
            except Exception as e:
                failed.append(f"{day}: {e}")
            day += timedelta(days=1)
            if args.since and day <= today:
                time.sleep(DAY_PAUSE)

    ops = load_ops()
    for r in rows.values():
        r["matched_ops_url"], r["match_basis"] = match(r, ops)

    DATA.mkdir(exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(rows.values(), key=lambda r: (r["sitemap_date"], r["slug"])))
    if not failed and not args.reclassify:
        state["last_poll_utc"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    if args.since:
        state["backfilled_from"] = min(str(args.since), state.get("backfilled_from", str(args.since)))
    STATE.write_text(json.dumps(state, indent=0, sort_keys=True), encoding="utf-8")

    local = [r for r in rows.values() if str(r["in_ottawa_ops"]) == "1"]
    print(f"ctv_crashes: {new} new, {len(rows)} total, {len(local)} in OPS area, "
          f"{sum(bool(r['matched_ops_url']) for r in local)} matched to an OPS release"
          + (f" | failed {len(failed)} day(s): {failed[0]}" if failed else ""))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
