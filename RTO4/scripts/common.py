#!/usr/bin/env python3
"""Shared helpers for the RTO4 page's external-data fetchers.

Stdlib only, matching Traffic/scripts/poll_traffic.py and
OC_Transpo/scripts/poll_gtfsrt.py — nothing here needs pip install, so the
scripts run the same on a laptop and on the Pi.

Everything these fetchers produce lands in RTO4/data/ as small JSON files that
rto.html can fetch directly. The rule: aggregate here, never ship a 35 MB CSV
to the browser.
"""

import json
import re
import ssl
import sys
import urllib.parse
import urllib.request
import zipfile
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                       # the RTO4/ directory
DATA = ROOT / "data"

# RTO milestones. Every series on the page is framed against these.
RTO3_DATE = date(2024, 9, 9)             # 3 days/week in office
RTO4_DATE = date(2026, 7, 6)             # 4 days/week in office
RTO4_FULL = date(2026, 9, 15)            # end of the phase-in

UA = {"User-Agent": "Ottawa-Visuals/1.0 (+https://github.com/OttawaVisuals)"}
TIMEOUT = 180

ARCGIS = "https://services.arcgis.com/G6F8XLCl5KtAlZ2G/arcgis/rest/services"


def fetch(url, timeout=TIMEOUT):
    """GET a URL and return raw bytes."""
    req = urllib.request.Request(url, headers=UA)
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.read()


def fetch_json(url, timeout=TIMEOUT):
    return json.loads(fetch(url, timeout).decode("utf-8", "replace"))


def arcgis_query(layer, out_fields="*", where="1=1", result_offset=None):
    """Query an ArcGIS FeatureServer layer, returning the attribute dicts.

    Pages through the 2000-record server limit rather than trusting one call.
    """
    out, offset = [], 0
    while True:
        params = {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": "false",
            "resultOffset": offset,
            "resultRecordCount": 2000,
            "f": "json",
        }
        url = f"{ARCGIS}/{layer}/FeatureServer/0/query?" + urllib.parse.urlencode(params)
        d = fetch_json(url)
        if "error" in d:
            raise RuntimeError(f"{layer}: {d['error'].get('message')}")
        feats = d.get("features", [])
        out += [f["attributes"] for f in feats]
        if not d.get("exceededTransferLimit") or not feats:
            break
        offset += len(feats)
    return out


def week_start(d):
    """Monday of the ISO week containing date d, as an ISO string."""
    return (d - timedelta(days=d.weekday())).isoformat()


def parse_iso(s):
    """Parse a 'YYYY-MM-DD' prefix into a date, or None."""
    if not s:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(s))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def mean(xs, digits=1):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), digits) if xs else None


def write_json(name, payload):
    """Write payload to RTO4/data/<name>, stamping when it was generated."""
    DATA.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, dict):
        payload = {"generated_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), **payload}
    p = DATA / name
    p.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"  wrote {p.relative_to(ROOT.parent)} ({p.stat().st_size/1024:.0f} KB)")
    return p


# ---------------------------------------------------------------- xlsx reading

def read_xlsx(raw):
    """Minimal .xlsx reader: {sheet_name: [[cell, ...], ...]}.

    Open Ottawa publishes several of these datasets as Excel only. Rather than
    take an openpyxl dependency for two files, unzip the OOXML and pull the
    cells out — enough for the flat single-header sheets we consume here.
    Returns cell values as strings (numbers as their raw stored text).
    """
    z = zipfile.ZipFile(BytesIO(raw))

    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        xml = z.read("xl/sharedStrings.xml").decode("utf-8", "replace")
        for si in re.findall(r"<si>(.*?)</si>", xml, re.S):
            shared.append("".join(re.findall(r"<t[^>]*>([^<]*)</t>", si)))

    # workbook.xml gives sheet display names + r:id, and the rels file maps
    # r:id -> the actual worksheets/sheetN.xml path. Order is not guaranteed.
    wb = z.read("xl/workbook.xml").decode("utf-8", "replace")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8", "replace")
    target = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))

    sheets = {}
    for name, rid in re.findall(r'<sheet[^>]*name="([^"]+)"[^>]*r:id="([^"]+)"', wb):
        path = target.get(rid, "")
        path = ("xl/" + path.lstrip("/")) if not path.startswith("xl/") else path
        if path not in z.namelist():
            continue
        sheets[name] = _sheet_rows(z.read(path).decode("utf-8", "replace"), shared)
    return sheets


def _col_index(ref):
    """'AB12' -> 27 (zero-based column index)."""
    letters = re.match(r"([A-Z]+)", ref).group(1)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _sheet_rows(xml, shared):
    rows = []
    for r in re.findall(r"<row[^>]*>(.*?)</row>", xml, re.S):
        cells = {}
        for ref, attrs, inline, val in re.findall(
            r'<c r="([A-Z]+\d+)"([^>]*)(?:/>|>(?:<is>.*?<t[^>]*>([^<]*)</t>.*?</is>)?'
            r"(?:<v>([^<]*)</v>)?.*?</c>)",
            r,
            re.S,
        ):
            if inline:
                v = inline
            elif val and 't="s"' in attrs:
                idx = int(val)
                v = shared[idx] if 0 <= idx < len(shared) else ""
            else:
                v = val or ""
            cells[_col_index(ref)] = v
        if not cells:
            rows.append([])
            continue
        width = max(cells) + 1
        rows.append([cells.get(i, "") for i in range(width)])
    return rows


def run(label, fn):
    """Run one fetcher, reporting failures without killing a batch refresh."""
    print(f"[{label}]")
    try:
        fn()
        return True
    except Exception as e:                                  # noqa: BLE001
        print(f"  FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        return False
