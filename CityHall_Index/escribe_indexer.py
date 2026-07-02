#!/usr/bin/env python3
"""
Ottawa City Hall — universal eScribe indexer.

Builds a structured, queryable index of what every City of Ottawa committee /
council / commission *discussed and decided*, straight from the public eScribe
portal. This is "Stage 1": metadata + decisions, NOT the contents of the PDFs.

It writes five joinable CSVs (join on meeting_id, and item_number where present):

  meetings.csv      one row per meeting        (committee, date, id, url, ...)
  agenda_items.csv  one row per agenda item    (number, title, report #, disposition)
  motions.csv       one row per motion         (text, result)
  votes.csv         one row per councillor-vote (item, motion, vote, councillor)
  attachments.csv   one row per PDF attachment (filename, DocumentId, url)

Data source per meeting (richest first): PostMinutes -> Minutes -> Agenda.
Minutes pages carry dispositions (Carried/Lost/Deferred) and recorded votes;
Agenda-only meetings (e.g. upcoming) still yield items + attachments.

Designed to run unattended: browser UA, OS-trust-store TLS, rate-limited,
retry/backoff, resumable, logged. Roughly ~300 meetings/year across all
committees, so a full multi-year crawl is an overnight job.

Usage
-----
  pip install -r requirements.txt
  python escribe_indexer.py --years 2020-2026                 # all committees
  python escribe_indexer.py --years 2023-2026 --committee transit
  python escribe_indexer.py --years 2025 --limit 5 --verbose   # quick test

Etiquette: public-records site; keep --delay >= 3s, don't run parallel copies.
The resume state avoids re-fetching finished meetings.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import random
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://pub-ottawa.escribemeetings.com/"
USER_AGENT = ("Mozilla/5.0 (X11; Linux aarch64; rv:124.0) "
              "Gecko/20100101 Firefox/124.0")
DEFAULT_DELAY = 3.0
DEFAULT_TIMEOUT = 60
# Pages to try per meeting, richest (has decisions+votes) first.
PAGE_VARIANTS = ["PostMinutes", "Minutes", "Agenda"]
GUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                     r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
ACS_RE = re.compile(r"ACS\d{4}-[A-Z]{2,4}-[A-Z]{2,4}-\d{3,4}")

log = logging.getLogger("escribe")


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-CA,en;q=0.9",
    })
    retry = Retry(total=5, connect=5, read=5, backoff_factor=2.0,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=frozenset(["GET", "POST"]),
                  respect_retry_after_header=True)
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


class Throttle:
    def __init__(self, delay: float):
        self.delay = delay
        self._last = 0.0

    def wait(self):
        if self.delay <= 0:
            return
        gap = self.delay + random.uniform(0, self.delay * 0.4) - \
            (time.monotonic() - self._last)
        if gap > 0:
            time.sleep(gap)
        self._last = time.monotonic()


class State:
    """Remembers which meeting_ids are fully indexed, for resume."""
    def __init__(self, path: Path):
        self.path = path
        self.done = set()
        if path.exists():
            try:
                self.done = set(json.loads(path.read_text("utf-8")))
            except Exception:
                log.warning("Bad state file %s; starting fresh", path)

    def is_done(self, mid): return mid in self.done

    def mark(self, mid):
        self.done.add(mid)
        self.path.write_text(json.dumps(sorted(self.done)), "utf-8")


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
@dataclass
class Meeting:
    meeting_id: str
    committee: str = ""
    date: str = ""
    meeting_type: str = ""

    def url(self, page): return (f"{BASE_URL}Meeting.aspx?Id={self.meeting_id}"
                                 f"&Agenda={page}&lang=English")


# --------------------------------------------------------------------------- #
# Discovery (calendar API)
# --------------------------------------------------------------------------- #
def discover(session, throttle, years, committee_filter="") -> list[Meeting]:
    endpoint = urljoin(BASE_URL, "MeetingsCalendarView.aspx/GetCalendarMeetings")
    needle = committee_filter.lower()
    found: dict[str, Meeting] = {}
    for year in years:
        body = ("{'calendarStartDate':'%d-01-01','calendarEndDate':'%d-12-31'}"
                % (year, year))
        try:
            throttle.wait()
            r = session.post(endpoint, data=body, timeout=DEFAULT_TIMEOUT,
                             headers={"Content-Type": "application/json; charset=UTF-8",
                                      "X-Requested-With": "XMLHttpRequest",
                                      "Referer": f"{BASE_URL}?Year={year}"})
            r.raise_for_status()
            meetings = r.json().get("d") or []
        except Exception as e:
            log.warning("discovery failed for %d: %s", year, e)
            continue
        hits = 0
        for m in meetings:
            name = str(m.get("MeetingName", ""))
            if needle and needle not in name.lower():
                continue
            g = GUID_RE.search(str(m.get("ID", "")))
            if not g:
                continue
            mid = g.group(0)
            found[mid] = Meeting(meeting_id=mid, committee=name,
                                 date=_norm_date(m.get("StartDate", "")),
                                 meeting_type=str(m.get("MeetingType", "")))
            hits += 1
        log.info("%d: %d meeting(s) kept (of %d total)", year, hits, len(meetings))
    return list(found.values())


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def _txt(el, cls):
    e = el.find(class_=cls)
    return e.get_text(" ", strip=True) if e else ""


def _split_names(s: str) -> list[str]:
    s = re.sub(r"\s+and\s+", ", ", s)
    return [n.strip() for n in s.split(",") if n.strip()]


def fetch_meeting_html(session, throttle, meeting: Meeting):
    """Return (soup, page_variant) for the richest page that has real items."""
    fallback = None
    for page in PAGE_VARIANTS:
        throttle.wait()
        try:
            r = session.get(meeting.url(page), timeout=DEFAULT_TIMEOUT)
        except Exception as e:
            log.warning("  fetch %s failed: %s", page, e)
            continue
        if r.status_code != 200:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        if soup.find(class_="AgendaItemContainer"):   # real rendered items
            return soup, page
        fallback = fallback or (soup, page)
    return (None, None) if fallback is None else fallback


_VOTE_RE = re.compile(r"([A-Za-z][A-Za-z /]*?)\s*\((\d+)\)")


def _has(tag, name):
    return tag.has_attr("class") and name in tag["class"]


def parse_meeting(soup, meeting: Meeting):
    """Return (items, motions, votes, attachments) rows for one meeting."""
    items, motions, votes, attachments = [], [], [], []

    for cont in soup.find_all(class_="AgendaItemContainer"):
        number = _txt(cont, "AgendaItemCounter").rstrip(". ").strip()
        title = _txt(cont, "AgendaItemTitle")
        if not number and not title:
            continue
        category = _txt(cont, "AgendaItemCategory")
        sponsors = _txt(cont, "AgendaItemSponsors")
        acs = ACS_RE.search(cont.get_text())
        report_number = acs.group(0) if acs else ""

        # Walk motions + recorded votes in document order so each vote tally
        # (VoterVote, e.g. "For (8)") is paired with the name list (VotesUsers)
        # that follows it and attributed to the current motion.
        disposition = ""
        n_motions = 0
        has_vote = False
        pending = None  # (vote_label, count) awaiting its VotesUsers
        # Items nest (6 contains 6.1); only attribute an element to the
        # *nearest* enclosing container, so parents don't double-count children.
        rel = cont.find_all(lambda t: t.has_attr("class") and any(
            k in t["class"] for k in ("AgendaItemMotion", "VoterVote", "VotesUsers"))
            and t.find_parent(class_="AgendaItemContainer") is cont)
        for n in rel:
            if _has(n, "AgendaItemMotion"):
                n_motions += 1
                result = _txt(n, "MotionResult")
                if result and not disposition:
                    disposition = result
                motions.append({
                    "meeting_id": meeting.meeting_id, "item_number": number,
                    "motion_index": n_motions, "result": result,
                    "motion_text": _txt(n, "MotionText"),
                })
                pending = None
            elif _has(n, "VoterVote"):
                m = _VOTE_RE.search(n.get_text(" ", strip=True))
                pending = ((m.group(1).strip(), m.group(2)) if m
                           else (n.get_text(" ", strip=True), ""))
            elif _has(n, "VotesUsers") and pending is not None:
                label, count = pending
                has_vote = True
                votes.append({
                    "meeting_id": meeting.meeting_id, "item_number": number,
                    "motion_index": max(n_motions, 1), "vote": label,
                    "count": count, "voters": n.get_text(" ", strip=True),
                })
                pending = None

        # attachments for this item
        n_att = 0
        for a in cont.find_all("a", href=True):
            if "filestream.ashx" not in a["href"].lower():
                continue
            if a.find_parent(class_="AgendaItemContainer") is not cont:
                continue  # belongs to a nested child item
            did = parse_qs(urlparse(a["href"]).query).get("DocumentId", [""])[0]
            if not did:
                continue
            n_att += 1
            attachments.append({
                "meeting_id": meeting.meeting_id, "item_number": number,
                "filename": (a.get("data-original-title") or a.get("title")
                             or a.get_text(strip=True) or f"doc_{did}").strip(),
                "document_id": did,
                "url": f"{BASE_URL}filestream.ashx?DocumentId={did}",
            })

        items.append({
            "meeting_id": meeting.meeting_id, "date": meeting.date,
            "committee": meeting.committee, "item_number": number,
            "title": title, "category": category, "sponsors": sponsors,
            "report_number": report_number, "disposition": disposition,
            "n_motions": n_motions, "n_attachments": n_att,
            "has_vote": int(has_vote),
        })
    return items, motions, votes, attachments


# --------------------------------------------------------------------------- #
# CSV sink
# --------------------------------------------------------------------------- #
class CsvSet:
    SPECS = {
        "meetings": ["meeting_id", "date", "committee", "meeting_type",
                     "source_page", "n_items", "url"],
        "agenda_items": ["meeting_id", "date", "committee", "item_number",
                         "title", "category", "sponsors", "report_number",
                         "disposition", "n_motions", "n_attachments", "has_vote"],
        "motions": ["meeting_id", "item_number", "motion_index", "result",
                    "motion_text"],
        "votes": ["meeting_id", "item_number", "motion_index", "vote",
                  "count", "voters"],
        "attachments": ["meeting_id", "item_number", "filename",
                        "document_id", "url"],
    }

    def __init__(self, out_dir: Path):
        self.files, self.writers = {}, {}
        for name, cols in self.SPECS.items():
            path = out_dir / f"{name}.csv"
            new = not path.exists()
            fh = open(path, "a", newline="", encoding="utf-8-sig")
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            if new:
                w.writeheader()
            self.files[name] = fh
            self.writers[name] = w

    def write(self, name, rows):
        if isinstance(rows, dict):
            rows = [rows]
        for row in rows:
            self.writers[name].writerow(row)
        self.files[name].flush()

    def close(self):
        for fh in self.files.values():
            fh.close()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _norm_date(s: str) -> str:
    m = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", str(s))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def parse_years(spec: str) -> range:
    if "-" in spec:
        a, b = spec.split("-", 1)
        return range(int(a), int(b) + 1)
    y = int(spec)
    return range(y, y + 1)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--years", required=True, help="e.g. 2020-2026 or 2025")
    ap.add_argument("--committee", default="",
                    help="only meetings whose name contains this (default: all)")
    ap.add_argument("--out", default="data", help="output dir (default: data)")
    ap.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    ap.add_argument("--limit", type=int, default=0, help="max meetings (0=all)")
    ap.add_argument("--no-resume", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(out_dir / "indexer.log", encoding="utf-8")])

    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        log.debug("truststore not installed; using default TLS trust store")

    session = make_session()
    throttle = Throttle(args.delay)
    state = State(out_dir / "state.json")
    if args.no_resume:
        state.done.clear()

    meetings = discover(session, throttle, parse_years(args.years), args.committee)
    if args.limit:
        meetings = meetings[:args.limit]
    log.info("Indexing %d meeting(s) -> %s", len(meetings), out_dir)

    sink = CsvSet(out_dir)
    tot = {"items": 0, "motions": 0, "votes": 0, "attachments": 0}
    try:
        for i, mtg in enumerate(sorted(meetings, key=lambda m: m.date), 1):
            if state.is_done(mtg.meeting_id):
                continue
            log.info("[%d/%d] %s  %s", i, len(meetings), mtg.date, mtg.committee)
            soup, page = fetch_meeting_html(session, throttle, mtg)
            if soup is None:
                log.warning("  no agenda/minutes page available")
                sink.write("meetings", {
                    "meeting_id": mtg.meeting_id, "date": mtg.date,
                    "committee": mtg.committee, "meeting_type": mtg.meeting_type,
                    "source_page": "", "n_items": 0, "url": mtg.url("Agenda")})
                state.mark(mtg.meeting_id)
                continue
            items, motions, votes, attachments = parse_meeting(soup, mtg)
            sink.write("meetings", {
                "meeting_id": mtg.meeting_id, "date": mtg.date,
                "committee": mtg.committee, "meeting_type": mtg.meeting_type,
                "source_page": page, "n_items": len(items),
                "url": mtg.url(page)})
            sink.write("agenda_items", items)
            sink.write("motions", motions)
            sink.write("votes", votes)
            sink.write("attachments", attachments)
            for k, v in (("items", items), ("motions", motions),
                         ("votes", votes), ("attachments", attachments)):
                tot[k] += len(v)
            log.info("  %s: %d items, %d motions, %d votes, %d attachments",
                     page, len(items), len(motions), len(votes), len(attachments))
            state.mark(mtg.meeting_id)
    finally:
        sink.close()

    log.info("Done. Totals: %d items, %d motions, %d votes, %d attachments -> %s",
             tot["items"], tot["motions"], tot["votes"], tot["attachments"], out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
