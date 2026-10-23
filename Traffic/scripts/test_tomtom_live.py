"""Offline checks for poll_tomtom_live.py: parsing, merge and the once-a-day gate."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import poll_tomtom_live as tt  # noqa: E402


def payload(*records):
    return {"region": {"id": "CAN_ottawa_new"}, "data": list(records)}


def rec(update_ms=1792760400000, live=32):
    return {"updateTime": update_ms, "trafficIndexLive": live, "trafficIndexHistoric": 21, "relTravelTimeLive": 108,
            "relTravelTimeHistoric": 100, "jamsCount": 13, "jamsLength": 9, "jamsDelay": 36.6,
            "date": "2026-10-23", "hour": 9}


class ParseChecks(unittest.TestCase):
    def test_local_time_comes_from_update_time(self):
        r = tt.parse(payload(rec()), "2026-10-23T14:00:00Z")[0]
        self.assertEqual(("2026-10-23T13:00:00Z", "2026-10-23", 9), (r["update_utc"], r["local_date"], r["local_hour"]))
        self.assertEqual((32, 21, 13, 9, 36.6), (r["congestion_pct"], r["congestion_usual_pct"], r["jams_count"],
                                                 r["jams_length_km"], r["jams_delay_min"]))

    def test_wrong_city_or_shape_is_rejected(self):
        with self.assertRaises(ValueError):
            tt.parse({"region": {"id": "CAN_toronto"}, "data": [rec()]}, "x")
        with self.assertRaises(ValueError):
            tt.parse(payload(), "x")
        bad = rec(); del bad["jamsCount"]
        with self.assertRaises(ValueError):
            tt.parse(payload(bad), "x")

    def test_merge_overwrites_same_hour(self):
        old = {r["update_utc"]: r for r in tt.parse(payload(rec(live=30)), "a")}
        merged, new = tt.merge(old, tt.parse(payload(rec(live=32), rec(update_ms=1792764000000)), "b"))
        self.assertEqual(1, new)
        self.assertEqual(2, len(merged))
        self.assertEqual(32, merged["2026-10-23T13:00:00Z"]["congestion_pct"])


class GateChecks(unittest.TestCase):
    def utc(self, h, d=23):
        return datetime(2026, 10, d, h, 0, tzinfo=timezone.utc)   # EDT: local = UTC-4

    def test_waits_until_5am_local_then_runs_once(self):
        self.assertFalse(tt.due({}, self.utc(8)))                  # 04:00 local
        self.assertTrue(tt.due({}, self.utc(9)))                   # 05:00 local
        self.assertFalse(tt.due({"last_success_local_date": "2026-10-23"}, self.utc(15)))
        self.assertTrue(tt.due({"last_success_local_date": "2026-10-22"}, self.utc(15)))

    def test_failure_waits_an_hour(self):
        failed = {"last_attempt_utc": "2026-10-23T14:00:00Z", "last_attempt_failed": True}
        self.assertFalse(tt.due(failed, datetime(2026, 10, 23, 14, 30, tzinfo=timezone.utc)))
        self.assertTrue(tt.due(failed, datetime(2026, 10, 23, 15, 5, tzinfo=timezone.utc)))


if __name__ == "__main__":
    unittest.main()
