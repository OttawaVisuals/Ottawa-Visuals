#!/usr/bin/env python3
"""
Ottawa City Hall — universal eScribe indexer.

Builds a structured, queryable index of what every City of Ottawa committee /
council / commission *discussed and decided*, straight from the public eScribe
portal. This is "Stage 1": metadata + decisions, NOT the contents of the PDFs.

It writes six joinable CSVs (join on meeting_id, and item_number where present):

  meetings.csv      one row per meeting        (committee, date, id, url, ...)
  agenda_items.csv  one row per agenda item    (number, title, report #, disposition)
  motions.csv       one row per motion         (text, result)
  votes.csv         one row per councillor-vote (item, motion, vote, councillor)
  attachments.csv   one row per PDF attachment (filename, DocumentId, url)
  item_text.csv     one row per agenda item    (all text shown on the page for it:
                    report summary, recommendations, motions, directions to
                    staff, minutes notes)

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
  python escribe_indexer.py --years recent --refresh-days 120   # weekly update

Etiquette: public-records site; keep --delay >= 3s, don't run parallel copies.
--refresh-days N re-indexes meetings dated in the last N days (or upcoming) that
were indexed before their minutes were posted (Agenda-only page, or no items):
their rows are removed from every CSV and written again from the current page.

The resume state avoids re-fetching finished meetings. item_text has its own
state file, so re-running over meetings indexed before it existed backfills
their text without duplicating rows in the other CSVs.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import logging
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, timedelta
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
LOCKED = 3                 # exit code when another run holds the lock
LOCK_STALE_S = 24 * 3600   # older lock = left over from a crash
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

    def unmark(self, mids):
        self.done -= set(mids)
        self.path.write_text(json.dumps(sorted(self.done)), "utf-8")

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
        # eScribe redirects e.g. PostMinutes -> Agenda when minutes aren't
        # published; record the page actually served.
        served = parse_qs(urlparse(r.url).query).get("Agenda", [page])[0]
        soup = BeautifulSoup(r.text, "html.parser")
        if soup.find(class_="AgendaItemContainer"):   # real rendered items
            return soup, served
        fallback = fallback or (soup, served)
    return (None, None) if fallback is None else fallback


_VOTE_RE = re.compile(r"([A-Za-z][A-Za-z /]*?)\s*\((\d+)\)")


def _has(tag, name):
    return tag.has_attr("class") and name in tag["class"]


# Parts of an item container that aren't the item's own text: nested child
# items (indexed separately), the title row (already in agenda_items) and the
# attachment list / icons / navigation chrome.
_NOT_OWN_TEXT = ["AgendaItemContainer", "AgendaItemTitleRow",
                 "AgendaItemAttachmentsList", "AgendaItemIcons",
                 "AgendaItemNavigate"]
_BLOCK_TAGS = ["p", "div", "li", "tr", "td", "h1", "h2", "h3", "h4", "h5",
               "h6", "ul", "ol", "table", "section"]


def _own_text(cont) -> str:
    """All text shown for this item, one line per block, children excluded."""
    return _block_text(cont, _NOT_OWN_TEXT)


def _page_text(soup) -> str:
    """Whole-meeting text for pages with no AgendaItemContainer structure
    (pre-2022 meetings are Word-exported HTML: full text, no item breakdown)."""
    body = (soup.find("section", class_="Agenda") or soup.find("article", class_="Meeting")
            or soup.find("main"))
    return _block_text(body, ["dropdown-item", "sr-only"]) if body else ""


def _block_text(el, drop_classes) -> str:
    c = copy.copy(el)
    for sub in c.find_all(class_=drop_classes):
        sub.decompose()
    for sub in c.find_all(["script", "style"]):
        sub.decompose()
    # Newlines only at block boundaries, so inline links/emphasis (and the hard
    # wraps in Word-exported HTML) don't split sentences across lines.
    for s in c.find_all(string=True):
        s.replace_with(re.sub(r"\s+", " ", s))
    for br in c.find_all("br"):
        br.replace_with("\n")
    for blk in c.find_all(_BLOCK_TAGS):
        blk.append("\n")
    lines = (ln.strip() for ln in c.get_text("").splitlines())
    return "\n".join(re.sub(r"[ \t\xa0]+", " ", ln) for ln in lines if ln)


def parse_meeting(soup, meeting: Meeting, page: str = ""):
    """Return (items, motions, votes, attachments, item_text) rows for one meeting."""
    items, motions, votes, attachments, texts = [], [], [], [], []

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

        text = _own_text(cont)
        texts.append({
            "meeting_id": meeting.meeting_id, "item_number": number,
            "source_page": page, "n_chars": len(text), "text": text,
        })

        items.append({
            "meeting_id": meeting.meeting_id, "date": meeting.date,
            "committee": meeting.committee, "item_number": number,
            "title": title, "category": category, "sponsors": sponsors,
            "report_number": report_number, "disposition": disposition,
            "n_motions": n_motions, "n_attachments": n_att,
            "has_vote": int(has_vote),
        })
    if not items:
        # No item structure: keep the whole page as one item_text row with an
        # empty item_number, so the meeting is still searchable.
        text = _page_text(soup)
        if text:
            texts.append({"meeting_id": meeting.meeting_id, "item_number": "",
                          "source_page": page, "n_chars": len(text), "text": text})
    return items, motions, votes, attachments, texts


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
        "item_text": ["meeting_id", "item_number", "source_page", "n_chars",
                      "text"],
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
    if spec == "recent":   # last year through next year
        y = date.today().year
        return range(y - 1, y + 2)
    if "-" in spec:
        a, b = spec.split("-", 1)
        return range(int(a), int(b) + 1)
    y = int(spec)
    return range(y, y + 1)


def stale_meetings(out_dir: Path, days: int) -> dict[str, dict]:
    """Meetings dated within `days` (or in the future) that were indexed from a
    page without minutes: Agenda/Minutes rather than PostMinutes, or no items.
    Returns meeting_id -> its meetings.csv row."""
    path = out_dir / "meetings.csv"
    if not path.exists():
        return {}
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return {r["meeting_id"]: r for r in csv.DictReader(fh)
                if r["date"] >= cutoff
                and (r["source_page"] != "PostMinutes" or r["n_items"] in ("", "0"))}


def purge_meetings(out_dir: Path, mids: set[str]) -> int:
    """Remove every row of these meetings from all CSVs (rewritten in place)."""
    removed = 0
    for name, cols in CsvSet.SPECS.items():
        path = out_dir / f"{name}.csv"
        if not path.exists():
            continue
        with open(path, encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        keep = [r for r in rows if r["meeting_id"] not in mids]
        removed += len(rows) - len(keep)
        tmp = path.with_suffix(".csv.tmp")
        with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(keep)
        tmp.replace(path)
    return removed


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--years", required=True,
                    help="e.g. 2020-2026, 2025, or 'recent' (last year to next year)")
    ap.add_argument("--committee", default="",
                    help="only meetings whose name contains this (default: all)")
    ap.add_argument("--out", default="data", help="output dir (default: data)")
    ap.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    ap.add_argument("--limit", type=int, default=0, help="max meetings (0=all)")
    ap.add_argument("--no-resume", action="store_true")
    ap.add_argument("--refresh-days", type=int, default=0,
                    help="re-index meetings from the last N days still lacking minutes")
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

    # One indexer per output folder: two would append to the same CSVs.
    lock = out_dir / "indexer.lock"
    if lock.exists() and time.time() - lock.stat().st_mtime < LOCK_STALE_S:
        log.error("Another indexer is running on %s (%s); remove it if that run "
                  "crashed.", out_dir, lock.name)
        return LOCKED
    lock.write_text(f"pid {os.getpid()} since {time.strftime('%Y-%m-%d %H:%M:%S')}", "utf-8")
    try:
        return _run(args, out_dir)
    finally:
        lock.unlink(missing_ok=True)


def _run(args, out_dir: Path) -> int:
    session = make_session()
    throttle = Throttle(args.delay)
    state = State(out_dir / "state.json")
    text_state = State(out_dir / "state_text.json")
    if args.no_resume:
        state.done.clear()
        text_state.done.clear()

    meetings = discover(session, throttle, parse_years(args.years), args.committee)
    on_calendar = {m.meeting_id for m in meetings}
    # Years the calendar actually answered for (a failed request must not look
    # like every meeting of that year vanished).
    answered = {m.date[:4] for m in meetings}
    if args.limit:
        meetings = meetings[:args.limit]

    if args.refresh_days:
        stale = stale_meetings(out_dir, args.refresh_days)
        # Still on the calendar: purge, then re-index below.
        redo = set(stale) & on_calendar
        # Gone from the calendar (eScribe replaces placeholder meetings with new
        # IDs, and drops cancelled ones): purge only, within the years/committee
        # this run covers.
        gone = {mid for mid, r in stale.items() if mid not in on_calendar
                and r["date"][:4] in answered
                and args.committee.lower() in r["committee"].lower()}
        if redo or gone:
            n = purge_meetings(out_dir, redo | gone)
            state.unmark(redo | gone)
            text_state.unmark(redo | gone)
            log.info("Refresh: re-indexing %d meeting(s) indexed before their minutes, "
                     "dropping %d no longer on the calendar; removed %d row(s)",
                     len(redo), len(gone), n)
    log.info("Indexing %d meeting(s) -> %s", len(meetings), out_dir)

    sink = CsvSet(out_dir)
    tot = {"items": 0, "motions": 0, "votes": 0, "attachments": 0, "item_text": 0}
    try:
        for i, mtg in enumerate(sorted(meetings, key=lambda m: m.date), 1):
            text_only = state.is_done(mtg.meeting_id)
            if text_only and text_state.is_done(mtg.meeting_id):
                continue
            log.info("[%d/%d] %s  %s%s", i, len(meetings), mtg.date, mtg.committee,
                     "  (text backfill)" if text_only else "")
            soup, page = fetch_meeting_html(session, throttle, mtg)
            if text_only:
                # Indexed before item_text existed: add only the text rows.
                if soup is not None:
                    texts = parse_meeting(soup, mtg, page)[4]
                    sink.write("item_text", texts)
                    tot["item_text"] += len(texts)
                    log.info("  %s: %d item texts", page, len(texts))
                text_state.mark(mtg.meeting_id)
                continue
            if soup is None:
                log.warning("  no agenda/minutes page available")
                sink.write("meetings", {
                    "meeting_id": mtg.meeting_id, "date": mtg.date,
                    "committee": mtg.committee, "meeting_type": mtg.meeting_type,
                    "source_page": "", "n_items": 0, "url": mtg.url("Agenda")})
                state.mark(mtg.meeting_id)
                text_state.mark(mtg.meeting_id)
                continue
            items, motions, votes, attachments, texts = parse_meeting(soup, mtg, page)
            sink.write("meetings", {
                "meeting_id": mtg.meeting_id, "date": mtg.date,
                "committee": mtg.committee, "meeting_type": mtg.meeting_type,
                "source_page": page, "n_items": len(items),
                "url": mtg.url(page)})
            sink.write("agenda_items", items)
            sink.write("motions", motions)
            sink.write("votes", votes)
            sink.write("attachments", attachments)
            sink.write("item_text", texts)
            for k, v in (("items", items), ("motions", motions),
                         ("votes", votes), ("attachments", attachments),
                         ("item_text", texts)):
                tot[k] += len(v)
            log.info("  %s: %d items, %d motions, %d votes, %d attachments",
                     page, len(items), len(motions), len(votes), len(attachments))
            state.mark(mtg.meeting_id)
            text_state.mark(mtg.meeting_id)
    finally:
        sink.close()

    log.info("Done. Totals: %d items, %d motions, %d votes, %d attachments, "
             "%d item texts -> %s", tot["items"], tot["motions"], tot["votes"],
             tot["attachments"], tot["item_text"], out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
