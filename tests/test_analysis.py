import copy
import unittest
from fixtures import configuration, items, match_and_timeline, record
from counter_note.extract import extract_match, first_level, level_interval, item_build
from counter_note.catalog import core_item_ids
from counter_note.statistics import aggregate_pair, fisher_greater, fdr_adjust


class ExtractionTests(unittest.TestCase):
    def test_direction_levels_solo_and_five_core(self):
        match, timeline, champs = match_and_timeline()
        rows = extract_match(match, timeline, champs, items(), configuration())
        self.assertEqual(len(rows), 2)
        own, enemy = rows
        self.assertEqual((own["own"], own["enemy"], own["lane"]), ("Ashe", "Tristana", "bottom"))
        self.assertEqual([own["levels"][x]["outcome"] for x in ("2", "3", "6")], [-1, -1, 1])
        self.assertEqual((own["solo"], enemy["soloAgainst"]), (1, 1))
        self.assertEqual(own["builds"]["start"], ["1055", "2003"])
        self.assertEqual(own["builds"]["5"], ["3031", "3085", "3094", "3036", "3072"])
        self.assertNotIn("puuid", str(rows))

    def test_assists_wrong_enemy_duplicate_and_strict_fifteen_minutes(self):
        match, timeline, champs = match_and_timeline()
        events = timeline["info"]["frames"][0]["events"]
        events.append(copy.deepcopy(events[-1]))
        for killer, victim, assists, timestamp in [(1, 6, [2], 650000), (1, 7, [], 660000), (1, 6, [], 900000), (6, 1, [], 899999)]:
            events.append({"type": "CHAMPION_KILL", "killerId": killer, "victimId": victim, "assistingParticipantIds": assists, "timestamp": timestamp})
        own = extract_match(match, timeline, champs, items(), configuration())[0]
        self.assertEqual((own["solo"], own["soloAgainst"]), (1, 1))

    def test_ambiguous_frames_not_reported_as_tie(self):
        self.assertEqual(first_level((60000, 120000, "frame"), (60000, 120000, "frame")), (None, "ambiguous"))
        self.assertEqual(first_level((60000, 120000, "frame"), (120000, 180000, "frame")), (1, "frame"))
        self.assertEqual(first_level((80000, 80000, "event"), (80000, 80000, "event")), (0, "event"))
        self.assertEqual(first_level(None, (60000, 60000, "event")), (None, "missing"))
        self.assertEqual(first_level((60000, 120000, "frame"), (120000, 120000, "event")), (None, "ambiguous"))

    def test_level_up_ignores_skill_points_and_invalid_participants(self):
        events = [{"type": "SKILL_LEVEL_UP", "participantId": 1, "timestamp": 60000, "skillSlot": 4}, {"type": "LEVEL_UP", "participantId": 0, "level": 6, "timestamp": 1}]
        self.assertIsNone(level_interval(1, 6, events, []))

    def test_undo_and_boots_are_not_core(self):
        data = items()
        events = [{"type": "ITEM_PURCHASED", "participantId": 1, "itemId": i, "timestamp": t} for i, t in [(1055, 1000), (2003, 2000), (3031, 100000), (3006, 200000), (3085, 300000)]]
        events += [{"type": "ITEM_UNDO", "participantId": 1, "beforeId": 3031, "afterId": 0, "timestamp": 110000}, {"type": "ITEM_PURCHASED", "participantId": 1, "itemId": 3031, "timestamp": 400000}]
        result = item_build(1, sorted(events, key=lambda e: e["timestamp"]), data, core_item_ids(data, configuration()), 90000)
        self.assertEqual(result["2"], ["3085", "3031"])
        self.assertEqual(result["start"], ["1055", "2003"])

    def test_wrong_queue_remake_and_incomplete_timeline(self):
        match, timeline, champs = match_and_timeline()
        match["info"]["queueId"] = 450
        self.assertEqual(extract_match(match, timeline, champs, items(), configuration()), [])
        match["info"]["queueId"] = 420
        match["info"]["gameDuration"] = 300
        self.assertEqual(extract_match(match, timeline, champs, items(), configuration()), [])
        match["info"]["gameDuration"] = 1800
        timeline["info"]["frames"] = timeline["info"]["frames"][:1]
        with self.assertRaises(ValueError):
            extract_match(match, timeline, champs, items(), configuration())


class StatisticsTests(unittest.TestCase):
    def test_known_fisher_value(self):
        self.assertAlmostEqual(fisher_greater(8, 2, 1, 5), 0.024475524475524483, places=12)
        self.assertEqual(fisher_greater(0, 0, 0, 0), 1)

    def test_fdr_reference_values(self):
        expected = [0.6, 0.6, 0.2, 0.004]
        for actual, target in zip(fdr_adjust([0.5, 0.6, 0.1, 0.001], "bh"), expected):
            self.assertAlmostEqual(actual, target)
        self.assertAlmostEqual(fdr_adjust([0.001, 0.04], "by")[0], 0.003)
        self.assertTrue(all(a >= b for a, b in zip(fdr_adjust([.01, .03], "by"), fdr_adjust([.01, .03], "bh"))))

    def test_both_early_and_minimum_sample(self):
        rows = [record() for _ in range(30)]
        result = aggregate_pair(rows, configuration())
        self.assertEqual(result["category"], "both")
        self.assertTrue(result["early"])
        self.assertIsNone(aggregate_pair(rows[:29], configuration())["category"])

    def test_unknowns_and_ties_use_explicit_denominators(self):
        rows = [record() for _ in range(30)]
        for row in rows[:10]:
            row["levels"]["6"] = {"outcome": None, "source": "ambiguous"}
        rows[10]["levels"]["6"] = {"outcome": 0, "source": "event"}
        result = aggregate_pair(rows, configuration())
        self.assertEqual(result["levels"]["6"]["observed"], 20)
        self.assertEqual(result["levels"]["6"]["rate"], 19 / 20)
        self.assertEqual(result["category"], "solo")

    def test_significant_build_and_stage_eligible_comparison(self):
        rows = [record(i < 45, "3031") for i in range(50)] + [record(i < 10, "3085") for i in range(50)]
        rows += [dict(record(False), builds={}) for _ in range(200)]
        result = aggregate_pair(rows, configuration())
        self.assertEqual(result["builds"]["1"]["eligibleGames"], 100)
        best = result["builds"]["1"]["rows"][0]
        self.assertTrue(best["significant"])
        self.assertEqual(best["otherGames"], 50)
        self.assertLess(best["q"], 0.05)

    def test_fdr_tests_all_candidates_before_top_ten(self):
        rows = [record(i < 5, str(4000 + j)) for j in range(12) for i in range(10)]
        result = aggregate_pair(rows, configuration())
        self.assertEqual(result["fdr"]["tests"], 12)
        self.assertEqual(len(result["builds"]["1"]["rows"]), 10)


if __name__ == "__main__":
    unittest.main()
