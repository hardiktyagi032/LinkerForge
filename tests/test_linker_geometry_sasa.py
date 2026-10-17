"""Numerical accessibility checked against closed-form sphere geometry."""

import unittest
from math import pi

from linkerforge.geometry.constants import (
    MAX_ASA_ANGSTROM2,
    SOLVENT_PROBE_RADIUS_ANGSTROM,
    VDW_RADII_ANGSTROM,
)
from linkerforge.geometry.sasa import (
    atom_sasa,
    relative_accessibility,
    residue_sasa,
    sphere_points,
)
from linkerforge.geometry.structure import Atom, Residue

PROBE = SOLVENT_PROBE_RADIUS_ANGSTROM
CARBON = VDW_RADII_ANGSTROM["C"]
FINE = sphere_points(4096)


def _carbon(x: float, y: float = 0.0, z: float = 0.0, name: str = "C") -> Atom:
    return Atom(name, "C", (x, y, z), CARBON)


class AnalyticComparisonTests(unittest.TestCase):
    def test_isolated_atom_matches_the_full_sphere_area(self):
        atom = _carbon(0.0)
        expected = 4.0 * pi * (CARBON + PROBE) ** 2
        self.assertAlmostEqual(atom_sasa(atom, (atom,), points=FINE), expected, delta=expected * 0.01)

    def test_two_overlapping_atoms_match_the_spherical_cap_formula(self):
        # Exposed area of sphere 1 = 4*pi*R1^2 - 2*pi*R1*h, with the cap height
        # h = R1 - (d^2 + R1^2 - R2^2) / (2d) for spheres of equal radius here.
        separation = 2.5
        first, second = _carbon(0.0), _carbon(separation)
        expanded = CARBON + PROBE
        cap = expanded - separation / 2.0
        expected = 4.0 * pi * expanded**2 - 2.0 * pi * expanded * cap
        self.assertAlmostEqual(
            atom_sasa(first, (first, second), points=FINE), expected, delta=expected * 0.02
        )

    def test_an_enclosed_atom_has_no_accessible_surface(self):
        # Six neighbours at 2 A along each axis bury the central atom: the probe
        # sphere has no point further than r + probe from every neighbour.
        centre = _carbon(0.0)
        shell = tuple(
            _carbon(*offset)
            for offset in (
                (2.0, 0.0, 0.0),
                (-2.0, 0.0, 0.0),
                (0.0, 2.0, 0.0),
                (0.0, -2.0, 0.0),
                (0.0, 0.0, 2.0),
                (0.0, 0.0, -2.0),
            )
        )
        self.assertEqual(atom_sasa(centre, (centre,) + shell, points=FINE), 0.0)

    def test_sphere_points_are_on_the_unit_sphere(self):
        for point in sphere_points(64):
            self.assertAlmostEqual(sum(value * value for value in point), 1.0, places=6)

    def test_too_few_sphere_points_is_an_error(self):
        with self.assertRaises(ValueError):
            sphere_points(3)


class RelativeAccessibilityTests(unittest.TestCase):
    def _residue(self, name: str) -> Residue:
        return Residue("A", 1, " ", name, (_carbon(0.0, name="CA"),))

    def test_an_isolated_residue_is_reported_as_exposed(self):
        residue = self._residue("GLY")
        report = relative_accessibility(residue, residue.atoms, points=FINE)
        self.assertEqual(report["band"], "exposed")
        self.assertEqual(report["max_asa_angstrom2"], MAX_ASA_ANGSTROM2["GLY"])
        self.assertGreater(report["relative_solvent_accessibility"], 0.25)

    def test_residue_area_is_the_sum_over_its_atoms(self):
        residue = Residue(
            "A", 7, " ", "ALA", (_carbon(0.0, name="CA"), _carbon(1.5, name="CB"))
        )
        total = sum(atom_sasa(atom, residue.atoms, points=FINE) for atom in residue.atoms)
        self.assertAlmostEqual(residue_sasa(residue, residue.atoms, points=FINE), total, places=6)

    def test_a_non_standard_residue_gets_no_invented_normalisation(self):
        residue = self._residue("MSE")
        report = relative_accessibility(residue, residue.atoms, points=FINE)
        self.assertIsNone(report["relative_solvent_accessibility"])
        self.assertEqual(report["band"], "unknown_residue_type")

    def test_buried_band_is_reported_for_an_enclosed_residue(self):
        residue = self._residue("GLY")
        shell = tuple(
            _carbon(*offset)
            for offset in ((2.0, 0.0, 0.0), (-2.0, 0.0, 0.0), (0.0, 2.0, 0.0), (0.0, -2.0, 0.0), (0.0, 0.0, 2.0), (0.0, 0.0, -2.0))
        )
        report = relative_accessibility(residue, residue.atoms + shell, points=FINE)
        self.assertEqual(report["band"], "buried")


if __name__ == "__main__":
    unittest.main()
