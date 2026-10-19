"""Path clearance, detour bounds and the rigid-body algebra underneath them."""

import unittest
from math import acos, dist, pi, sqrt

from linkerforge.geometry.constants import VDW_RADII_ANGSTROM
from linkerforge.geometry.occlusion import (
    detour_length_around_sphere,
    enclosing_sphere,
    path_clearance,
    point_segment_distance,
    required_path_length,
)
from linkerforge.geometry.rigid import (
    apply,
    optimal_superposition,
    quaternion_from_axis_angle,
    rotation_from_quaternion,
)
from linkerforge.geometry.structure import Atom

CARBON = VDW_RADII_ANGSTROM["C"]


def _carbon(x: float, y: float = 0.0, z: float = 0.0) -> Atom:
    return Atom("C", "C", (x, y, z), CARBON)


class SegmentDistanceTests(unittest.TestCase):
    def test_perpendicular_distance_inside_the_segment(self):
        self.assertAlmostEqual(
            point_segment_distance((5.0, 3.0, 0.0), (0.0, 0.0, 0.0), (10.0, 0.0, 0.0)), 3.0
        )

    def test_distance_beyond_an_endpoint_is_measured_to_that_endpoint(self):
        self.assertAlmostEqual(
            point_segment_distance((-4.0, 3.0, 0.0), (0.0, 0.0, 0.0), (10.0, 0.0, 0.0)), 5.0
        )

    def test_degenerate_segment_falls_back_to_point_distance(self):
        self.assertAlmostEqual(
            point_segment_distance((0.0, 0.0, 3.0), (1.0, 1.0, 1.0), (1.0, 1.0, 1.0)),
            dist((0.0, 0.0, 3.0), (1.0, 1.0, 1.0)),
        )


class PathClearanceTests(unittest.TestCase):
    def test_an_open_path_is_not_blocked(self):
        atoms = (_carbon(5.0, 12.0), _carbon(5.0, -12.0))
        report = path_clearance((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), atoms)
        self.assertFalse(report["passes_through_domain"])
        self.assertAlmostEqual(report["minimum_clearance_angstrom"], 12.0 - CARBON, places=3)

    def test_an_atom_on_the_line_blocks_the_path(self):
        atoms = (_carbon(5.0, 1.0),)
        report = path_clearance((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), atoms)
        self.assertTrue(report["passes_through_domain"])
        self.assertEqual(report["blocking_atom_count"], 1)

    def test_no_atoms_leaves_the_clearance_undefined_rather_than_zero(self):
        report = path_clearance((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), ())
        self.assertIsNone(report["minimum_clearance_angstrom"])
        self.assertFalse(report["passes_through_domain"])


class DetourTests(unittest.TestCase):
    def test_detour_matches_the_tangent_arc_tangent_closed_form(self):
        start, end, centre, radius = (-10.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 0.0, 0.0), 5.0
        tangent = sqrt(10.0**2 - radius**2)
        arc = pi - 2 * acos(radius / 10.0)
        expected = 2 * tangent + radius * arc
        self.assertAlmostEqual(
            detour_length_around_sphere(start, end, centre, radius), expected, places=6
        )

    def test_a_sphere_off_the_path_does_not_lengthen_it(self):
        start, end = (-10.0, 0.0, 0.0), (10.0, 0.0, 0.0)
        self.assertAlmostEqual(
            detour_length_around_sphere(start, end, (0.0, 40.0, 0.0), 5.0), 20.0
        )

    def test_a_detour_is_always_at_least_the_straight_distance(self):
        start, end = (-10.0, 0.0, 0.0), (10.0, 0.0, 0.0)
        for radius in (1.0, 3.0, 5.0, 8.0, 9.5):
            self.assertGreaterEqual(
                detour_length_around_sphere(start, end, (0.0, 0.0, 0.0), radius), 20.0
            )

    def test_an_anchor_inside_the_obstacle_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "inside the obstacle"):
            detour_length_around_sphere((1.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 0.0, 0.0), 5.0)

    def test_enclosing_sphere_covers_every_atom_surface(self):
        atoms = (_carbon(0.0), _carbon(4.0), _carbon(0.0, 3.0))
        centre, radius = enclosing_sphere(atoms)
        for atom in atoms:
            self.assertLessEqual(dist(centre, atom.point) + atom.radius, radius + 1e-9)

    def test_a_blocked_path_reports_a_longer_required_length(self):
        blocking = tuple(_carbon(0.0, y, 0.0) for y in (-1.0, 0.0, 1.0))
        report = required_path_length((-10.0, 0.0, 0.0), (10.0, 0.0, 0.0), blocking)
        self.assertTrue(report["passes_through_domain"])
        self.assertTrue(report["detour_lower_bound"])
        self.assertGreater(report["path_length_angstrom"], report["straight_distance_angstrom"])

    def test_an_open_path_uses_the_straight_line(self):
        report = required_path_length((-10.0, 0.0, 0.0), (10.0, 0.0, 0.0), (_carbon(0.0, 30.0),))
        self.assertEqual(report["path_model"], "straight_line")
        self.assertEqual(report["path_length_angstrom"], report["straight_distance_angstrom"])


class RigidBodyTests(unittest.TestCase):
    def test_a_known_motion_is_recovered_exactly(self):
        points = ((0.0, 0.0, 0.0), (5.0, 0.0, 0.0), (0.0, 7.0, 0.0), (0.0, 0.0, 3.0))
        rotation = rotation_from_quaternion(
            quaternion_from_axis_angle((1.0, 2.0, 3.0), 0.9)
        )
        translation = (4.0, -2.0, 11.0)
        moved = tuple(apply(rotation, translation, point) for point in points)
        recovered_rotation, recovered_translation = optimal_superposition(points, moved)
        for point, expected in zip(points, moved):
            placed = apply(recovered_rotation, recovered_translation, point)
            self.assertAlmostEqual(dist(placed, expected), 0.0, places=6)

    def test_the_solution_is_a_rotation_and_never_a_reflection(self):
        points = ((0.0, 0.0, 0.0), (5.0, 0.0, 0.0), (0.0, 7.0, 0.0), (0.0, 0.0, 3.0))
        mirrored = tuple((-x, y, z) for x, y, z in points)
        rotation, _ = optimal_superposition(points, mirrored)
        determinant = (
            rotation[0][0] * (rotation[1][1] * rotation[2][2] - rotation[1][2] * rotation[2][1])
            - rotation[0][1] * (rotation[1][0] * rotation[2][2] - rotation[1][2] * rotation[2][0])
            + rotation[0][2] * (rotation[1][0] * rotation[2][1] - rotation[1][1] * rotation[2][0])
        )
        self.assertAlmostEqual(determinant, 1.0, places=6)

    def test_mismatched_point_sets_are_errors(self):
        with self.assertRaises(ValueError):
            optimal_superposition(((0.0, 0.0, 0.0),), ())
        with self.assertRaises(ValueError):
            optimal_superposition((), ())


if __name__ == "__main__":
    unittest.main()
