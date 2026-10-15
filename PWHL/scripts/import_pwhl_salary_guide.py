"""Extract player salary rows and team assignments from the PWHLPA guide.

Requires pypdf for the one-time PDF import. The generated CSV is the compact,
reviewable input used by the team-awards builder; the source PDF is retained.
"""

import csv
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "PWHL" / "data"
PDF = DATA / "69efbccd65fdec269086fc2c_PlayerSalaries_2025-2026.pdf"
OUT = DATA / "pwhl_salaries_2025_26.csv"
SEASON_ID = "8"


def norm(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", value.lower())


def main():
    with (DATA / "pwhl_teams.csv").open(newline="", encoding="utf-8-sig") as f:
        season_teams = [r for r in csv.DictReader(f) if r["season_id"] == SEASON_ID]
    teams = {norm(r["team_city"]): r["team_code"] for r in season_teams}

    salary_lines = []
    for page in PdfReader(PDF).pages:
        lines = [line.strip() for line in (page.extract_text() or "").splitlines() if line.strip()]
        for i, line in enumerate(lines):
            if re.fullmatch(r"[\d,]+\.\d{2}", line) and i >= 3:
                first, last, city = lines[i - 3:i]
                code = teams.get(norm(city))
                if not code:
                    raise ValueError(f"Unknown team in salary PDF: {city}")
                salary_lines.append({
                    "season_id": SEASON_ID,
                    "player_name": f"{first} {last}",
                    "team_code": code,
                    "salary": f"{float(line.replace(',', '')):.2f}",
                })

    if not salary_lines:
        raise ValueError("No salary rows found in PDF")
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["season_id", "player_name", "team_code", "salary"])
        writer.writeheader()
        writer.writerows(salary_lines)
    print(f"Wrote {len(salary_lines)} player salary rows to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
