"""Offline checks for poll_ctv_crashes.py slug rules and OPS matching."""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import poll_ctv_crashes as ctv  # noqa: E402


def c(slug):
    return ctv.classify(slug)


class SlugChecks(unittest.TestCase):
    def test_jurisdiction(self):
        self.assertEqual("kingston", c("motorcycle-driver-dead-after-crash-west-of-kingston-ont")["out_reason"])
        self.assertEqual("gatineau", c("pedestrian-dead-following-collision-in-gatineau-que")["out_reason"])
        # The 417 is OPP even inside the city; Hwy 174 is a City road (OPS).
        self.assertEqual(0, c("opp-seeking-witnesses-to-collision-on-hwy-417-in-ottawa")["in_ottawa_ops"])
        self.assertEqual(1, c("1-dead-after-crash-involving-pedestrian-on-hwy-174")["in_ottawa_ops"])
        self.assertEqual(1, c("pedestrian-78-struck-by-vehicle-in-sandy-hill")["in_ottawa_ops"])

    def test_severity(self):
        self.assertEqual("fatal", c("man-dies-after-vehicle-crashes-into-home-in-orleans")["severity"])
        self.assertEqual("critical", c("motorcyclist-in-critical-condition-after-hunt-club-rd-collision")["severity"])
        self.assertEqual("injury", c("pedestrian-suffers-non-life-threatening-injuries-in-hwy-417-collision")["severity"])
        self.assertEqual("serious", c("cyclist-seriously-injured-after-being-struck-by-suv-in-carp")["severity"])
        self.assertEqual("unknown", c("vehicle-crashes-into-barrhaven-gas-bar")["severity"])

    def test_collision_types(self):
        self.assertEqual("motorcycle", c("motorcyclist-in-critical-condition-after-hunt-club-rd-collision")["collision_type"])
        self.assertEqual(0, c("motorcyclist-in-critical-condition-after-hunt-club-rd-collision")["cyclist"])
        self.assertEqual("cyclist", c("driver-of-e-bike-in-critical-condition-following-barrhaven-crash")["collision_type"])
        self.assertEqual("off_road", c("petawawa-man-killed-in-dirt-bike-crash")["collision_type"])
        self.assertEqual("building", c("truck-crashes-into-wall-of-business-in-ottawas-east-end")["collision_type"])
        self.assertEqual("building", c("vehicle-crashes-into-orleans-business-2")["collision_type"])
        self.assertEqual("pedestrian", c("driver-charged-after-suv-strikes-pedestrian-crashes-into-building-in-downtown-ottawa")["collision_type"])
        self.assertEqual("multi_vehicle", c("two-seriously-injured-in-head-on-crash-near-findlay-creek")["collision_type"])
        self.assertEqual("single_vehicle", c("two-people-seriously-injured-in-merivale-rd-rollover")["collision_type"])
        self.assertEqual("pedestrian", c("man-in-motorized-wheelchair-struck-by-a-car-in-ottawas-west-end")["collision_type"])

    def test_parse_sitemap(self):
        raw = ("<urlset><url><loc>https://www.ctvnews.ca/ottawa/article/1-dead-1-injured-after-vehicle-"
               "strikes-vanier-barber-shop/</loc><lastmod>2026-09-23T22:47:54.166Z</lastmod>"
               "<changefreq>always</changefreq><priority>0.5</priority>" + "<x/>" * 80 + "</url>"
               "<url><loc>https://www.ctvnews.ca/ottawa/article/a-sunny-tuesday/</loc></url>"
               "<url><loc>https://www.ctvnews.ca/kitchener/article/crash-on-king-st/</loc></url></urlset>")
        rows = ctv.parse_sitemap(raw, "2026-09-23")
        self.assertEqual(["1-dead-1-injured-after-vehicle-strikes-vanier-barber-shop"], [r["slug"] for r in rows])
        self.assertEqual("2026-09-23T22:47:54Z", rows[0]["lastmod_utc"])
        self.assertEqual(("building", "fatal"), (c(rows[0]["slug"])["collision_type"], c(rows[0]["slug"])["severity"]))

    def test_not_crashes(self):
        self.assertIsNone(ctv.CRASH.search("cold-temperatures-in-ottawa-on-new-years-eve-as-the-clock-strikes-midnight"))
        self.assertIsNotNone(ctv.CRASH.search("several-injured-including-child-after-vehicle-strikes-stittsville-bakery"))
        self.assertEqual("context", c("ottawa-police-cracking-down-on-underage-operation-and-misuse-of-e-scooters")["story_kind"])

    def test_struck_means_pedestrian(self):
        self.assertEqual("pedestrian", c("woman-struck-by-vehicle-in-south-keys-parking-lot-dies")["collision_type"])
        self.assertEqual("cyclist", c("cyclist-seriously-injured-after-being-struck-by-suv-in-carp")["collision_type"])
        self.assertEqual("unknown", c("police-look-for-witnesses-to-hit-and-run-crash-on-bank-street")["collision_type"])
        self.assertEqual("train", c("train-strikes-vehicle-near-fallowfield-station-in-ottawas-south-end")["collision_type"])
        self.assertEqual("single_vehicle", c("2-people-make-it-to-shore-after-crashing-car-into-mooneys-bay")["collision_type"])
        self.assertEqual("follow_up", c("ottawa-police-seek-witnesses-to-aug-24-crash-after-victim-dies-of-injuries")["story_kind"])

    def test_story_kind(self):
        self.assertEqual("context", c("6-jump-in-collisions-on-ottawa-roads-so-far-this-year")["story_kind"])
        self.assertEqual("context", c("this-is-why-the-city-installed-an-oversized-pedestrian-crossing-button")["story_kind"])
        self.assertEqual("follow_up", c("video-shows-moments-before-collision-that-killed-ottawa-crossing-guard-accused-testifies")["story_kind"])
        self.assertEqual("follow_up", c("driver-charged-following-fatal-crash-near-fallowfield-station-in-may")["story_kind"])
        self.assertEqual("incident", c("pedestrian-struck-by-a-vehicle-in-barrhaven-2")["story_kind"])


class MatchChecks(unittest.TestCase):
    OPS = [
        {"url": "ops/burton", "collision_type": "multi_vehicle", "severity": "critical",
         "_dates": {date(2026, 10, 15), date(2026, 10, 16)}, "_roads": ctv.road_words("700 block of Burton Road")},
        {"url": "ops/strandherd", "collision_type": "pedestrian", "severity": "fatal",
         "_dates": {date(2026, 10, 14)}, "_roads": ctv.road_words("Strandherd Drive")},
        {"url": "ops/huntclub", "collision_type": "motorcycle", "severity": "critical",
         "_dates": {date(2026, 9, 20), date(2026, 9, 21)}, "_roads": ctv.road_words("Hunt Club Road at Cahill Drive")},
    ]

    def row(self, slug, day):
        return {"slug": slug, "sitemap_date": day, **c(slug)}

    def test_road_words(self):
        self.assertEqual({"hunt-club", "cahill"}, ctv.road_words("Hunt Club Road at Cahill Drive"))
        self.assertEqual({"burton"}, ctv.road_words("700 block of Burton Road"))

    def test_match_by_road(self):
        self.assertEqual(("ops/huntclub", "road"), ctv.match(self.row(
            "motorcyclist-in-critical-condition-after-hunt-club-rd-collision", "2026-09-21"), self.OPS))

    def test_match_by_type_and_date(self):
        # CTV names the neighbourhood (Barrhaven), OPS the street (Strandherd).
        self.assertEqual(("ops/strandherd", "type+date"), ctv.match(self.row(
            "pedestrian-dies-after-being-struck-by-a-vehicle-in-barrhaven", "2026-10-14"), self.OPS))

    def test_fatal_prefers_fatal_release_on_same_road(self):
        ops = self.OPS + [
            {"url": "ops/huntclub-oct1", "collision_type": "motorcycle", "severity": "critical",
             "_dates": {date(2026, 9, 30), date(2026, 10, 1)}, "_roads": ctv.road_words("Hunt Club Road")},
            {"url": "ops/escape", "collision_type": "unknown", "severity": "fatal",
             "_dates": {date(2026, 10, 7)}, "_roads": ctv.road_words("West Hunt Club Road and Merivale Road")},
        ]
        self.assertEqual("ops/escape", ctv.match(self.row(
            "motorcyclist-dies-following-west-hunt-club-road-hit-and-run-crash-police-seeking", "2026-10-04"), ops)[0])

    def test_no_match_out_of_window_or_area(self):
        self.assertEqual(("", ""), ctv.match(self.row(
            "pedestrian-dies-after-being-struck-by-a-vehicle-in-barrhaven", "2026-08-01"), self.OPS))
        # Same type, two days off, no shared road: a different crash (Friel St, Sandy Hill).
        self.assertEqual(("", ""), ctv.match(self.row(
            "pedestrian-dies-after-being-struck-by-a-vehicle-in-sandy-hill-on-thursday", "2026-10-16"), self.OPS))
        # Fatal vs a non-fatal release on the same road, with the fatal one out of window.
        self.assertEqual(("", ""), ctv.match(self.row(
            "motorcyclist-dies-following-hunt-club-rd-crash", "2026-09-22"), self.OPS))
        self.assertEqual(("", ""), ctv.match(self.row(
            "pedestrian-dead-following-collision-in-gatineau-que", "2026-10-14"), self.OPS))


if __name__ == "__main__":
    unittest.main()
