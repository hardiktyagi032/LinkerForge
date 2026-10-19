"""Several simultaneous tethers: what is proved, what is searched, what topology it needs."""

import unittest
from math import dist

from linkerforge.geometry.rigid import apply, quaternion_from_axis_angle, rotation_from_quaternion
from linkerforge.geometry.tether import (
    TetherConstraint,
    find_placement,
    implied_chain_topology,
    pairwise_consistency,
    placement_violation,
)

TETRAHEDRON = (
    (0.0, 0.0, 0.0),
    (10.0, 0.0, 0.0),
    (3.0, 9.0, 0.0),
    (4.0, 3.0, 8.0),
)


def _constraints(
    anchors_a: tuple[tuple[float, float, float], ...],
    anchors_b: tuple[tuple[float, float, float], ...],
    lower: float = 0.0,
    upper: float = 5.0,
) -> tuple[TetherConstraint, ...]:
    return tuple(
        TetherConstraint(f"t{index}", a, b, lower, upper)
        for index, (a, b) in enumerate(zip(anchors_a, anchors_b))
    )


class PairwiseConditionTests(unittest.TestCase):
    def test_incompatible_anchor_separations_are_certified_infeasible(self):
        # 30 A apart on domain A, 5 A apart on domain B, and two 2 A tethers
        # cannot absorb a 25 A mismatch, whatever the placement.
        constraints = _constraints(
            ((0.0, 0.0, 0.0), (30.0, 0.0, 0.0)),
            ((0.0, 0.0, 0.0), (5.0, 0.0, 0.0)),
            upper=2.0,
        )
        report = pairwise_consistency(constraints)
        self.assertTrue(report["certified_infeasible"])
        self.assertFalse(report["pairs"][0]["pair_satisfiable"])

    def test_matching_separations_pass_the_condition(self):
        constraints = _constraints(
            ((0.0, 0.0, 0.0), (30.0, 0.0, 0.0)),
            ((0.0, 0.0, 0.0), (28.0, 0.0, 0.0)),
            upper=2.0,
        )
        self.assertFalse(pairwise_consistency(constraints)["certified_infeasible"])

    def test_a_single_tether_has_no_pairwise_condition(self):
        report = pairwise_consistency(_constraints((TETRAHEDRON[0],), (TETRAHEDRON[1],)))
        self.assertEqual(report["pairs"], [])
        self.assertFalse(report["certified_infeasible"])

    def test_the_condition_uses_upper_bounds_only_and_so_never_over_rejects(self):
        # Tight lower bounds must not turn a satisfiable pair into a rejection:
        # the condition is a relaxation on purpose.
        constraints = _constraints(
            ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0)),
            ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0)),
            lower=4.0,
            upper=5.0,
        )
        self.assertFalse(pairwise_consistency(constraints)["certified_infeasible"])


class PlacementSearchTests(unittest.TestCase):
    def test_a_displaced_copy_of_the_anchors_is_placed_back(self):
        rotation = rotation_from_quaternion(quaternion_from_axis_angle((1.0, 1.0, 0.0), 1.2))
        moved = tuple(apply(rotation, (20.0, -5.0, 7.0), point) for point in TETRAHEDRON)
        constraints = _constraints(TETRAHEDRON, moved, upper=1.0)
        report = find_placement(constraints, restarts=16, iterations=200, seed=3)
        self.assertTrue(report["placement_found"])
        self.assertLessEqual(report["maximum_violation_angstrom"], report["tolerance_angstrom"])
        # The witness is independently recheckable.
        recheck = placement_violation(constraints, report["rotation"], report["translation"])
        self.assertLessEqual(recheck["maximum_violation_angstrom"], report["tolerance_angstrom"])

    def test_the_input_frame_is_tried_first_and_returned_when_it_already_fits(self):
        constraints = _constraints(TETRAHEDRON, TETRAHEDRON, upper=1.0)
        report = find_placement(constraints, restarts=4, iterations=10)
        self.assertTrue(report["placement_found"])
        self.assertEqual(report["translation"], (0.0, 0.0, 0.0))
        self.assertEqual(report["tethers"][0]["span_angstrom"], 0.0)

    def test_a_mirror_image_anchor_set_is_not_claimed_feasible(self):
        # Every pairwise distance is identical, so the necessary condition
        # passes, but no rotation superposes a chiral set on its mirror image.
        mirrored = tuple((-x, y, z) for x, y, z in TETRAHEDRON)
        constraints = _constraints(TETRAHEDRON, mirrored, upper=0.5)
        self.assertFalse(pairwise_consistency(constraints)["certified_infeasible"])
        report = find_placement(constraints, restarts=24, iterations=200, seed=5)
        self.assertFalse(report["placement_found"])
        self.assertGreater(report["maximum_violation_angstrom"], 0.5)
        self.assertIn("not a proof of infeasibility", report["interpretation"])

    def test_one_tether_is_satisfied_by_translation_alone(self):
        constraints = _constraints(((0.0, 0.0, 0.0),), ((50.0, 50.0, 50.0),), upper=2.0)
        report = find_placement(constraints, restarts=2, iterations=50)
        self.assertTrue(report["placement_found"])
        placed = apply(report["rotation"], report["translation"], (50.0, 50.0, 50.0))
        self.assertLessEqual(dist(placed, (0.0, 0.0, 0.0)), 2.0 + 1e-6)

    def test_several_satisfying_placements_are_returned_for_screening(self):
        constraints = _constraints(
            ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0)),
            ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0)),
            upper=6.0,
        )
        report = find_placement(constraints, restarts=8, iterations=100, seed=1)
        self.assertTrue(report["placement_found"])
        self.assertGreaterEqual(len(report["satisfying_placements"]), 2)

    def test_lower_bounds_are_enforced_not_just_upper_ones(self):
        # A rigid tether that must hold the anchors 10 A apart: a placement that
        # puts them on top of each other is a violation.
        constraints = _constraints(TETRAHEDRON, TETRAHEDRON, lower=9.0, upper=11.0)
        zero = placement_violation(constraints, ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), (0.0, 0.0, 0.0))
        self.assertGreater(zero["maximum_violation_angstrom"], 8.0)

    def test_bad_constraints_are_errors(self):
        with self.assertRaises(ValueError):
            TetherConstraint("bad", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), -1.0, 5.0)
        with self.assertRaises(ValueError):
            TetherConstraint("bad", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 6.0, 5.0)
        with self.assertRaises(ValueError):
            find_placement(())


class ChainTopologyTests(unittest.TestCase):
    def test_one_peptide_tether_is_a_tandem_fusion(self):
        self.assertEqual(implied_chain_topology(1)["topology"], "tandem")

    def test_two_peptide_tethers_require_an_insertional_topology(self):
        report = implied_chain_topology(2)
        self.assertEqual(report["topology"], "insertional")
        self.assertEqual(report["chain_crossings_required"], 2)

    def test_three_peptide_tethers_require_splitting_a_domain(self):
        self.assertEqual(implied_chain_topology(3)["topology"], "split_or_non_peptide")

    def test_a_disulfide_costs_no_chain_crossing(self):
        # Two tethers, one of them a disulfide, stays a tandem fusion.
        report = implied_chain_topology(2, peptide_tethers=1)
        self.assertEqual(report["topology"], "tandem")
        self.assertEqual(report["non_peptide_tethers"], 1)
        self.assertEqual(report["chain_crossings_required"], 1)

    def test_crosslinks_only_means_there_is_no_fusion_protein(self):
        report = implied_chain_topology(2, peptide_tethers=0)
        self.assertEqual(report["topology"], "crosslink_only")

    def test_impossible_counts_are_errors(self):
        with self.assertRaises(ValueError):
            implied_chain_topology(0)
        with self.assertRaises(ValueError):
            implied_chain_topology(2, peptide_tethers=3)


if __name__ == "__main__":
    unittest.main()
