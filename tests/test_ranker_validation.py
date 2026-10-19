import unittest

from linkerforge.validation.ranking import evaluate_queries


class RankingValidationTests(unittest.TestCase):
    def test_tie_does_not_give_favorable_rank(self):
        result = evaluate_queries([
            {"query_id": "q", "candidate_id": "natural", "score": 0.5, "observed": True, "split_group_id": "g"},
            {"query_id": "q", "candidate_id": "control", "score": 0.5, "observed": False, "split_group_id": "g"},
        ])
        self.assertEqual(result["per_query"][0]["rank"], 1.5)
        self.assertEqual(result["top1"], 0.0)

    def test_reject_missing_positive(self):
        with self.assertRaises(ValueError):
            evaluate_queries([
                {"query_id": "q", "candidate_id": "a", "score": 0.5, "observed": False, "split_group_id": "g"},
                {"query_id": "q", "candidate_id": "b", "score": 0.4, "observed": False, "split_group_id": "g"},
            ])
