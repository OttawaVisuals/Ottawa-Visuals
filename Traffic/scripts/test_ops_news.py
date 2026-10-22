"""Offline checks for poll_ops_news.py extraction, on saved OPS release text."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import poll_ops_news as ops  # noqa: E402

FIXTURES = HERE / "fixtures" / "ops_news"


def row(slug, title, release_utc):
    text = (FIXTURES / f"{slug}.txt").read_text(encoding="utf-8")
    return ops.extract({"title": title, "release_utc": release_utc,
                        "url": f"https://www.ottawapolice.ca/en/news/posts/{slug}/"}, text)


class ExtractChecks(unittest.TestCase):
    def test_life_threatening_is_not_fatal(self):
        # The footer names the "Fatal Collision Investigation Unit"; that must
        # not turn a critical injury into a death.
        r = row("serious-collision-on-burton-road-man-in-life-threatening-condition",
                "Serious collision on Burton Road; man in life-threatening condition",
                "2026-10-16T15:10:00Z")
        self.assertEqual("collision", r["kind"])
        self.assertEqual("critical", r["severity"])
        self.assertEqual("", r["people_killed"])
        self.assertEqual(("2026-10-15", "19:46"), (r["incident_date"], r["incident_time"]))
        self.assertEqual("700 block of Burton Road", r["location"])
        self.assertEqual("East", r["district"])
        self.assertEqual((0, 1), (r["pedestrian"], r["truck"]))

    def test_fatal_pedestrian(self):
        r = row("fatal-collision-on-strandherd-drive-seeking-witnesses",
                "Fatal collision on Strandherd Drive; seeking witnesses", "2026-10-14T17:55:00Z")
        self.assertEqual(("fatal", "1", 1), (r["severity"], r["people_killed"], r["pedestrian"]))
        self.assertEqual(("2026-10-14", "06:19"), (r["incident_date"], r["incident_time"]))
        self.assertEqual("Strandherd Drive", r["location"])

    def test_cyclist_struck_is_not_a_pedestrian(self):
        r = row("seeking-witnesses-to-a-serious-collision-involving-a-cyclist-on-haig-dr",
                "Seeking witnesses to a serious collision involving a cyclist on Haig Dr",
                "2026-03-26T14:00:00Z")
        self.assertEqual((1, 0, 0), (r["cyclist"], r["pedestrian"], r["motorcycle"]))
        self.assertEqual("critical", r["severity"])
        self.assertEqual("2000 block of Haig Drive", r["location"])

    def test_enforcement_charges(self):
        r = row("south-district-traffic-initiative-results-in-41-provincial-offence-notices",
                "South District traffic initiative results in 41 provincial offence notices",
                "2026-10-19T15:50:00Z")
        self.assertEqual(("enforcement", "41", "South"), (r["kind"], r["charges"], r["district"]))

    def test_feature_story_is_skipped(self):
        self.assertIsNone(row(
            "running-towards-danger-cst-hanniman-and-det-nissan-s-heroic-actions-during-lisbon-funicular-crash",
            "Running towards danger: Cst Hanniman and Det Nissan’s heroic actions during Lisbon funicular crash",
            "2026-05-11T14:00:00Z"))

    def test_classify_titles(self):
        self.assertIsNone(ops.classify("Two men charged following drug trafficking investigation", ""))
        self.assertIsNone(ops.classify("29 lives lost on Ottawa roads this year: Police urge action", ""))
        self.assertEqual("enforcement", ops.classify("117 km/h in a School Zone: Street Racing Driver Charged", ""))
        self.assertEqual("collision", ops.classify("Fatal Collision – Hwy 174 E/B at Blair Rd", ""))

    def test_follow_up_and_dates(self):
        self.assertEqual("2025-12-30", ops.incident_date("occurred on December 30.", "2026-01-02T15:00:00Z"))
        self.assertEqual("21:50", ops.incident_time("At approximately 9:50 pm, officers"))
        r = ops.extract({"title": "Man arrested in fatal hit-and-run", "release_utc": "2026-03-23T15:00:00Z",
                         "url": "x"}, "FOR IMMEDIATE RELEASE\nA crossing guard lost his life.\n— 30 —")
        self.assertEqual((1, "fatal", 1, 1), (r["follow_up"], r["severity"], r["pedestrian"], r["hit_and_run"]))

    def test_collision_types(self):
        def kind_of(text):
            r = ops.extract({"title": "Seeking witnesses to a collision", "release_utc": "2026-09-23T12:30:00Z",
                             "url": "x"}, f"FOR IMMEDIATE RELEASE\n{text}\n— 30 —")
            return r["collision_type"]
        self.assertEqual("building", kind_of(
            "officers responded to a motor vehicle collision in the 100 block of McArthur Avenue, "
            "where a vehicle struck the front of a commercial business, injuring two men inside."))
        self.assertEqual("single_vehicle", kind_of("a serious single motor vehicle collision on Fallowfield Road."))
        self.assertEqual("multi_vehicle", kind_of("a collision involving a vehicle and a transport truck."))
        self.assertEqual("motorcycle", kind_of("a collision involving a motorcycle and an SUV on Trim Road."))
        self.assertEqual("pedestrian", kind_of("a collision involving a vehicle and a pedestrian near Cresthaven."))
        self.assertEqual("train", kind_of("a collision involving a vehicle and a VIA Rail train."))
        self.assertEqual("off_road", kind_of("an ATV collision in the 1700 block of Dunrobin Road."))
        self.assertEqual("unknown", kind_of("a fatal hit-and-run collision in the area of Merivale Road."))

    def test_parse_rss(self):
        raw = b"""<?xml version="1.0" encoding="UTF-8" ?><rss version="2.0"><channel>
            <item><title>A</title><link>https://x/a/</link><pubDate>Fri, 16 October 2026 15:10:00</pubDate></item>
            <item><title>B</title><link>https://x/b/</link><pubDate>bad</pubDate></item>
            </channel></rss>"""
        items = ops.parse_rss(raw)
        self.assertEqual(["2026-10-16T15:10:00Z", ""], [i["release_utc"] for i in items])


if __name__ == "__main__":
    unittest.main()
