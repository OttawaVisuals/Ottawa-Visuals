#!/usr/bin/env python3
"""Log Ottawa Police collision and traffic-enforcement news releases.

The City's detailed collision layer stops at 2024 and the OPS traffic-stop
layer at 2024. OPS still publishes a news release for collisions it wants
witnesses for -- mostly fatal or life-threatening ones -- and for enforcement
blitzes. This turns those releases into rows.

It is a SAMPLE, not a dataset: OPS chooses which collisions get a release, so
counts here are a floor, skewed to the most serious. Never append it to the
City series; one collision can also get several releases (initial + "UPDATE").

Source: https://www.ottawapolice.ca/en/news/rss/ -- public, no key. It lists
every post the site still hosts (~216, back to about Dec 2025), so the first
run is the backfill. Each new post's page is fetched once and classified.

Outputs (Traffic/data/):
  * ops_collision_releases.csv -- one row per traffic release (kind =
                                  collision | enforcement), fields extracted
                                  by regex; blank when the text doesn't say.
  * ops_news_seen.json         -- every post link already classified (state),
                                  plus the last successful poll time.

Runs from collect.yml every 5 min but self-gates to hourly (--force skips the
gate). Stdlib only.
"""

import argparse
import csv
import html
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"

RSS_FEED = "https://www.ottawapolice.ca/en/news/rss/"
UA = "Mozilla/5.0 (compatible; ottawa-visuals-collector)"

OUT = DATA / "ops_collision_releases.csv"
STATE = DATA / "ops_news_seen.json"

POLL_EVERY = timedelta(minutes=55)
MAX_FETCH = 25            # post pages per run; the backfill passes --max
FETCH_PAUSE = 1.0         # seconds between post pages

FIELDS = [
    "release_utc", "kind", "follow_up", "incident_date", "incident_time",
    "district", "location", "severity", "collision_type", "pedestrian", "cyclist",
    "motorcycle", "truck", "bus", "hit_and_run", "people_killed", "charges",
    "title", "url",
]

MONTHS = ("January|February|March|April|May|June|July|August|September|"
          "October|November|December")
DAYS = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
ROAD = (r"(?:Road|Rd|Street|St|Avenue|Ave|Drive|Dr|Boulevard|Blvd|Way|Crescent|"
        r"Cres|Lane|Parkway|Pkwy|Place|Court|Terrace|Highway|Hwy|Line|Side ?Road|"
        r"Trail|Gate|Private|Circle|Row)\b\.?")
NUM_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve".split())}


# --------------------------------------------------------------------------
# Fetch
# --------------------------------------------------------------------------

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def parse_rss(raw):
    """-> [{title, url, release_utc}] newest first. pubDate is UTC with no zone."""
    items = []
    for it in ET.fromstring(raw).iter("item"):
        url = (it.findtext("link") or "").strip()
        if not url:
            continue
        pub = (it.findtext("pubDate") or "").strip()
        try:
            utc = datetime.strptime(pub, "%a, %d %B %Y %H:%M:%S").strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            utc = ""
        items.append({"title": (it.findtext("title") or "").strip(), "url": url,
                      "release_utc": utc})
    return items


def page_text(raw):
    """Release body as plain text: the <main> element, one paragraph per line."""
    t = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    m = re.search(r"<main\b.*?</main>", t, re.S | re.I)
    t = m.group(0) if m else t
    t = re.sub(r"<(script|style)\b.*?</\1>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>|</(p|div|h\d|li)>", "\n", t, flags=re.I)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t)).replace("\xa0", " ")
    lines = (re.sub(r"[ \t]+", " ", ln).strip() for ln in t.splitlines())
    return "\n".join(ln for ln in lines if ln)


# --------------------------------------------------------------------------
# Classify + extract
# --------------------------------------------------------------------------

def body_of(text):
    """From the dateline to '— 30 —': drops site chrome and the boilerplate footer."""
    start = re.search(r"FOR IMMEDIATE RELEASE[^\n]*\n?", text, re.I)
    text = text[start.end():] if start else text
    end = re.search(r"[-–—]\s*30\s*[-–—]", text)
    return text[:end.start()] if end else text


def header_of(text):
    start = re.search(r"FOR IMMEDIATE RELEASE", text, re.I)
    return text[:start.start()] if start else text[:400]


def has(pattern, text):
    return 1 if re.search(pattern, text, re.I) else 0


# Road-safety messaging and feature stories, not incidents ("Running towards
# danger: ... heroic actions during Lisbon funicular crash").
ADVISORY = re.compile(r"lives lost|\burge\b|remind|share the road|slow down|safer roads|"
                      r"safety tips|school is back|back[- ]to[- ]school|know your tow|"
                      r"heroic|honou?r|award|celebrat|beeping eggs", re.I)
COLLISION = re.compile(r"collision|crash|hit[- ]and[- ]run|struck by|was struck|"
                       r"pedestrian|\bcyclist|\b(?:drove|drives?|driven|ploughed) into", re.I)
# Traffic enforcement only: "drug trafficking" fails \btraffic\b, and plain
# "driver"/"operation" would pull in carjackings and retail-theft blitzes.
TRAFFIC_ENFORCEMENT = re.compile(r"\btraffic\b|speeding|\bspeed\b|km/?h|stunt|impaired|"
                                 r"\bR\.?I\.?D\.?E\b|commercial vehicle|school zone|"
                                 r"street racing|aggressive driving|unsafe driving|careless|"
                                 r"distracted driving|#ResidentsMatter", re.I)


def classify(title, body):
    """'collision' (a specific incident), 'enforcement' (traffic charges/blitz) or None."""
    lead = body[:600]
    if ADVISORY.search(title):
        return None
    if COLLISION.search(title):
        return "collision"
    if TRAFFIC_ENFORCEMENT.search(title):
        return "enforcement"
    # "Woman dies following injuries sustained on Friel Street": the title is
    # vague, so trust the opening paragraph only if it describes a collision.
    if re.search(r"(responded to|investigating|report of) an? (?:\w+[- ])*"
                 r"(collision|crash|hit-and-run)|struck by an? (vehicle|car|truck|bus|van|SUV)",
                 lead, re.I):
        return "collision"
    return None


def incident_date(body, release_utc):
    m = re.search(rf"(?:{DAYS}),?\s+({MONTHS})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})", body)
    if m:
        try:
            return datetime.strptime(f"{m[1]} {m[2]} {m[3]}", "%B %d %Y").date().isoformat()
        except ValueError:
            pass
    m = re.search(rf"\b({MONTHS})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?!,?\s*\d{{4}})", body)
    if m and release_utc:   # "on October 15" -> the release's year (or the year before)
        rel = datetime.strptime(release_utc[:10], "%Y-%m-%d").date()
        try:
            d = datetime.strptime(f"{m[1]} {m[2]} {rel.year}", "%B %d %Y").date()
        except ValueError:
            return ""
        return (d.replace(year=rel.year - 1) if d > rel else d).isoformat()
    return ""


def incident_time(body):
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m\.?(?![a-z])", body, re.I)
    if not m:
        return ""
    h, mins = int(m[1]) % 12, int(m[2] or 0)
    if m[3].lower() == "p":
        h += 12
    return f"{h:02d}:{mins:02d}" if h < 24 and mins < 60 else ""


W = r"[A-Z0-9][\w'’.-]*"
STREET = rf"(?:{W}\s){{0,4}}?[A-Z][\w'’.-]*\s+{ROAD}(?:\s+(?:East|West|North|South)\b)?"


def location(title, body):
    pats = [
        rf"(\d+\s+block of\s+{STREET})",
        rf"(?:intersection of|area of|in the)\s+({STREET}\s*(?:and|&|/)\s*{STREET})",
        r"\b((?:Highway|Hwy)\s*\d+[^.,;\n]{0,40}?)(?=[.,;\n]| near| in )",
        rf"\b(?:on|at|near|along)\s+({STREET}(?:\s*(?:/|and|&|at|near)\s*{STREET})?)",
    ]
    for p in pats:
        m = re.search(p, body)
        if m:
            return re.sub(r"\s+", " ", m[1]).strip(" .")
    m = re.search(r"\b(?:on|at|in)\s+([A-Z0-9][^;:,\n]+?)\s*(?:;|,|:|$)", title)
    return m[1].strip() if m else ""


# Every release names the unit to call; it says nothing about the outcome.
UNIT = re.compile(r"(?:Fatal\s+)?Collision\s+Investigations?\s+Unit", re.I)


def severity(text):
    t = UNIT.sub("unit", text)
    if re.search(r"\b(fatal|fatality|death of|died|dies|passed away|pronounced (?:dead|deceased)|succumbed|"
                 r"deceased|killed|lost (?:his|her|their) li(?:fe|ves))\b", t, re.I):
        return "fatal"
    t = re.sub(r"non[- ]life[- ]threatening", "NLT", t, flags=re.I)
    if re.search(r"life[- ]threatening|critical(?:ly)? (?:condition|injur)|"
                 r"in critical|critically injured|grave", t, re.I):
        return "critical"
    if re.search(r"serious(?:ly)?\s+(?:\w+\s+)?injur|serious condition", t, re.I):
        return "serious"
    if "NLT" in t:
        return "injury"
    if re.search(r"minor injur|injur|hospital", t, re.I):
        return "injury"
    if re.search(r"no (?:one|injuries)|not injured|uninjured", t, re.I):
        return "none"
    return "unknown"


# Phrases OPS uses for what else was involved. Checked after the road-user
# flags, so "a vehicle and a pedestrian" stays a pedestrian collision.
OFF_ROAD = r"\bATV\b|all[- ]terrain|snowmobile|dirt bike|side-by-side"
TRAIN = r"\btrain\b|railway|rail crossing|level crossing|O-Train|\bLRT\b"
# "a vehicle struck the front of a commercial business" (McArthur, Sep 2026)
BUILDING = (r"(?:into|struck|hit|crashed into) (?:the (?:front|side) of )?(?:a |the )?(?:\w+ )?"
            r"(?:store|storefront|building|home|house|residence|business|restaurant|plaza|"
            r"garage|wall)\b")
MULTI = (r"(?:two|three|four|multi(?:ple)?)[- ]vehicles?\b|head[- ]on|rear[- ]end|t-?boned|"
         r"between (?:two|several) vehicles|vehicles? collided|"
         r"(?:vehicle|car|SUV|sedan|van|truck) and an? (?:\w+ )?(?:vehicle|car|SUV|sedan|van|truck|bus)\b")
SINGLE = (r"single[- ](?:motor[- ])?vehicle|rolled over|rollover|lost control|left the road(?:way)?|"
          r"(?:struck|hit) a (?:pole|tree|guardrail|hydro pole|light standard)|into (?:a|the) ditch")


def collision_type(both, flags):
    """One label per release, most vulnerable road user first."""
    for name in ("pedestrian", "cyclist", "motorcycle"):
        if flags[name]:
            return name
    for name, pat in (("off_road", OFF_ROAD), ("train", TRAIN), ("building", BUILDING),
                      ("multi_vehicle", MULTI), ("single_vehicle", SINGLE)):
        if re.search(pat, both, re.I):
            return name
    return "unknown"


def people_killed(body):
    body = UNIT.sub("unit", body)
    if not re.search(r"\b(fatal|fatality|death|died|dies|pronounced|deceased|killed|succumbed|"
                     r"lost (?:his|her|their) life)\b", body, re.I):
        return ""
    m = re.search(r"\b(\w+) (?:people|persons|occupants|individuals) (?:died|were killed|"
                  r"were pronounced|lost their lives)", body, re.I)
    if m:
        w = m[1].lower()
        return str(int(w) if w.isdigit() else NUM_WORDS.get(w, "")) if (w.isdigit() or w in NUM_WORDS) else ""
    return "1"


def charges(title, body):
    m = re.search(r"(\d[\d,]*)\s+(?:\w+\s+){0,3}(?:charges?|provincial offence notices?|"
                  r"PONs?|tickets?|offence notices?|summons(?:es)?)\b", title + "\n" + body, re.I)
    return m[1].replace(",", "") if m else ""


def extract(item, text):
    """One CSV row for a traffic release, or None for anything else."""
    title, body = item["title"], body_of(text)
    kind = classify(title, body)
    if kind is None:
        return None
    district = re.search(r"\b((?:Rural |Central |)?(?:Central|East|West|South|North|"
                         r"Rural)) District\b", header_of(text))
    row = {
        "release_utc": item["release_utc"], "kind": kind,
        # A later release about an incident already announced: don't double count.
        "follow_up": has(r"^\s*update\b|\b(?:arrested|arrest made|charged|charges laid) in\b",
                         title) if kind == "collision" else 0,
        "district": district[1] if district else "",
        "title": title, "url": item["url"],
    }
    if kind == "enforcement":
        row["charges"] = charges(title, body)
        return row
    both = title + "\n" + body
    cyclist = has(r"\bcyclist|bicycl|\bbike\b|e-bike|e-scooter|electric scooter", both)
    motorcycle = has(r"motorcycl|motorbike|moped", both)
    # "struck by a vehicle" alone means a pedestrian unless a rider is named
    # ("fallen off their bicycle before being struck by an oncoming vehicle").
    pedestrian = int(bool(has(r"pedestrian|was walking|while crossing|crossing guard", both) or (
        has(r"struck by an? (?:\w+[- ])*(?:vehicle|car|truck|bus|van|SUV|sedan)", both)
        and not (cyclist or motorcycle))))
    row.update({
        "incident_date": incident_date(body, item["release_utc"]),
        "incident_time": incident_time(body),
        "location": location(title, body),
        "severity": severity(both),
        "pedestrian": pedestrian, "cyclist": cyclist, "motorcycle": motorcycle,
        "truck": has(r"transport truck|tractor[- ]trailer|dump truck|"
                     r"commercial (?:motor )?vehicle|heavy truck|cement truck|garbage truck", both),
        "bus": has(r"\bbus\b|OC Transpo", both),
        "hit_and_run": has(r"hit[- ]and[- ]run|fled the scene|failed to remain|"
                           r"left the scene|did not remain", both),
        "people_killed": people_killed(body),
    })
    row["collision_type"] = collision_type(both, row)
    return row


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------

def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"last_poll_utc": None, "seen": {}}


def append_rows(rows):
    if not rows:
        return
    new = not OUT.exists()
    with open(OUT, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["release_utc"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true", help="ignore the hourly gate")
    ap.add_argument("--max", type=int, default=MAX_FETCH, help="post pages to fetch this run")
    ap.add_argument("--html-cache", type=Path, help="dev only: keep fetched pages here")
    args = ap.parse_args()

    state = load_state()
    now = datetime.now(timezone.utc)
    last = state.get("last_poll_utc")
    if not args.force and last and now - datetime.fromisoformat(last.replace("Z", "+00:00")) < POLL_EVERY:
        return

    items = parse_rss(get(RSS_FEED))
    todo = [it for it in items if it["url"] not in state["seen"]]
    rows, fetched, failed = [], 0, 0
    for it in reversed(todo):              # oldest first, so a capped run keeps order
        if fetched >= args.max:
            break
        try:
            cached = args.html_cache / (it["url"].rstrip("/").rsplit("/", 1)[-1] + ".html") \
                if args.html_cache else None
            if cached and cached.exists():
                raw = cached.read_bytes()
            else:
                if fetched:
                    time.sleep(FETCH_PAUSE)
                raw = get(it["url"])
                fetched += 1
                if cached:
                    cached.parent.mkdir(parents=True, exist_ok=True)
                    cached.write_bytes(raw)
            row = extract(it, page_text(raw))
        except Exception as e:             # retried next run: not marked seen
            print(f"ops_news: {it['url']}: {e}", file=sys.stderr)
            failed += 1
            continue
        if row:
            rows.append(row)
        state["seen"][it["url"]] = row["kind"] if row else ""

    DATA.mkdir(exist_ok=True)
    append_rows(rows)
    state["last_poll_utc"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    STATE.write_text(json.dumps(state, indent=0, sort_keys=True), encoding="utf-8")
    left = len(todo) - fetched - failed
    print(f"ops_news: {len(items)} in feed, {len(rows)} traffic releases logged"
          + (f", {left} left for next run" if left > 0 and not args.html_cache else "")
          + (f", {failed} failed" if failed else ""))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
