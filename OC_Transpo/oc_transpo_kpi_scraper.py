#!/usr/bin/env python3
"""
OC Transpo Ridership & KPI scraper for Ottawa's eScribe meeting portal.

Designed to run unattended (e.g. overnight on a Raspberry Pi):
  - polite, rate-limited HTTP with a real browser User-Agent
  - automatic retry/backoff on transient errors
  - resumable: re-runs skip meetings/files already done
  - logs to console + file

What it does
------------
1. Builds a list of Transit Committee / Transit Commission meetings, either:
     (a) by querying the eScribe meeting-list API (best effort), and/or
     (b) from a seed file of meeting URLs/IDs you paste in (always works).
2. For each meeting, fetches the agenda page and finds every PDF attachment
   (filestream.ashx?DocumentId=N) together with its filename and agenda-item title.
3. Keeps only attachments whose filename or item title matches the KEYWORDS
   (ridership / KPI / performance / statistics / OC Transpo ...), unless --all.
4. Downloads the matching PDFs into per-meeting folders and writes manifest.csv.
5. Optionally (--extract) pulls text + tables out of each PDF with pdfplumber.

Verified facts (June 2026) baked in as defaults:
  - Browser UA returns HTTP 200; default/empty UA is 403.
  - Attachments: <a href="filestream.ashx?DocumentId=N" data-original-title="X.pdf">
  - Agenda item titles: <div class="AgendaItemTitle">...</div>
  - Meeting page:  Meeting.aspx?Id=<GUID>&Agenda=Agenda&lang=English
  - Transit type IDs: Transit Committee 159*31cc..., Transit Commission 53*ef58...

Usage
-----
  pip install -r requirements.txt
  python oc_transpo_kpi_scraper.py --years 2019-2026 --seed meetings.txt
  python oc_transpo_kpi_scraper.py --seed meetings.txt --extract       # also parse PDFs
  python oc_transpo_kpi_scraper.py --seed meetings.txt --all --dry-run  # preview, download nothing

Be a good citizen: this hits a public-records site. Keep --delay reasonable,
don't run many copies in parallel, and cache (the resume logic already does).
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
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
BASE_URL = "https://pub-ottawa.escribemeetings.com/"

# Realistic desktop UA — the site 403s default/empty agents.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux aarch64; rv:124.0) Gecko/20100101 Firefox/124.0"
)

# Meeting-type filter values used by the eScribe list API (id*siteGuid).
TRANSIT_TYPES = {
    "Transit Committee": "159*31cc7ee0-0c69-44af-b8f2-f0f80e9606c3",
    "Transit Commission": "53*ef58236b-fce9-45cc-becf-c31c7a95d20f",
    "Joint Transportation Committee and Transit Commission": "38*ef58236b-fce9-45cc-becf-c31c7a95d20f",
    "Joint Transit Commission and Light Rail Sub-Committee": "151*31cc7ee0-0c69-44af-b8f2-f0f80e9606c3",
    "Joint Audit Committee and Transit Commission": "146*31cc7ee0-0c69-44af-b8f2-f0f80e9606c3",
}

# An attachment is kept if any of these appears in its filename or item title.
KEYWORDS = [
    "ridership", "kpi", "key performance", "performance", "statistic",
    "oc transpo update", "transit service", "service level", "metrics",
    "dashboard", "monitoring report", "quarterly", "annual report",
    "boarding", "on-time", "reliability", "para transpo", "o-train",
]

# Agenda variants to try, in order (English).
AGENDA_VARIANTS = ["Agenda", "PostMinutes", "Minutes"]

DEFAULT_DELAY = 3.0          # seconds between requests
DEFAULT_TIMEOUT = 60         # per-request timeout (seconds)
GUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                     r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

log = logging.getLogger("octranspo")


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass
class Meeting:
    meeting_id: str                 # GUID
    name: str = ""
    date: str = ""                  # YYYY-MM-DD if known
    agenda: str = "Agenda"

    def url(self) -> str:
        return (f"{BASE_URL}Meeting.aspx?Id={self.meeting_id}"
                f"&Agenda={self.agenda}&lang=English")


@dataclass
class Attachment:
    document_id: str
    filename: str
    item_title: str
    meeting: Meeting = field(repr=False, default=None)

    def url(self) -> str:
        return f"{BASE_URL}filestream.ashx?DocumentId={self.document_id}"


# --------------------------------------------------------------------------- #
# HTTP session (UA + retry/backoff)
# --------------------------------------------------------------------------- #
def make_session(verify: bool | str = True) -> requests.Session:
    s = requests.Session()
    s.verify = verify
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-CA,en;q=0.9",
    })
    retry = Retry(
        total=5, connect=5, read=5,
        backoff_factor=2.0,                       # 0,2,4,8,16s
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST"]),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


class Throttle:
    """Sleep `delay` (+jitter) between requests."""
    def __init__(self, delay: float):
        self.delay = delay
        self._last = 0.0

    def wait(self):
        if self.delay <= 0:
            return
        elapsed = time.monotonic() - self._last
        gap = self.delay + random.uniform(0, self.delay * 0.4) - elapsed
        if gap > 0:
            time.sleep(gap)
        self._last = time.monotonic()


# --------------------------------------------------------------------------- #
# Resume state
# --------------------------------------------------------------------------- #
class State:
    def __init__(self, path: Path):
        self.path = path
        self.data = {"meetings_done": [], "docs_done": []}
        if path.exists():
            try:
                self.data.update(json.loads(path.read_text("utf-8")))
            except Exception:
                log.warning("Could not read state file %s; starting fresh", path)
        self._meetings = set(self.data["meetings_done"])
        self._docs = set(self.data["docs_done"])

    def meeting_done(self, mid: str) -> bool:
        return mid in self._meetings

    def mark_meeting(self, mid: str):
        if mid not in self._meetings:
            self._meetings.add(mid)
            self.data["meetings_done"].append(mid)
            self.save()

    def doc_done(self, did: str) -> bool:
        return did in self._docs

    def mark_doc(self, did: str):
        if did not in self._docs:
            self._docs.add(did)
            self.data["docs_done"].append(did)
            self.save()

    def save(self):
        self.path.write_text(json.dumps(self.data, indent=0), "utf-8")


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #
def discover_via_api(session: requests.Session, throttle: Throttle,
                     years: range, committee: str) -> list[Meeting]:
    """
    Enumerate meetings via eScribe's calendar page method and keep those whose
    MeetingName matches `committee` (case-insensitive substring, e.g. "transit").

    One JSON POST per year to GetCalendarMeetings returns every meeting in the
    range; we filter client-side. (The param names are calendarStartDate /
    calendarEndDate — verified against the live portal.)
    """
    found: dict[str, Meeting] = {}
    endpoint = urljoin(BASE_URL, "MeetingsCalendarView.aspx/GetCalendarMeetings")
    needle = committee.lower()
    for year in years:
        body = ("{'calendarStartDate':'%d-01-01','calendarEndDate':'%d-12-31'}"
                % (year, year))
        try:
            throttle.wait()
            r = session.post(
                endpoint,
                headers={"Content-Type": "application/json; charset=UTF-8",
                         "X-Requested-With": "XMLHttpRequest",
                         "Referer": f"{BASE_URL}?Year={year}"},
                data=body, timeout=DEFAULT_TIMEOUT,
            )
            r.raise_for_status()
            meetings = r.json().get("d") or []
        except Exception as e:
            log.warning("API discovery failed for %d: %s", year, e)
            continue
        hits = 0
        for m in meetings:
            name = str(m.get("MeetingName", ""))
            if needle not in name.lower():
                continue
            g = GUID_RE.search(str(m.get("ID", "")))
            if not g:
                continue
            mid = g.group(0)
            found[mid] = Meeting(meeting_id=mid, name=name,
                                 date=_norm_date(m.get("StartDate", "")))
            hits += 1
        log.info("API: %d '%s' meeting(s) found for %d (of %d total)",
                 hits, committee, year, len(meetings))
    if not found:
        log.warning("API discovery found no '%s' meetings — check --committee / "
                    "--years, or use --seed meetings.txt.", committee)
    return list(found.values())


def load_seed(path: Path) -> list[Meeting]:
    """Read meeting URLs or bare GUIDs, one per line (# = comment)."""
    out: dict[str, Meeting] = {}
    if not path or not path.exists():
        return []
    for raw in path.read_text("utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        g = GUID_RE.search(line)
        if not g:
            log.warning("No meeting GUID found in seed line: %s", line)
            continue
        mid = g.group(0)
        agenda = "Agenda"
        if "Agenda=" in line:
            agenda = parse_qs(urlparse(line).query).get("Agenda", ["Agenda"])[0]
        out[mid] = Meeting(meeting_id=mid, agenda=agenda)
    log.info("Loaded %d meeting(s) from seed file %s", len(out), path)
    return list(out.values())


# --------------------------------------------------------------------------- #
# Agenda parsing
# --------------------------------------------------------------------------- #
def fetch_agenda_html(session, throttle, meeting: Meeting) -> str | None:
    for variant in [meeting.agenda] + [v for v in AGENDA_VARIANTS
                                       if v != meeting.agenda]:
        meeting.agenda = variant
        throttle.wait()
        try:
            r = session.get(meeting.url(), timeout=DEFAULT_TIMEOUT)
        except Exception as e:
            log.warning("  fetch failed (%s): %s", variant, e)
            continue
        if r.status_code == 200 and "filestream.ashx" in r.text.lower():
            return r.text
        log.debug("  %s -> HTTP %s (no attachments)", variant, r.status_code)
    return None


def parse_attachments(html: str, meeting: Meeting) -> list[Attachment]:
    """
    Walk the document in source order, tracking the most recent agenda-item
    title, and attach it to each filestream link encountered.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Pull meeting name/date from the page title/header if not already known.
    if not meeting.name:
        t = soup.find("title")
        if t:
            meeting.name = t.get_text(strip=True)
    if not meeting.date:
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", html) or \
            re.search(r"(January|February|March|April|May|June|July|August|"
                      r"September|October|November|December)\s+\d{1,2},\s+\d{4}",
                      html, re.I)
        if m:
            meeting.date = _norm_date(m.group(0))

    attachments: list[Attachment] = []
    current_title = ""
    for el in soup.find_all(True):
        classes = " ".join(el.get("class", []))
        if "AgendaItemTitle" in classes and "Row" not in classes:
            txt = el.get_text(" ", strip=True)
            if txt:
                current_title = txt
        href = el.get("href", "") if el.name == "a" else ""
        if "filestream.ashx" in href.lower():
            did = parse_qs(urlparse(href).query).get("DocumentId", [""])[0]
            if not did:
                continue
            fname = (el.get("data-original-title")
                     or el.get("title")
                     or el.get_text(strip=True)
                     or f"document_{did}.pdf")
            attachments.append(Attachment(
                document_id=did, filename=fname.strip(),
                item_title=current_title, meeting=meeting))
    return attachments


def keep(att: Attachment, keep_all: bool) -> bool:
    if keep_all:
        return True
    hay = f"{att.filename} {att.item_title}".lower()
    return any(k in hay for k in KEYWORDS)


# --------------------------------------------------------------------------- #
# Download + extract
# --------------------------------------------------------------------------- #
def safe_name(s: str, maxlen: int = 120) -> str:
    s = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", s).strip(" .")
    return (s or "untitled")[:maxlen]


def download(session, throttle, att: Attachment, dest: Path,
             dry_run: bool) -> Path | None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        log.info("    skip (exists): %s", dest.name)
        return dest
    if dry_run:
        log.info("    [dry-run] would download: %s", att.filename)
        return None
    throttle.wait()
    try:
        with session.get(att.url(), timeout=DEFAULT_TIMEOUT, stream=True) as r:
            if r.status_code != 200:
                log.warning("    HTTP %s for DocumentId=%s", r.status_code,
                            att.document_id)
                return None
            tmp = dest.with_suffix(dest.suffix + ".part")
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(64 * 1024):
                    fh.write(chunk)
            tmp.replace(dest)
        log.info("    saved: %s (%d KB)", dest.name, dest.stat().st_size // 1024)
        return dest
    except Exception as e:
        log.warning("    download error DocumentId=%s: %s", att.document_id, e)
        return None


def extract_pdf(pdf: Path):
    """Dump text + tables next to the PDF. Needs pdfplumber (optional)."""
    try:
        import pdfplumber
    except ImportError:
        log.warning("    --extract needs pdfplumber: pip install pdfplumber")
        return
    try:
        text_out, tables = [], []
        with pdfplumber.open(pdf) as doc:
            for i, page in enumerate(doc.pages, 1):
                text_out.append(f"\n----- page {i} -----\n")
                text_out.append(page.extract_text() or "")
                for tbl in page.extract_tables():
                    tables.append((i, tbl))
        pdf.with_suffix(".txt").write_text("".join(text_out), "utf-8")
        if tables:
            with open(pdf.with_suffix(".tables.csv"), "w", newline="",
                      encoding="utf-8") as fh:
                w = csv.writer(fh)
                for page_no, tbl in tables:
                    w.writerow([f"# page {page_no}"])
                    for row in tbl:
                        w.writerow([("" if c is None else c) for c in row])
                    w.writerow([])
        log.info("    extracted text%s", " + tables" if tables else "")
    except Exception as e:
        log.warning("    extract failed for %s: %s", pdf.name, e)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _norm_date(s: str) -> str:
    s = str(s)
    m = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(January|February|March|April|May|June|July|August|"
                  r"September|October|November|December)\s+(\d{1,2}),\s+(\d{4})",
                  s, re.I)
    if m:
        months = {mn: i for i, mn in enumerate(
            ["january", "february", "march", "april", "may", "june", "july",
             "august", "september", "october", "november", "december"], 1)}
        return f"{m.group(3)}-{months[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
    return ""


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
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data", help="output directory (default: data)")
    ap.add_argument("--seed", type=Path, help="file of meeting URLs/GUIDs, one per line")
    ap.add_argument("--years", default="", help="e.g. 2019-2026 — auto-discover meetings")
    ap.add_argument("--committee", default="transit",
                    help="substring to match meeting names during --years "
                         "discovery (default: transit)")
    ap.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                    help=f"seconds between requests (default {DEFAULT_DELAY})")
    ap.add_argument("--all", action="store_true",
                    help="download every attachment, not just KPI/ridership ones")
    ap.add_argument("--extract", action="store_true",
                    help="extract text+tables from each PDF (needs pdfplumber)")
    ap.add_argument("--limit", type=int, default=0, help="max meetings (0 = all)")
    ap.add_argument("--dry-run", action="store_true", help="list, download nothing")
    ap.add_argument("--no-resume", action="store_true", help="ignore saved state")
    ap.add_argument("--insecure", action="store_true",
                    help="skip TLS verification (only if your cert store is broken)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(out_dir / "scraper.log", encoding="utf-8")],
    )

    # The eScribe server sends an incomplete cert chain (missing intermediate),
    # which trips certifi-only verification. Use the OS-native trust store via
    # `truststore` (handles this the way browsers/curl do) — still fully verified.
    verify: bool | str = True
    if args.insecure:
        verify = False
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        log.warning("TLS verification DISABLED (--insecure).")
    else:
        try:
            import truststore
            truststore.inject_into_ssl()
            log.debug("Using OS-native trust store (truststore).")
        except ImportError:
            try:
                import certifi
                verify = certifi.where()
                log.debug("truststore not installed; falling back to certifi.")
            except ImportError:
                pass

    session = make_session(verify)
    throttle = Throttle(args.delay)
    state = State(out_dir / "state.json")
    if args.no_resume:
        state._meetings.clear(); state._docs.clear()

    # ---- build meeting list ----
    meetings: dict[str, Meeting] = {}
    for m in load_seed(args.seed):
        meetings[m.meeting_id] = m
    if args.years:
        for m in discover_via_api(session, throttle, parse_years(args.years),
                                  args.committee):
            meetings.setdefault(m.meeting_id, m)
    if not meetings:
        log.error("No meetings to process. Provide --seed meetings.txt and/or "
                  "--years 2019-2026. See README.md.")
        return 2

    meeting_list = list(meetings.values())
    if args.limit:
        meeting_list = meeting_list[:args.limit]
    log.info("Processing %d meeting(s); output -> %s", len(meeting_list), out_dir)

    # ---- manifest ----
    manifest_path = out_dir / "manifest.csv"
    new_manifest = not manifest_path.exists()
    mf = open(manifest_path, "a", newline="", encoding="utf-8")
    writer = csv.writer(mf)
    if new_manifest:
        writer.writerow(["meeting_date", "meeting_name", "item_title",
                         "filename", "document_id", "download_url", "local_path"])

    kept_total = 0
    for i, meeting in enumerate(meeting_list, 1):
        if state.meeting_done(meeting.meeting_id) and not args.dry_run:
            log.info("[%d/%d] skip done meeting %s", i, len(meeting_list),
                     meeting.meeting_id)
            continue
        log.info("[%d/%d] meeting %s %s", i, len(meeting_list),
                 meeting.date or "", meeting.name or meeting.meeting_id)
        html = fetch_agenda_html(session, throttle, meeting)
        if not html:
            log.warning("  no agenda/attachments found; skipping")
            continue
        attachments = parse_attachments(html, meeting)
        kept = [a for a in attachments if keep(a, args.all)]
        log.info("  %d attachment(s), %d match filter", len(attachments), len(kept))

        folder = out_dir / safe_name(f"{meeting.date or '0000'}_{meeting.name}")
        for att in kept:
            if state.doc_done(att.document_id) and not args.dry_run:
                continue
            dest = folder / safe_name(att.filename or f"doc_{att.document_id}.pdf")
            if not dest.suffix:
                dest = dest.with_suffix(".pdf")
            saved = download(session, throttle, att, dest, args.dry_run)
            writer.writerow([meeting.date, meeting.name, att.item_title,
                             att.filename, att.document_id, att.url(),
                             str(saved) if saved else ""])
            mf.flush()
            if saved:
                kept_total += 1
                if args.extract and saved.suffix.lower() == ".pdf":
                    extract_pdf(saved)
                state.mark_doc(att.document_id)
        if not args.dry_run:
            state.mark_meeting(meeting.meeting_id)

    mf.close()
    log.info("Done. %d file(s) saved this run. Manifest: %s", kept_total,
             manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
