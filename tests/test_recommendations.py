import copy
import math
import unittest
from fixtures import configuration, items, match_and_timeline, record
from counter_note.choices import FEATURES, extract_choices, rune_choice, skill_choices
from counter_note.extract import extract_match
from counter_note.recommendations import count_choices, interaction_test, recommendation_pair
from counter_note.statistics import aggregate, fdr_adjust


def participant():
    return {"participantId": 1, "champLevel": 9, "summoner1Id": 4, "summoner2Id": 7, "perks": {"styles": [{"description": "primaryStyle", "style": 8000, "selections": [{"perk": i} for i in (8005, 9111, 9104, 8014)]}, {"description": "subStyle", "style": 8200, "selections": [{"perk": i} for i in (8236, 8234)]}], "statPerks": {"offense": 5005, "flex": 5008, "defense": 5011}}}


def skill_events():
    return [{"type": "SKILL_LEVEL_UP", "participantId": 1, "levelUpType": "NORMAL", "skillSlot": slot, "timestamp": 10000 + i * 90000} for i, slot in enumerate((1, 2, 3, 1, 1, 4, 1, 2, 1))]


def group(n, wins, choice, enemy="Tristana"):
    return [dict(record(i < wins, choice), enemy=enemy, choices={"spells": [choice, "4"]}) for i in range(n)]


class ChoiceExtractionTests(unittest.TestCase):
    def test_match_fields_and_exact_skill_duplicates(self):
        match, timeline, champions = match_and_timeline()
        match["info"]["participants"][0].update(participant())
        events = skill_events()
        timeline["info"]["frames"][0]["events"] += events + [copy.deepcopy(events[0])]
        rows = extract_match(match, timeline, champions, items(), configuration())
        own, enemy = rows
        self.assertEqual(own["choices"]["runes"], ["8000", "8005", "9111", "9104", "8014", "8200", "8234", "8236"])
        self.assertEqual(own["choices"]["spells"], ["4", "7"])
        self.assertEqual(own["choices"]["skills6"], list("QWEQQR"))
        self.assertEqual(len(own["choices"]["skills9"]), 9)
        self.assertEqual(enemy["choices"], {})
        self.assertEqual(own["levels"]["6"]["outcome"], 1)
        self.assertNotIn("statPerks", str(rows))

    def test_missing_and_malformed_optional_fields_do_not_reject_matches(self):
        for perks in (None, [], {}, {"styles": [None, {}]}):
            match, timeline, champions = match_and_timeline()
            match["info"]["participants"][0]["perks"] = perks
            rows = extract_match(match, timeline, champions, items(), configuration())
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["choices"], {})
            self.assertIn("1", rows[0]["builds"])

    def test_spell_order_and_secondary_rune_order_are_normalized(self):
        first = participant()
        second = copy.deepcopy(first)
        second["summoner1Id"], second["summoner2Id"] = 7, 4
        second["perks"]["styles"][1]["selections"].reverse()
        self.assertEqual(extract_choices(first, "Ashe", skill_events()), extract_choices(second, "Ashe", skill_events()))

    def test_invalid_runes_and_spellbook_spells_are_excluded(self):
        invalid = participant()
        invalid["perks"]["styles"][1]["style"] = 8000
        self.assertIsNone(rune_choice(invalid))
        invalid = participant()
        invalid["perks"]["styles"][1]["selections"][0]["perk"] = []
        self.assertIsNone(rune_choice(invalid))
        special = participant()
        special["perks"]["styles"][0]["selections"][0]["perk"] = 8360
        choices, status = extract_choices(special, "Ashe", skill_events())
        self.assertIn("runes", choices)
        self.assertNotIn("spells", choices)
        self.assertEqual(status["spells"], "spellbook")

    def test_uncertain_skill_events_are_excluded_without_losing_spells(self):
        cases = []
        events = skill_events()
        events.append(dict(events[-1], timestamp=events[-1]["timestamp"] + 500))
        cases.append(events)
        events = skill_events()
        events[0]["levelUpType"] = "EVOLVE"
        cases.append(events)
        events = skill_events()
        events[1]["timestamp"] = events[0]["timestamp"]
        cases.append(events)
        events = skill_events()
        events[0]["skillSlot"] = 5
        cases.append(events)
        cases.append(skill_events()[:-1])
        for events in cases:
            choices, status = extract_choices(participant(), "Ashe", events)
            self.assertFalse(any(k.startswith("skills") for k in choices))
            self.assertIn("spells", choices)
            self.assertNotEqual(status["skills"], "observed")

    def test_special_champion_and_unreached_stage(self):
        self.assertEqual(skill_choices(participant(), "Aphelios", skill_events())[1], "unsupported_champion")
        own = dict(participant(), champLevel=6)
        choices, status = skill_choices(own, "Ashe", skill_events()[:6])
        self.assertEqual(status, "observed")
        self.assertEqual(set(choices), {"skills3", "skills6"})


class RecommendationTests(unittest.TestCase):
    def result(self, local, baseline):
        return recommendation_pair(local, count_choices(local + baseline), configuration())

    def test_known_odds_ratio_interaction_and_joint_p(self):
        value = interaction_test((100, 80), (100, 20), (100, 50), (100, 50))
        self.assertAlmostEqual(value["ratio"], 16)
        self.assertAlmostEqual(value["interactionP"], .5 * math.erfc(math.log(16) / math.sqrt(.205) / math.sqrt(2)))
        self.assertEqual(value["p"], max(value["interactionP"], value["withinP"]))
        self.assertGreater(value["ratioCi"][0], 1)
        self.assertLess(value["ratioCi"][0], value["ratio"])
        self.assertGreater(value["ratioCi"][1], value["ratio"])

    def test_global_strength_alone_is_not_matchup_specific(self):
        local = group(100, 80, "3031") + group(100, 20, "3001")
        baseline = [dict(r, enemy="Caitlyn") for r in local]
        result = self.result(local, baseline)
        row = result["features"]["1"]["rows"][0]
        self.assertAlmostEqual(row["ratio"], 1)
        self.assertAlmostEqual(row["interactionP"], .5)
        self.assertFalse(row["significant"])

    def test_matchup_advantage_highlight_and_disjoint_baseline(self):
        local = group(100, 80, "3031") + group(100, 20, "3001")
        baseline = group(100, 50, "3031", "Caitlyn") + group(100, 50, "3001", "Caitlyn")
        row = self.result(local, baseline)["features"]["1"]["rows"][0]
        self.assertTrue(row["significant"])
        self.assertEqual(row["baselineGames"], 100)
        self.assertEqual(row["overallGames"], 200)
        self.assertEqual(row["overallWinRate"], .65)
        self.assertEqual(row["baselineWinRate"], .5)
        self.assertEqual(row["alternativeWinRate"], .2)
        self.assertLess(row["ci"][1], 1)
        self.assertGreater(row["ratioCi"][0], 1)

    def test_relative_improvement_without_local_advantage_not_highlighted(self):
        local = group(100, 40, "3031") + group(100, 60, "3001")
        baseline = group(100, 10, "3031", "Caitlyn") + group(100, 90, "3001", "Caitlyn")
        rows = self.result(local, baseline)["features"]["1"]["rows"]
        row = next(r for r in rows if r["values"] == ["3031"])
        self.assertGreater(row["ratio"], 1)
        self.assertLess(row["interactionP"], .05)
        self.assertGreater(row["p"], .9)
        self.assertFalse(row["significant"])

    def test_insufficient_sparse_and_missing_data_have_no_p_or_highlight(self):
        local = group(100, 99, "3031") + group(100, 1, "3001")
        baseline = group(100, 50, "3031", "Caitlyn") + group(100, 50, "3001", "Caitlyn")
        for other, status in (([], "insufficient_sample"), (baseline, "sparse_outcomes")):
            result = self.result(local, other)
            self.assertEqual(result["fdr"]["tests"], 0)
            for row in result["features"]["1"]["rows"]:
                self.assertIsNone(row["p"])
                self.assertIsNone(row["q"])
                self.assertFalse(row["significant"])
                self.assertEqual(row["status"], status)
        result = self.result([record()] * 30, [])
        self.assertEqual(result["features"]["runes"]["excludedGames"], 30)
        self.assertEqual(result["features"]["runes"]["rows"], [])
        self.assertEqual(result["features"]["runes"]["observedGames"], 0)

    def test_all_features_fdr_before_top_ten_and_shared_family(self):
        local = []
        for j in range(12):
            for i in range(40):
                row = record(i < 20)
                row["builds"] = {k: [str(4000 + j)] for k in FEATURES[:6]}
                row["choices"] = {k: [str(4000 + j)] for k in FEATURES[6:]}
                local.append(row)
        baseline = [dict(r, enemy="Caitlyn") for r in local]
        result = self.result(local, baseline)
        self.assertEqual(result["fdr"]["tests"], 12 * len(FEATURES))
        for feature in result["features"].values():
            self.assertEqual(feature["candidateCount"], 12)
            self.assertEqual(len(feature["rows"]), 10)
            self.assertTrue(all(r["q"] == 1 for r in feature["rows"]))

    def test_fdr_matches_reference_across_item_and_spell_features(self):
        local = group(100, 80, "3031") + group(100, 20, "3001")
        baseline = group(100, 50, "3031", "Caitlyn") + group(100, 50, "3001", "Caitlyn")
        result = self.result(local, baseline)
        rows = [r for f in result["features"].values() for r in f["rows"] if r["p"] is not None]
        self.assertEqual(len(rows), 4)
        self.assertEqual([r["q"] for r in rows], fdr_adjust([r["p"] for r in rows], "by"))

    def test_aggregation_keeps_own_champion_and_lane_separate(self):
        local = group(40, 30, "3031") + group(40, 10, "3001")
        strangers = [dict(r, lane="top", enemy="Garen") for r in local]
        strangers += [dict(r, own="Jinx", enemy="Caitlyn") for r in local]
        _, _, details = aggregate(local + strangers, configuration())
        result = details["bottom"]["Tristana"]["Ashe"]["recommendations"]
        self.assertEqual(result["features"]["1"]["baselineGames"], 0)
        self.assertEqual(result["fdr"]["tests"], 0)

    def test_invalid_counts_are_rejected(self):
        with self.assertRaises(ValueError):
            interaction_test((20, 21), (20, 10), (20, 10), (20, 10))


if __name__ == "__main__":
    unittest.main()
