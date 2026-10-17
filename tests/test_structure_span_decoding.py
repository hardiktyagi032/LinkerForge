"""Tests for the AlphaFold-feature loader and span decoders (numpy only)."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.linkerforge.detector.span_decoding import (
    evaluate_decoding, hysteresis_decode, viterbi_decode)
from src.linkerforge.structure.af_features import (
    SCHEMA_VERSION, StructureFeatureError, load_registry, parse_registry)

# Tests-only SYNTHETIC fixture: invented numbers, not AlphaFold output.
FIXTURE = {
    "schema_version": SCHEMA_VERSION,
    "provenance": {"source": "SYNTHETIC TEST FIXTURE (not AlphaFold output)",
                   "generated_independent_of_labels": True},
    "entries": {
        "P12345": {"sequence": "MKVLA", "plddt": [90, 85, 40, 35, 80],
                   "pae_mean": [2.0, 3.0, 12.0, 15.0, 4.0]},
        "Q8N158": {"sequence": "GSGS", "plddt": [30, 30, 30, 30]},
    },
}


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.registry = parse_registry(copy.deepcopy(FIXTURE))

    def test_valid_lookup(self):
        entry = self.registry.get("P12345", "mkvla")
        self.assertEqual(entry.plddt.tolist(), [90, 85, 40, 35, 80])
        self.assertIsNone(self.registry.get("Q8N158", "GSGS").pae_mean)

    def test_refuses_missing_accession(self):
        with self.assertRaisesRegex(StructureFeatureError, "No structure features"):
            self.registry.get("P99999", "MKVLA")

    def test_refuses_sequence_and_length_mismatch(self):
        with self.assertRaisesRegex(StructureFeatureError, "Sequence mismatch"):
            self.registry.get("P12345", "MKVLG")
        with self.assertRaisesRegex(StructureFeatureError, "Length mismatch"):
            self.registry.get("P12345", "MKVL")

    def test_require_all_fails_closed_on_any_gap(self):
        self.registry.require_all({"P12345": "MKVLA", "Q8N158": "GSGS"})
        with self.assertRaises(StructureFeatureError):
            self.registry.require_all({"P12345": "MKVLA", "P99999": "AAA"})

    def test_rejects_malformed_documents(self):
        def mutated(fn):
            doc = copy.deepcopy(FIXTURE)
            fn(doc)
            with self.assertRaises(StructureFeatureError):
                parse_registry(doc)
        mutated(lambda d: d.update(schema_version="v0"))
        mutated(lambda d: d["provenance"].update(generated_independent_of_labels=False))
        mutated(lambda d: d["provenance"].pop("source"))
        mutated(lambda d: d["entries"]["P12345"]["plddt"].pop())
        mutated(lambda d: d["entries"]["P12345"]["plddt"].__setitem__(0, 101))
        mutated(lambda d: d["entries"]["P12345"]["plddt"].__setitem__(0, float("nan")))
        mutated(lambda d: d["entries"]["P12345"]["pae_mean"].__setitem__(0, -1))
        mutated(lambda d: d["entries"]["P12345"].update(sequence="MKVLB"))
        mutated(lambda d: d["entries"]["P12345"].update(extra=1))
        mutated(lambda d: d["entries"].update(bad_id={"sequence": "A", "plddt": [1]}))
        mutated(lambda d: d.update(entries={}))

    def test_load_from_file_and_missing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "af.json"
            path.write_text(json.dumps(FIXTURE), encoding="utf-8")
            self.assertEqual(len(load_registry(path)), 2)
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(StructureFeatureError):
                load_registry(path)
            with self.assertRaises(StructureFeatureError):
                load_registry(Path(folder) / "absent.json")


class DecoderTests(unittest.TestCase):
    def test_hysteresis_requires_high_seed_and_merges_gap(self):
        p = [0.0, 0.4, 0.4, 0.0, 0.4, 0.4, 0.4, 0.0]  # nothing reaches high
        self.assertFalse(hysteresis_decode(p, 0.5, 0.3).any())
        p = [0.0, 0.9, 0.4, 0.1, 0.1, 0.8, 0.4, 0.0]
        self.assertEqual(np.flatnonzero(hysteresis_decode(p, 0.5, 0.3, max_gap=0)).tolist(), [1, 2, 5, 6])
        self.assertEqual(np.flatnonzero(hysteresis_decode(p, 0.5, 0.3, max_gap=2)).tolist(), [1, 2, 3, 4, 5, 6])

    def test_hysteresis_min_length(self):
        p = [0.9, 0.0, 0.9, 0.9, 0.9]
        self.assertEqual(np.flatnonzero(hysteresis_decode(p, min_length=2)).tolist(), [2, 3, 4])

    def test_input_validation(self):
        for bad in ([0.5, 1.5], [float("nan")], [[0.5]]):
            with self.assertRaises(ValueError):
                hysteresis_decode(bad)
            with self.assertRaises(ValueError):
                viterbi_decode(bad)
        with self.assertRaises(ValueError):
            hysteresis_decode([0.5], high=0.2, low=0.4)

    def test_viterbi_matches_brute_force(self):
        rng = np.random.default_rng(0)
        for _ in range(20):
            p = rng.uniform(0.05, 0.95, 8)
            path = viterbi_decode(p, switch_penalty=1.5)
            emit = np.stack([np.log(1 - p), np.log(p)], axis=1) - np.log(0.5)

            def total(bits):
                return (sum(emit[i, b] for i, b in enumerate(bits))
                        - 1.5 * sum(bits[i] != bits[i - 1] for i in range(1, 8)))
            best = max(total([(m >> i) & 1 for i in range(8)]) for m in range(256))
            self.assertAlmostEqual(total([int(b) for b in path]), best, places=9)

    def test_viterbi_smooths_isolated_dip(self):
        p = [0.9] * 5 + [0.45] + [0.9] * 5
        self.assertTrue(viterbi_decode(p, switch_penalty=3.0).all())
        self.assertFalse(viterbi_decode(p, switch_penalty=0.0)[5])
        self.assertEqual(viterbi_decode([]).size, 0)


class EvaluationTests(unittest.TestCase):
    def test_metrics_and_improvement_over_threshold(self):
        truth = {"a": [False] + [True] * 6 + [False] * 3}
        probs = {"a": [0.1, 0.9, 0.9, 0.2, 0.2, 0.9, 0.9, 0.1, 0.1, 0.1]}
        raw = evaluate_decoding(truth, probs, lambda p: np.asarray(p) >= 0.5)
        smooth = evaluate_decoding(truth, probs, lambda p: hysteresis_decode(p, 0.5, 0.15, max_gap=2))
        self.assertEqual(raw["predicted_regions"], 2)
        self.assertEqual(raw["matched_regions"], 0)  # fragments each have IoU 2/6
        self.assertEqual(smooth["predicted_regions"], 1)
        self.assertEqual(smooth["region_recall"], 1.0)
        self.assertEqual(smooth["matched_start_mae"], 0)
        self.assertEqual(smooth["matched_end_mae"], 0)
        self.assertEqual(smooth["residue_overlap_iou"], 1.0)

    def test_empty_everything(self):
        out = evaluate_decoding({"a": [False] * 3}, {"a": [0.0] * 3}, hysteresis_decode)
        self.assertEqual(out["residue_overlap_iou"], 1.0)
        self.assertEqual(out["predicted_regions"], 0)


if __name__ == "__main__":
    unittest.main()
