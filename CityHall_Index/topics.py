"""Topic, routine-item and result-bucket rules shared by the public exports.

Topics are a best-effort guess: title keywords first (first match wins, in the
order below), then the body that handled the item. Anything else is "Other".
"""
import re

ROUTINE = re.compile(
    r"^(minutes\b|motion to (introduce|adopt)|confirmation by-?law|three readings|roadmap motion|"
    r"adjournment|call to order|roll call|regrets|declarations? of interest|orders? of the day|"
    r"approval of (the )?(agenda|minutes)|confirmation of minutes|in camera|"
    r"notice of motion|motions? of which notice|suspension of rules|summary of oral and written|"
    r"disposition of items|status update - council inquiries|confidential minutes|"
    r"(councillor|mayor)\s+[a-z]\.\s*[a-z'\-]+(\s+[a-z'\-]+)?$|"
    r".{0,80}committee report \d+)", re.I)

# (topic, title regex) in priority order
TITLE_RULES = [
    ("Transit", r"\btransit\b|oc transpo|light rail|\blrt\b|paratranspo|\bstage 2\b|\bO-train\b|\bbus(es)?\b"),
    ("Housing & homelessness", r"\bhousing\b|homeless|shelter|affordab|\btenants?\b|encampment|\brent(al)?\b"),
    ("Budget, taxes & fees", r"\bbudget|\btaxes?\b|\btaxation\b|\blevy\b|user fees?|\bfees? (and|&) charges|development charges?|"
                            r"\bborrowing|debenture|\bfinancial\b|\bpayment in lieu|\bfunding\b"),
    ("Planning & zoning", r"zoning|official plan|by-law amendment|site plan|subdivision|severance|minor variance|"
                          r"demolition|urban boundary|\bland use\b|secondary plan|community design plan"),
    ("Heritage", r"heritage|designat(e|ion)\b"),
    ("Roads, cycling & safety", r"\btransportation\b|\broads?\b|\btraffic\b|\bcycling\b|\bbike|\bsidewalk|\bspeed\b|pedestrian|vision zero|"
                                r"\bparking\b|\bstreets?\b|\bbridge\b|\bstop control|\bintersection"),
    ("Police & public safety", r"\bpolice\b|policing|fire services|paramedic|by-law (and|&) regulatory|emergency"),
    ("Environment & climate", r"climate|\benergy\b|\bwaste\b|\bwater\b|sewer|environment|\btrees?\b|\bgreen\b|"
                              r"stormwater|flood|\bparks?\b|organics|recycl|solid waste"),
    ("Health, community & library", r"\bhealth\b|library|\bsocial\b|long-term care|recreation|community (services|safety)|"
                                    r"\bseniors?\b|\byouth\b|\bchild"),
    ("Governance, audits & admin", r"governance|code of conduct|council (remuneration|procedure)|integrity commissioner|"
                                   r"auditor general|\baudit\b|city clerk|collective bargaining|rules of procedure|"
                                   r"\bby-?laws?\b|\belection|expense policy|remuneration|vacant office"),
]
_TITLE = [(t, re.compile(p, re.I)) for t, p in TITLE_RULES]

BODY_TOPIC = [
    (r"transit|light rail", "Transit"),
    (r"police", "Police & public safety"),
    (r"emergency preparedness", "Police & public safety"),
    (r"planning|committee of adjustment|committee of revision", "Planning & zoning"),
    (r"built heritage", "Heritage"),
    (r"finance|debenture|investment board", "Budget, taxes & fees"),
    (r"health|library|community services|accessibility|french language", "Health, community & library"),
    (r"environment|water|waste", "Environment & climate"),
    (r"transportation|public works|infrastructure", "Roads, cycling & safety"),
]
_BODY = [(re.compile(p, re.I), t) for p, t in BODY_TOPIC]
TOPICS = [t for t, _ in TITLE_RULES] + ["Other"]


def is_routine(title: str) -> bool:
    return bool(ROUTINE.match(title.strip()))


def topic_of(title: str, body: str) -> str:
    for t, rx in _TITLE:
        if rx.search(title):
            return t
    if body != "City Council":
        for rx, t in _BODY:
            if rx.search(body):
                return t
    return "Other"


def result_bucket(result: str) -> str:
    r = result.split(" (")[0].strip().lower()
    if r.startswith("carried"):
        return "Carried"
    if r.startswith("lost"):
        return "Lost"
    if r.startswith("received"):
        return "Received"
    if r.startswith("withdrawn"):
        return "Withdrawn"
    if r.startswith("deferred") or r.startswith("tabled"):
        return "Deferred"
    return "No result recorded" if not r else "Other"
