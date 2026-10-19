"""Fail-closed checks for the CAID3 sequence blacklist."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_caid3_protected_dfl_splits import REFERENCE, match, reference_sequences
from preflight_caid3_protected_training import verify
from build_caid3_protected_dfl_splits import OUTPUT


class Caid3BlacklistTests(unittest.TestCase):
    def test_exact_identifier_is_excluded(self):
        identifier, sequence = reference_sequences(REFERENCE)[0]
        self.assertEqual(match({"protein_id": identifier, "sequence": sequence},
                               reference_sequences(REFERENCE))["reason"],
                         "exact_id_sequence_or_containment")

    def test_exact_sequence_with_new_identifier_is_excluded(self):
        _, sequence = reference_sequences(REFERENCE)[0]
        self.assertIsNotNone(match({"protein_id": "synthetic_test_id", "sequence": sequence},
                                   reference_sequences(REFERENCE)))

    def test_old_versioned_split_fails_prospective_holdout_gate(self):
        with self.assertRaisesRegex(ValueError, "Prospective DP94 benchmark sequence overlap"):
            verify(OUTPUT / "manifest.json")


if __name__ == "__main__":
    unittest.main()
