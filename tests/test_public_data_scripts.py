"""Offline checks for the public-data pilot parsers."""

import unittest

from scripts.build_rcsb_pilot import read_scheme
from scripts.probe_interpro_domains import candidate_pairs
from scripts.select_cath_pilot import simple_pair


class CathSelectionTests(unittest.TestCase):
    def test_real_format_two_continuous_domains(self):
        line = "2b2xL D02 F00  1  L    1 - L  107 -  1  L  113 - L  215 -"
        pair = simple_pair(line)
        self.assertEqual(pair["pdb_id"], "2B2X")
        self.assertEqual(pair["linker_start_author"], 108)
        self.assertEqual(pair["linker_end_author"], 112)
        self.assertEqual(pair["linker_length_author"], 5)

    def test_rejects_out_of_range_gap(self):
        line = "2b2xL D02 F00  1  L    1 - L  107 -  1  L  139 - L  215 -"
        self.assertIsNone(simple_pair(line))


class SchemeReaderTests(unittest.TestCase):
    def test_maps_unresolved_polymer_residue(self):
        payload = b"""data_demo
loop_
_pdbx_poly_seq_scheme.asym_id
_pdbx_poly_seq_scheme.seq_id
_pdbx_poly_seq_scheme.mon_id
_pdbx_poly_seq_scheme.pdb_seq_num
_pdbx_poly_seq_scheme.pdb_strand_id
_pdbx_poly_seq_scheme.pdb_ins_code
A 1 GLY 108 L .
A 2 SER 109 L .
#
"""
        self.assertEqual(read_scheme(payload, "L"), {108: (1, "G"), 109: (2, "S")})


class InterproProbeTests(unittest.TestCase):
    def test_only_separated_domain_sized_hits_form_candidates(self):
        matches = [("IPR_A", 1, 100), ("IPR_A", 1, 100),
                   ("IPR_B", 111, 180), ("IPR_C", 300, 330)]
        self.assertEqual(candidate_pairs(matches),
                         [("IPR_A", 1, 100, "IPR_B", 111, 180)])


if __name__ == "__main__":
    unittest.main()
