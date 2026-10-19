import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from linkerforge.structure.score import load_ca_pdb, score_fusion


class StructureScoreTests(unittest.TestCase):
    def test_first_model_pdb_ca_mapping(self):
        pdb = (
                "MODEL        1\n"
                "ATOM      1  CA  GLY A   1       1.000   2.000   3.000  1.00 90.00           C\n"
                "ENDMDL\n"
                "MODEL        2\n"
                "ATOM      2  CA  GLY A   1       9.000   9.000   9.000  1.00 90.00           C\n"
                "ENDMDL\n")
        with patch.object(Path, "open", return_value=StringIO(pdb)):
            self.assertEqual(load_ca_pdb("small.pdb", "A"), {1: (1.0, 2.0, 3.0)})

    def test_simple_contiguous_fusion(self):
        coords = {i: (3.8 * i, 0.0, 0.0) for i in range(1, 9)}
        report = score_fusion(coords, (1, 3), (4, 5), (6, 8),
                              [coords[i] for i in range(1, 4)],
                              [coords[i] for i in range(6, 9)])
        self.assertEqual(report["ca_gaps_above_4_5_angstrom"], 0)
        self.assertEqual(report["severe_nonlocal_ca_overlaps_below_2_angstrom"], 0)
        self.assertAlmostEqual(report["domain_a_internal_distance_rmsd_angstrom"], 0.0)

    def test_missing_linker_atom_is_error(self):
        coords = {i: (3.8 * i, 0.0, 0.0) for i in range(1, 9) if i != 4}
        with self.assertRaisesRegex(ValueError, "linker missing"):
            score_fusion(coords, (1, 3), (4, 5), (6, 8))

    def test_bad_spans_rejected(self):
        coords = {i: (3.8 * i, 0.0, 0.0) for i in range(1, 9)}
        with self.assertRaisesRegex(ValueError, "contiguous"):
            score_fusion(coords, (1, 3), (5, 5), (6, 8))


if __name__ == "__main__":
    unittest.main()
