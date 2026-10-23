"""Regression checks for publication errors; run after the JSON builders."""

import csv
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "PWHL/scripts"))
from pwhl_stats import build_leaders, build_team_players, deduplicate_season_stats, unique_shots


def stat(code, **values):
    return {"season_id": "8", "season_name": "2025-26 Regular Season",
            "stat_type": "regular", "player_id": "115", "team_code": code,
            "games_played": "5", "ice_time": "3000", "goals": "1",
            "assists": "2", "points": "3", "shots": "10", **values}


def shot(event="shot", **values):
    return {"game_id": "1", "period_of_game": "1", "time_of_period": "2:00",
            "player_id": "115", "event": event, "goal": "FALSE",
            "x_coord": "20", "y_coord": "10", **values}


class CountingRules(unittest.TestCase):
    def test_duplicate_alias_does_not_erase_an_identical_second_club(self):
        ott, van = stat("OTT"), stat("VAN")
        rows = deduplicate_season_stats([stat("NA"), ott, van, ott,
                                         stat("OTT", season_name="Total")])
        self.assertEqual([r["team_code"] for r in rows], ["OTT", "VAN"])
        self.assertEqual(build_leaders(rows, {})["8"]["points"][0]["points"], 6)

    def test_faceoff_percentage_uses_attempts_not_average_percentages(self):
        rows = [stat("OTT", faceoff_wins="1", faceoff_attempts="2"),
                stat("VAN", faceoff_wins="9", faceoff_attempts="10")]
        result = build_leaders(rows, {})["8"]["faceoff_pct"][0]
        self.assertAlmostEqual(result["faceoff_pct"], 100 * 10 / 12)
        self.assertEqual(result["gp"], 10)

    def test_goalies_are_split_by_club_and_excluded_from_skater_leaders(self):
        rows = [stat("OTT", shots_against="20", goals_against="1", shutouts="0"),
                stat("VAN", shots_against="30", goals_against="0", shutouts="1")]
        result = build_team_players(rows, {})["8"]
        self.assertEqual(result["skaters"], [])
        self.assertEqual([(r["team_code"], r["sa"], r["so"]) for r in result["goalies"]],
                         [("OTT", 20, 0), ("VAN", 30, 1)])
        self.assertEqual(build_leaders(rows, {}), {})

    def test_goal_pair_is_one_shot_and_goal_only_event_survives(self):
        rows = [shot(goal="TRUE"), shot("goal", goal="TRUE"),
                shot("goal", time_of_period="3:00", goal="TRUE")]
        result = unique_shots(rows)
        self.assertEqual(len(result), 2)
        self.assertEqual(sum(r["goal"] == "TRUE" for r in result), 2)

    def test_saved_and_scoring_shots_at_same_clock_are_not_two_goals(self):
        result = unique_shots([shot(), shot(goal="TRUE"), shot("goal", goal="TRUE")])
        self.assertEqual(len(result), 2)
        self.assertEqual(sum(r["goal"] == "TRUE" for r in result), 1)

    def test_missing_shot_coordinates_can_come_from_matching_goal(self):
        source = shot(goal="TRUE", x_coord="NA", y_coord="NA")
        result = unique_shots([source, shot("goal", goal="TRUE")])
        self.assertEqual((result[0]["x_coord"], result[0]["y_coord"]), ("20", "10"))
        self.assertEqual(source["x_coord"], "NA")


class PublishedRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ROOT / "PWHL/data"

    def read(self, name):
        return json.loads((self.data / "json" / f"pwhl_{name}.json").read_text(encoding="utf-8"))

    def test_cava_club_splits_and_vanisova_franchise_totals(self):
        seasons = self.read("team_players")
        cava = {r["team_code"]: (r["gp"], r["points"])
                for r in seasons["8"]["skaters"] if r["player_id"] == "115"}
        self.assertEqual(cava, {"OTT": (17, 4), "VAN": (13, 5)})
        vanisova = [r for sid in ("1", "5", "8") for r in seasons[sid]["skaters"]
                    if r["player_id"] == "161" and r["team_code"] == "OTT"]
        self.assertEqual((sum(r["gp"] for r in vanisova), sum(r["points"] for r in vanisova)), (36, 24))

    def test_eldridge_is_in_home_points_leaders_once(self):
        rows = self.read("leaders")["8"]["points"]
        eldridge = [r for r in rows if r["player_id"] == "36"]
        self.assertEqual(len(eldridge), 1)
        self.assertEqual((eldridge[0]["points"], eldridge[0]["gp"]), (23, 30))
        self.assertEqual(set(eldridge[0]["team_codes"]), {"SEA", "BOS"})

    def test_leaderboards_have_one_row_per_player(self):
        for season in self.read("leaders").values():
            for rows in season.values():
                ids = [r["player_id"] for r in rows]
                self.assertEqual(len(ids), len(set(ids)))

    def test_shot_totals_reconcile_to_source_goal_records(self):
        path = self.data / "pwhl_pbp.csv"
        if not path.exists():
            self.skipTest("Optional play-by-play cache unavailable")
        with path.open(encoding="utf-8-sig", newline="") as stream:
            raw_goals = sum(r["event"] == "goal" for r in csv.DictReader(stream))
        events = self.read("events")
        self.assertEqual(sum(events["goals_by_period"].values()), raw_goals)
        self.assertEqual(events["event_counts"]["goal"], raw_goals)
        self.assertEqual(sum(events["shots_by_period"].values()),
                         events["event_counts"]["shot"] + raw_goals)
        self.assertLessEqual(sum(c["goals"] for c in self.read("shot_map")["cells"]), raw_goals)

    def test_scorer_count_excludes_players_with_zero_points(self):
        montreal = next(r for r in self.read("team_awards")["by_season"]["8"] if r["code"] == "MTL")
        self.assertEqual(montreal["scorers"], 21)

    def test_current_roster_has_catalog_season_name(self):
        roster = self.read("rosters")
        with (self.data / "pwhl_seasons.csv").open(encoding="utf-8-sig", newline="") as stream:
            catalog = {r["season_id"]: r["season_name"] for r in csv.DictReader(stream)}
        self.assertEqual(roster["season"], catalog[roster["season_id"]])


if __name__ == "__main__":
    unittest.main()
