"""Small synthetic fixtures only; no network or structural validation."""

import unittest

from linkerforge.data import (
    AdjudicationConfig,
    ChainSequence,
    DomainAssignment,
    Provenance,
    ResidueMap,
    SourceMetadata,
    extract_natural_example,
)


def fixture_chain(**overrides):
    # 10 aa domain, 5 aa gap, 10 aa domain. Author numbering starts at 101.
    sequence = "A" * 10 + "GSGSG" + "C" * 10
    residues = tuple(
        ResidueMap(i, i + 100, "", i, True) for i in range(1, 26)
    )
    values = {"sequence": sequence, "residues": residues}
    values.update(overrides)
    return ChainSequence(**values)


def fixture_args(chain=None, domains=None, source=None):
    return (
        chain or fixture_chain(),
        domains or (DomainAssignment(1, 10, ("1.10.10.10",)), DomainAssignment(16, 25, ("2.40.50.140",))),
        source or SourceMetadata("1ABC", "A", "P00000", "2026-10-08"),
        Provenance("abc123", "sha256:fixture", {"linkerforge": "0.1.0"}),
    )


class NaturalLinkerAdjudicationTests(unittest.TestCase):
    def test_valid_fixture_uses_canonical_not_author_numbering(self):
        result = extract_natural_example(*fixture_args())
        self.assertTrue(result.accepted)
        self.assertEqual(result.reason_codes, ())
        record = result.record
        self.assertEqual(record["source_record_type"], "natural_observation")
        self.assertEqual(record["linker"]["sequence"], "GSGSG")
        self.assertEqual((record["linker"]["start"], record["linker"]["end"]), (11, 15))
        self.assertEqual(record["linker"]["evidence_quality"], "uncertain")
        self.assertEqual(record["residue_mapping"][1]["author_number"], 111)

    def test_overlap_and_too_short_are_rejected(self):
        result = extract_natural_example(*fixture_args(domains=(DomainAssignment(1, 12), DomainAssignment(12, 25))))
        self.assertFalse(result.accepted)
        self.assertIn("OVERLAPPING_OR_REVERSED_DOMAINS", result.reason_codes)
        self.assertIsNone(result.record)

    def test_unresolved_junction_is_rejected(self):
        chain = fixture_chain()
        residues = list(chain.residues)
        residues[10] = ResidueMap(11, 111, "", 11, False)
        result = extract_natural_example(*fixture_args(chain=fixture_chain(residues=tuple(residues))))
        self.assertIn("UNRESOLVED_JUNCTION", result.reason_codes)

    def test_missing_numbering_does_not_get_silently_guessed(self):
        chain = fixture_chain()
        residues = list(chain.residues)
        residues[11] = ResidueMap(12, None, "", None, False)
        result = extract_natural_example(*fixture_args(chain=fixture_chain(residues=tuple(residues))))
        self.assertIn("UNMAPPED_JUNCTION_NUMBERING", result.reason_codes)

    def test_nonexperimental_and_engineered_excluded_from_primary_tier(self):
        result = extract_natural_example(*fixture_args(chain=fixture_chain(engineered=True), source=SourceMetadata("1ABC", "A", None, "2026-10-08", "predicted")))
        self.assertIn("ENGINEERED_CONSTRUCT", result.reason_codes)
        self.assertIn("NONEXPERIMENTAL_STRUCTURE", result.reason_codes)

    def test_quality_must_not_be_self_declared_high_without_review(self):
        result = extract_natural_example(*fixture_args(), config=AdjudicationConfig(evidence_quality="rejected"))
        self.assertIn("INVALID_EVIDENCE_QUALITY", result.reason_codes)


if __name__ == "__main__":
    unittest.main()
