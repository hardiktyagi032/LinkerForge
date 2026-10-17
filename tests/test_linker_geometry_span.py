"""Required linker length: exact bounds, both ends of the window, chain statistics."""

import unittest

from linkerforge.geometry.constants import (
    CA_VIRTUAL_BOND_ANGSTROM,
    GS_CHAIN_STATISTICS,
    HELIX_RISE_DEFAULT_ANGSTROM,
)
from linkerforge.geometry.span import (
    comfortable_residues,
    flexible_strain,
    flexible_window,
    gaussian_rms_end_to_end,
    helical_window,
    maximum_span,
    minimum_residues,
    required_length,
    verdict_for_requested_length,
    wormlike_rms_end_to_end,
)


class MinimumLengthTests(unittest.TestCase):
    def test_a_linker_spans_one_more_bond_than_it_has_residues(self):
        # n residues between two anchors make n + 1 virtual Ca-Ca bonds.
        self.assertAlmostEqual(maximum_span(0), CA_VIRTUAL_BOND_ANGSTROM)
        self.assertAlmostEqual(maximum_span(4), 5 * CA_VIRTUAL_BOND_ANGSTROM)

    def test_minimum_residues_is_exact_at_the_physical_ceiling(self):
        self.assertEqual(minimum_residues(0.0), 0)
        self.assertEqual(minimum_residues(3.8), 0)
        self.assertEqual(minimum_residues(3.81), 1)
        self.assertEqual(minimum_residues(7.6), 1)
        self.assertEqual(minimum_residues(7.61), 2)

    def test_design_figure_is_never_below_the_physical_bound(self):
        for distance in (1.0, 5.6, 12.0, 23.7, 40.0, 97.3):
            window = flexible_window(distance)
            self.assertGreaterEqual(window["minimum_residues_design"], window["minimum_residues"])
            self.assertEqual(
                window["minimum_residues_range"][0], window["minimum_residues"]
            )

    def test_negative_inputs_are_errors(self):
        with self.assertRaises(ValueError):
            minimum_residues(-1.0)
        with self.assertRaises(ValueError):
            maximum_span(-1)
        with self.assertRaises(ValueError):
            flexible_window(-0.1)


class FlexibleWindowTests(unittest.TestCase):
    def test_flexible_linkers_have_no_geometric_upper_bound(self):
        window = required_length(30.0, "flexible")
        self.assertIsNone(window["maximum_residues"])
        self.assertEqual(
            verdict_for_requested_length(window, 500)["verdict"], "bridgeable"
        )

    def test_too_short_is_reported_with_the_number_needed(self):
        window = required_length(30.0, "flexible")
        verdict = verdict_for_requested_length(window, 2)
        self.assertEqual(verdict["verdict"], "too_short")
        self.assertIn(str(window["minimum_residues"]), verdict["reason"])

    def test_unstrained_length_exceeds_the_minimum_and_is_monotone(self):
        previous = -1
        for distance in (5.0, 10.0, 20.0, 40.0, 80.0):
            window = flexible_window(distance)
            self.assertGreaterEqual(window["unstrained_residues"], window["minimum_residues"])
            self.assertGreater(window["unstrained_residues"], previous)
            previous = window["unstrained_residues"]

    def test_strain_flags_a_linker_that_must_be_nearly_fully_extended(self):
        # 11 residues over 40 A is 0.87 of the contour length.
        strain = flexible_strain(40.0, 11)
        self.assertTrue(strain["near_full_extension"])
        self.assertTrue(strain["requires_stretching_beyond_rms"])
        relaxed = flexible_strain(40.0, 80)
        self.assertFalse(relaxed["near_full_extension"])
        self.assertFalse(relaxed["requires_stretching_beyond_rms"])

    def test_comfortable_length_is_where_the_unstretched_chain_reaches(self):
        residues = comfortable_residues(30.0, "G2S4")
        _, ratio = GS_CHAIN_STATISTICS["G2S4"]
        self.assertGreaterEqual(gaussian_rms_end_to_end(residues, ratio), 30.0)
        self.assertLess(gaussian_rms_end_to_end(residues - 1, ratio), 30.0)


class ChainStatisticsTests(unittest.TestCase):
    def test_gaussian_and_wormlike_models_agree_for_a_long_flexible_linker(self):
        # van Rosmalen et al. (2017) report that the two models give very
        # similar results for these linkers; 73 residues of (GS5)9.
        persistence, ratio = GS_CHAIN_STATISTICS["GS5"]
        gaussian = gaussian_rms_end_to_end(73, ratio)
        wormlike = wormlike_rms_end_to_end(73, persistence)
        self.assertLess(abs(gaussian - wormlike) / gaussian, 0.1)

    def test_predicted_end_to_end_distance_matches_the_published_measurement(self):
        # Published ensemble mean end-to-end distance for (G2S4)1, 25 residues,
        # is 27.4 A (WLC) / 27.1 A (Gaussian chain). An RMS value computed from
        # the published C_inf should land near that, not at twice or half it.
        _, ratio = GS_CHAIN_STATISTICS["G2S4"]
        self.assertAlmostEqual(gaussian_rms_end_to_end(25, ratio), 29.4, delta=2.5)

    def test_zero_length_chains_have_zero_extent(self):
        self.assertEqual(gaussian_rms_end_to_end(0, 2.0), 0.0)
        self.assertEqual(wormlike_rms_end_to_end(0, 4.5), 0.0)


class HelicalWindowTests(unittest.TestCase):
    def test_a_rigid_linker_has_a_window_at_both_ends(self):
        window = helical_window(40.0)
        self.assertTrue(window["window_exists"])
        self.assertIsNotNone(window["maximum_residues"])
        self.assertLess(window["minimum_residues"], window["maximum_residues"])
        # The window brackets the rod length that actually matches the span.
        exact = 40.0 / HELIX_RISE_DEFAULT_ANGSTROM - 1
        self.assertLessEqual(window["minimum_residues"], exact)
        self.assertGreaterEqual(window["maximum_residues"], exact)

    def test_too_long_a_rigid_linker_is_a_failure_mode_of_its_own(self):
        window = helical_window(40.0)
        verdict = verdict_for_requested_length(window, int(window["maximum_residues"]) + 1)
        self.assertEqual(verdict["verdict"], "too_long")
        self.assertIn("rigid helix", verdict["reason"])

    def test_a_helical_linker_needs_more_residues_than_a_flexible_one(self):
        # 1.5 A of axial rise per residue against 3.8 A of chain extension.
        self.assertGreater(
            helical_window(40.0)["minimum_residues"],
            flexible_window(40.0)["minimum_residues"],
        )

    def test_unknown_linker_type_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "Unknown linker type"):
            required_length(10.0, "coiled_coil")


if __name__ == "__main__":
    unittest.main()
