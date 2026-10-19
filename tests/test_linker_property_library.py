"""Tests for the curated linker property library and its two property callers.

These tests guard the honesty properties of the library, not just the plumbing:
no invented sequences, no silent promotion of 'unassigned' to a real label, and
no negative cleavability call dressed up as 'not cleavable'.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from linkerforge.properties import (  # noqa: E402
    call_cleavability,
    composition_features,
    feature_names,
    featurise,
    fit_rigidity_model,
    leave_one_out_report,
    load_library,
    modelling_subset,
)
from linkerforge.properties.cleavability import build_motif_table  # noqa: E402

LIBRARY_PATH = REPO_ROOT / "data" / "curated" / "linker_property_library_sources.v1.json"
SCHEMA_PATH = REPO_ROOT / "schemas" / "linker_property_library.v1.schema.json"

STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWY")


class TestLibraryIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = load_library(LIBRARY_PATH)
        cls.raw = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))

    def test_loads(self):
        self.assertTrue(self.library.entries)
        self.assertEqual(self.library.library_id, "linker_property_library.v1")

    def test_schema_file_is_valid_json_and_matches_version(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            schema["properties"]["schema_version"]["const"], self.raw["schema_version"]
        )

    def test_entry_ids_unique(self):
        ids = [e.entry_id for e in self.library.entries]
        self.assertEqual(len(ids), len(set(ids)))

    def test_sequences_are_standard_residues_only(self):
        for entry in self.library.entries:
            if entry.sequence is None:
                continue
            bad = set(entry.sequence) - STANDARD_AA
            self.assertFalse(
                bad, "entry %s has non-standard residues %s" % (entry.entry_id, bad)
            )

    def test_no_sequence_means_excluded_from_model(self):
        """A pattern or compressed notation must never become a fake sequence."""
        for entry in self.library.entries:
            if entry.sequence is None:
                self.assertTrue(
                    entry.excluded_from_model,
                    "entry %s has no sequence but is not excluded" % entry.entry_id,
                )
                self.assertTrue(entry.exclusion_reason)

    def test_every_entry_cites_a_declared_source(self):
        for entry in self.library.entries:
            self.assertIn(entry.source_key, self.library.sources)
            self.assertTrue(entry.source_locator)
            self.assertTrue(entry.attributed_origin)

    def test_every_cleavable_entry_names_a_protease(self):
        for entry in self.library.entries:
            if entry.cleavability_label == "cleavable":
                self.assertTrue(
                    entry.protease, "cleavable entry %s names no protease" % entry.entry_id
                )

    def test_unassigned_is_never_offered_as_a_class(self):
        for axis in ("rigidity", "cleavability"):
            subset = modelling_subset(self.library, axis)
            for entry in subset:
                label = (
                    entry.rigidity_label
                    if axis == "rigidity"
                    else entry.cleavability_label
                )
                self.assertNotEqual(label, "unassigned")

    def test_inferred_labels_are_marked_as_inferred(self):
        """Non-cleavable labels derived from category exclusion must say so."""
        for entry in self.library.entries:
            if (
                entry.cleavability_label == "non_cleavable"
                and entry.cleavability_basis == "source_stated"
            ):
                self.fail(
                    "entry %s claims a source-stated non-cleavable label; the "
                    "curation source assigns cleavability by category, so this "
                    "must be inferred_from_category_exclusion" % entry.entry_id
                )

    def test_composite_template_exists_for_rigid_cleavable(self):
        """The physically awkward combination must be represented as parts."""
        targets = [
            tpl["target_properties"] for tpl in self.library.composite_templates
        ]
        self.assertIn({"rigidity": "rigid", "cleavability": "cleavable"}, targets)
        for tpl in self.library.composite_templates:
            self.assertTrue(tpl["evidence"], "composite template needs evidence")

    def test_acquisition_status_records_unincorporated_sources(self):
        """A cited database must not look like an incorporated one."""
        for key in ("linkerdb", "synlinker"):
            self.assertIn(key, self.library.acquisition_status)
            self.assertIn("NOT ACQUIRED", self.library.acquisition_status[key])


class TestFeatures(unittest.TestCase):
    def test_feature_order_is_stable(self):
        self.assertEqual(len(feature_names()), len(featurise("GGGGS")))

    def test_fractions_sum_sensibly(self):
        feats = composition_features("GGGGS")
        self.assertAlmostEqual(feats["frac_G"], 0.8)
        self.assertAlmostEqual(feats["frac_ST"], 0.2)
        self.assertAlmostEqual(feats["frac_P"], 0.0)

    def test_helical_repeat_composition(self):
        feats = composition_features("EAAAKEAAAK")
        self.assertAlmostEqual(feats["frac_A"], 0.6)
        self.assertAlmostEqual(feats["frac_EK"], 0.4)

    def test_rejects_non_standard_residues(self):
        with self.assertRaises(ValueError):
            featurise("GGXGS")

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            featurise("")


class TestCleavability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = load_library(LIBRARY_PATH)

    def test_motif_table_comes_from_the_library(self):
        table = build_motif_table(self.library)
        self.assertTrue(table)
        for motif, entry in table.items():
            self.assertEqual(entry.sequence, motif)
            self.assertEqual(entry.cleavability_label, "cleavable")

    def test_known_motif_is_called_cleavable_with_a_citation(self):
        call = call_cleavability("PLGLWA", library=self.library)
        self.assertEqual(call.label, "cleavable")
        self.assertTrue(call.matches)
        self.assertIn("MMP", call.proteases[0])
        self.assertTrue(call.matches[0].citation)

    def test_motif_embedded_in_flexible_padding_is_found(self):
        """The composite construction pattern must still be detected."""
        call = call_cleavability("GGGGSPLGLWAGGGGS", library=self.library)
        self.assertEqual(call.label, "cleavable")
        match = call.matches[0]
        self.assertEqual(match.motif, "PLGLWA")
        self.assertEqual(match.start, 6)
        self.assertEqual(match.end, 11)

    def test_negative_call_is_no_known_motif_not_non_cleavable(self):
        call = call_cleavability("GGGGSGGGGSGGGGS", library=self.library)
        self.assertEqual(call.label, "no_known_motif")
        self.assertNotEqual(call.label, "non_cleavable")
        self.assertIn("not that the sequence", call.coverage_note)

    def test_short_basic_motifs_are_excluded_from_matching(self):
        """RR must not make every arginine-containing linker look cleavable."""
        call = call_cleavability("GGRRGG", library=self.library)
        self.assertEqual(call.label, "no_known_motif")

    def test_no_false_positive_on_curated_non_cleavable_entries(self):
        for entry in self.library.entries:
            if entry.sequence is None or entry.cleavability_label != "non_cleavable":
                continue
            call = call_cleavability(entry.sequence, library=self.library)
            self.assertEqual(
                call.label,
                "no_known_motif",
                "non-cleavable entry %s tripped motifs %s"
                % (entry.entry_id, [m.motif for m in call.matches]),
            )


class TestRigidityModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = load_library(LIBRARY_PATH)
        cls.entries = modelling_subset(cls.library, "rigidity")
        cls.sequences = [e.sequence for e in cls.entries]
        cls.labels = [e.rigidity_label for e in cls.entries]

    def test_training_set_has_both_classes(self):
        self.assertIn("rigid", self.labels)
        self.assertIn("flexible", self.labels)

    def test_fits_and_predicts_known_cases(self):
        model = fit_rigidity_model(self.sequences, self.labels)
        self.assertEqual(model.predict("GGGGSGGGGSGGGGS"), "flexible")
        self.assertEqual(model.predict("EAAAKEAAAKEAAAK"), "rigid")

    def test_probabilities_are_in_range(self):
        model = fit_rigidity_model(self.sequences, self.labels)
        for seq in self.sequences:
            p = model.predict_proba(seq)
            self.assertGreaterEqual(p, 0.0)
            self.assertLessEqual(p, 1.0)

    def test_rejects_unknown_label(self):
        with self.assertRaises(ValueError):
            fit_rigidity_model(["GGGGS"], ["springy"])

    def test_leave_one_out_beats_majority_baseline(self):
        report = leave_one_out_report(
            self.sequences, self.labels, permutation_rounds=0
        )
        self.assertGreater(report.accuracy, report.majority_baseline)

    def test_proline_rich_rigidity_is_the_known_failure_mode(self):
        """PAPAP is rigid via proline, not via a helix.

        It is the one out-of-fold miss, and that is the documented limitation:
        one Pro-rich exemplar is not enough for the model to learn the second
        rigidity mechanism. If this test starts failing because PAPAP is now
        predicted correctly, the library gained Pro-rich entries and the
        report's interpretation section needs rewriting.
        """
        report = leave_one_out_report(
            self.sequences, self.labels, permutation_rounds=0
        )
        misses = [r for r in report.out_of_fold if not r["correct"]]
        self.assertEqual([m["sequence"] for m in misses], ["PAPAP"])


if __name__ == "__main__":
    unittest.main()
