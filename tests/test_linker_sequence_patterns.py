import unittest

from scripts.discover_linker_sequence_patterns import bh_qvalues, motifs


class PatternTests(unittest.TestCase):
    def test_motifs_are_distinct_within_sequence(self):
        self.assertEqual(motifs("AAAA", [3]), {"AAA"})

    def test_motif_widths(self):
        self.assertEqual(motifs("AGST", [3, 4]), {"AGS", "GST", "AGST"})

    def test_bh_correction(self):
        q = bh_qvalues([("a", 0.01), ("b", 0.04), ("c", 0.9)])
        self.assertAlmostEqual(q["a"], 0.03)
        self.assertAlmostEqual(q["b"], 0.06)
        self.assertAlmostEqual(q["c"], 0.9)


if __name__ == "__main__":
    unittest.main()
