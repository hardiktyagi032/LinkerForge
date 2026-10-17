import unittest

from src.linkerforge.detector.regions import intervals


class RegionTests(unittest.TestCase):
    def test_one_based_inclusive_and_composition(self):
        regions = intervals("AGGSST", [0.1, 0.91, 0.95, 0.92, 0.1, 0.1], 0.9)
        self.assertEqual([(r["start"], r["end"], r["sequence"]) for r in regions], [(2, 4, "GGS")])
        self.assertEqual(regions[0]["composition_counts"], {"G": 2, "S": 1})

    def test_no_call_does_not_invent_span(self):
        self.assertEqual(intervals("AAAA", [0.1] * 4, 0.9), [])

    def test_ties_are_not_split(self):
        self.assertEqual(len(intervals("AAAA", [0.9] * 4, 0.9)), 1)

    def test_invalid_scores_rejected(self):
        with self.assertRaises(ValueError):
            intervals("AA", [float("nan"), 0.1], 0.9)


if __name__ == "__main__":
    unittest.main()
