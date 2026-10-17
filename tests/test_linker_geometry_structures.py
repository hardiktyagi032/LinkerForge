"""The geometry checked against real coordinates, not only synthetic ones.

Fixtures and their provenance: ``tests/fixtures/geometry/PROVENANCE.md``. The
protease dimer is RCSB entry 4E43; the kinase file is a derived open-state
adenylate kinase model (4AKE), used for distances only.

These are the tests that would catch a wrong constant: a per-residue extension
figure that is too small makes real protein segments look impossible, and a
clash tolerance that is too tight makes a real packed interface look like an
overlap.
"""

import unittest
from math import dist
from pathlib import Path

from linkerforge.geometry.constants import (
    CA_VIRTUAL_BOND_ANGSTROM,
    DISULFIDE_CA_CA_WINDOW_ANGSTROM,
    EXTENDED_RISE_DEFAULT_ANGSTROM,
)
from linkerforge.geometry.junction import (
    CLASH_OVERLAP_TOLERANCE_ANGSTROM,
    _clashes,
    evaluate_junction,
    evaluate_tether_set,
)
from linkerforge.geometry.occlusion import required_path_length
from linkerforge.geometry.rigid import IDENTITY
from linkerforge.geometry.span import minimum_residues
from linkerforge.geometry.structure import read_chains

FIXTURES = Path(__file__).parent / "fixtures" / "geometry"
PROTEASE = FIXTURES / "4e43_protease_dimer.pdb"
KINASE = FIXTURES / "adk_open_4ake_ca.pdb"


def _chain_alphas(path: Path) -> dict[str, list[tuple[float, float, float]]]:
    return {
        identifier: [residue.ca for residue in chain.residues]
        for identifier, chain in read_chains(path).items()
    }


class VirtualBondTests(unittest.TestCase):
    """Is 3.8 A per residue the right ceiling? Measure it."""

    def test_consecutive_alpha_carbons_sit_at_the_virtual_bond_length(self):
        for identifier, alphas in _chain_alphas(PROTEASE).items():
            steps = [dist(alphas[i], alphas[i + 1]) for i in range(len(alphas) - 1)]
            mean = sum(steps) / len(steps)
            self.assertAlmostEqual(mean, CA_VIRTUAL_BOND_ANGSTROM, delta=0.05, msg=identifier)
            self.assertLess(max(steps), CA_VIRTUAL_BOND_ANGSTROM + 0.1, msg=identifier)

    def test_no_real_segment_is_shorter_than_the_calculator_demands(self):
        # For every window of k consecutive residues in both structures, a
        # k-residue linker must be judged able to span the gap it actually
        # spans. A violation would mean the bound rejects real geometry.
        for path in (PROTEASE, KINASE):
            for identifier, alphas in _chain_alphas(path).items():
                for k in range(1, 31):
                    for start in range(len(alphas) - k - 1):
                        separation = dist(alphas[start], alphas[start + k + 1])
                        self.assertLessEqual(
                            minimum_residues(separation),
                            k,
                            msg=f"{path.name} chain {identifier!r} window {start}+{k}",
                        )

    def test_the_design_figure_is_exceeded_by_real_extended_segments(self):
        # 3.5 A per residue is a design convention, not a physical ceiling, and
        # this is the evidence: real short extended segments beat it. It is why
        # the required-length bound uses 3.8 A and reports 3.5 A separately.
        exceeded = 0
        for identifier, alphas in _chain_alphas(PROTEASE).items():
            for k in range(1, 6):
                for start in range(len(alphas) - k - 1):
                    separation = dist(alphas[start], alphas[start + k + 1])
                    if minimum_residues(separation, EXTENDED_RISE_DEFAULT_ANGSTROM) > k:
                        exceeded += 1
        self.assertGreater(exceeded, 0)


class ClashToleranceTests(unittest.TestCase):
    def test_a_real_packed_interface_is_not_called_a_clash(self):
        chains = read_chains(PROTEASE)
        report = _clashes(chains["A"], chains["B"], IDENTITY, (0.0, 0.0, 0.0))
        self.assertFalse(report["domains_clash"], report)
        self.assertEqual(report["clashing_atom_pairs"], 0)

    def test_the_tolerance_is_above_the_worst_real_overlap_but_not_far_above(self):
        chains = read_chains(PROTEASE)
        worst = 0.0
        b_atoms = [atom for residue in chains["B"].residues for atom in residue.atoms]
        for residue in chains["A"].residues:
            for atom in residue.atoms:
                for other in b_atoms:
                    worst = max(worst, (atom.radius + other.radius) - dist(atom.point, other.point))
        self.assertLess(worst, CLASH_OVERLAP_TOLERANCE_ANGSTROM)
        self.assertGreater(worst, CLASH_OVERLAP_TOLERANCE_ANGSTROM - 0.3)


class JunctionReportTests(unittest.TestCase):
    def test_the_protease_dimer_termini_need_almost_no_linker(self):
        chains = read_chains(PROTEASE)
        report = evaluate_junction(chains["A"], 99, chains["B"], 1, "flexible", requested_residues=5)
        span = report["span"]["straight_ca_distance_angstrom"]
        self.assertAlmostEqual(span, 5.6, delta=0.1)
        self.assertEqual(report["required_linker_length"]["minimum_residues"], 1)
        self.assertFalse(report["span"]["path"]["passes_through_domain"])
        self.assertEqual(report["requested_length_verdict"]["verdict"], "bridgeable")

    def test_the_new_terminus_of_the_second_subunit_is_solvent_exposed(self):
        chains = read_chains(PROTEASE)
        report = evaluate_junction(chains["A"], 99, chains["B"], 1, "flexible")
        anchor = report["accessibility"]["domain_b_anchor"]
        self.assertEqual(anchor["residue"], "B1")
        self.assertEqual(anchor["band"], "exposed")
        self.assertGreater(anchor["relative_solvent_accessibility"], 0.25)

    def test_orientation_is_reported_for_both_anchors(self):
        chains = read_chains(PROTEASE)
        report = evaluate_junction(chains["A"], 99, chains["B"], 1, "flexible")
        for side in ("domain_a", "domain_b"):
            orientation = report["orientation"][side]
            self.assertIn("chain_exit_angle_to_span_degrees", orientation)
            self.assertIn("anchor_faces_partner_domain", orientation)

    def test_a_terminal_residue_has_no_exit_vector_and_says_so(self):
        chains = read_chains(PROTEASE)
        # Residue 1 of chain A has no preceding residue, so a C-terminal exit
        # vector cannot be defined there.
        report = evaluate_junction(chains["A"], 1, chains["B"], 2, "flexible")
        self.assertIn("chain_exit_angle_note", report["orientation"]["domain_a"])

    def test_a_blocked_path_through_the_kinase_lengthens_the_requirement(self):
        chain = next(iter(read_chains(KINASE).values()))
        atoms = tuple(
            atom
            for residue in chain.residues
            if residue.number not in (30, 120)
            for atom in residue.atoms
        )
        report = required_path_length(chain.residue(30).ca, chain.residue(120).ca, atoms)
        self.assertTrue(report["passes_through_domain"])
        self.assertTrue(report["detour_lower_bound"])
        self.assertGreater(report["path_length_angstrom"], report["straight_distance_angstrom"])


class TetherSetTests(unittest.TestCase):
    def test_the_native_dimer_satisfies_two_tethers_in_its_own_frame(self):
        # The crystal placement itself is a witness: both termini pairs are
        # within reach of a short linker, which is what makes single-chain
        # tethered protease dimers possible.
        chains = read_chains(PROTEASE)
        report = evaluate_tether_set(
            chains["A"], chains["B"], ((99, 1, "flexible", 2), (1, 99, "flexible", 2))
        )
        self.assertEqual(report["verdict"], "feasible_with_witness")
        self.assertEqual(report["placement"]["placement_source"], "input_frame")
        self.assertEqual(report["steric_check"]["clashing_atom_pairs"], 0)
        self.assertEqual(report["chain_topology"]["topology"], "insertional")

    def test_a_disulfide_tether_fits_the_published_distance_window(self):
        chains = read_chains(PROTEASE)
        separation = dist(chains["A"].residue(99).ca, chains["B"].residue(1).ca)
        lower, upper = DISULFIDE_CA_CA_WINDOW_ANGSTROM
        self.assertTrue(lower <= separation <= upper)
        report = evaluate_tether_set(chains["A"], chains["B"], ((99, 1, "disulfide", 0),))
        self.assertEqual(report["verdict"], "feasible_with_witness")
        self.assertEqual(report["chain_topology"]["topology"], "crosslink_only")

    def test_mismatched_anchor_separations_are_certified_infeasible_on_real_coordinates(self):
        chains = read_chains(PROTEASE)
        report = evaluate_tether_set(
            chains["A"], chains["B"], ((99, 1, "flexible", 1), (37, 2, "flexible", 1))
        )
        self.assertEqual(report["verdict"], "certified_infeasible")
        self.assertTrue(report["pairwise_necessary_condition"]["certified_infeasible"])

    def test_a_disulfide_cannot_be_given_linker_residues(self):
        chains = read_chains(PROTEASE)
        with self.assertRaisesRegex(ValueError, "no linker residues"):
            evaluate_tether_set(chains["A"], chains["B"], ((99, 1, "disulfide", 4),))

    def test_unknown_tether_type_is_an_error(self):
        chains = read_chains(PROTEASE)
        with self.assertRaisesRegex(ValueError, "Unknown tether type"):
            evaluate_tether_set(chains["A"], chains["B"], ((99, 1, "staple", 0),))


class StructureReaderTests(unittest.TestCase):
    def test_chains_and_residues_are_read_as_the_file_numbers_them(self):
        chains = read_chains(PROTEASE)
        self.assertEqual(sorted(chains), ["A", "B"])
        self.assertEqual(len(chains["A"].residues), 99)
        self.assertEqual(chains["A"].residue(99).name, "PHE")
        self.assertEqual(chains["A"].index_of(1), 0)

    def test_a_missing_residue_or_chain_is_an_error(self):
        chains = read_chains(PROTEASE)
        with self.assertRaisesRegex(ValueError, "no residue 400"):
            chains["A"].residue(400)
        with self.assertRaisesRegex(ValueError, "not found"):
            read_chains(PROTEASE)["A"].residues  # sanity: chain A exists
            from linkerforge.geometry.structure import read_chain

            read_chain(PROTEASE, "Z")

    def test_a_reversed_span_is_an_error(self):
        chains = read_chains(PROTEASE)
        with self.assertRaisesRegex(ValueError, "reversed"):
            chains["A"].span(50, 20)


if __name__ == "__main__":
    unittest.main()
