"""Offline regression checks for report transformations and missing periods."""
import csv
import json
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "data"


class ReportChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads((ROOT / "derived/stops_report/report.json").read_text(encoding="utf-8"))

    def test_police_rollups_do_not_lose_outcomes_or_hours(self):
        police = self.report["police"]
        expected = Counter({(y, o): n for y, o, n in police["annual"]})
        for name, year_i, outcome_i, n_i in [("monthly", 0, 2, 3), ("weekdays", 0, 2, 3),
                                            ("hourly", 0, 2, 3), ("areas", 0, 2, 3), ("drivers", 0, 4, 5)]:
            actual = Counter()
            for row in police[name]:
                actual[(row[year_i], row[outcome_i])] += row[n_i]
            self.assertEqual(expected, actual, name)
        self.assertEqual({"Charged", "Warning (T-Stop)", "Final", "Data Quality"}, {o for y, o in expected})
        self.assertEqual(set(map(str, range(24))) | {"Unknown"}, {r[1] for r in police["hourly"]})
        # OPS hour is HH00; verify a non-midnight hour, not merely the grand total.
        with (ROOT / "police/traffic_stops_by_time.csv").open(encoding="utf-8") as stream:
            raw = list(csv.DictReader(stream))
        self.assertEqual(sum(int(r["n"]) for r in raw if r["hour"] == "1400"),
                         sum(r[3] for r in police["hourly"] if r[1] == "14"))

    def test_months_are_valid_and_unique(self):
        rows = self.report["police"]["monthly"]
        self.assertTrue(all(1 <= r[1] <= 12 for r in rows))
        self.assertEqual(len(rows), len({tuple(r[:3]) for r in rows}))

    def test_collision_gap_and_record_reconciliation(self):
        rows = self.report["collisions"]
        self.assertNotIn(2023, {r["year"] for r in rows})
        for r in rows:
            self.assertEqual(r["total"], sum(r["severity"].values()))
        for year in {r["year"] for r in rows}:
            with (ROOT / f"city/collisions/{year}.csv").open(encoding="utf-8") as stream:
                raw_count = sum(1 for _ in csv.DictReader(stream))
            self.assertEqual(raw_count, sum(r["total"] for r in rows if r["year"] == year))
            locations = json.loads((ROOT / f"derived/stops_report/collisions-{year}.json").read_text(encoding="utf-8"))
            self.assertLessEqual(sum(r[4] for r in locations), raw_count)

    def test_camera_keys_and_missing_periods(self):
        for key in ["speed", "redlight"]:
            camera = self.report[key]
            self.assertEqual(len(camera["months"]), len({tuple(r[:3]) for r in camera["months"]}))
            self.assertTrue(all(0 <= r[2] < len(camera["sites"]) and r[3] >= 0 for r in camera["months"]))
        # Keep the original report's two reference totals reproducible.
        self.assertEqual(43416, sum(r[3] for r in self.report["speed"]["months"] if r[:2] == [2024, 3]))
        self.assertEqual(6507, sum(r[3] for r in self.report["redlight"]["months"] if r[:2] == [2023, 7]))
        self.assertFalse(any(r[0] > 2025 for r in self.report["speed"]["months"]))

    def test_monitoring_keeps_stages_and_undated_baselines(self):
        rows = self.report["monitoring"]
        self.assertEqual({"ASE Active", "ASE Removed", "Pre ASE Installation"}, {r["stage"] for r in rows})
        self.assertTrue(any(not r["month"] and r["source_date"] == "N/A" for r in rows))
        self.assertTrue(any(r["stage"] == "ASE Removed" and r["month"].startswith("2026") for r in rows if r["month"]))


if __name__ == "__main__":
    unittest.main()
