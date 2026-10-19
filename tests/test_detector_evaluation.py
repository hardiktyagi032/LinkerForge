import unittest

from src.linkerforge.detector.evaluation import spans, region_metrics


class EvaluationTests(unittest.TestCase):
    def test_intervals_are_inclusive(self):
        self.assertEqual(spans([False, True, True, False, True]), [(2, 3), (5, 5)])

    def test_region_match_and_boundary_error(self):
        result = region_metrics({"p": [False, True, True, True, False]},
                                {"p": [0.1, 0.1, 0.9, 0.9, 0.1]}, 0.5)
        self.assertEqual(result["matched_regions"], 1)
        self.assertEqual(result["matched_start_mae"], 1)
        self.assertEqual(result["region_recall"], 1)

    def test_no_prediction(self):
        result = region_metrics({"p": [False, True]}, {"p": [0.1, 0.1]}, 0.5)
        self.assertEqual(result["region_recall"], 0)
        self.assertIsNone(result["matched_start_mae"])


if __name__ == "__main__":
    unittest.main()
