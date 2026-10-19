import unittest

from scripts.extract_disprot_flexible_linkers import extract
from scripts.audit_disprot_dld_overlap import audit


class DisProtFlexibleLinkerTests(unittest.TestCase):
    def test_only_explicit_linker_term_is_extracted(self):
        entry = {"disprot_id": "DP00001", "acc": "P00001", "sequence": "AAGGSSAA",
                 "regions": [
                     {"region_id": "DP00001r001", "term_id": "IDPO:0000033", "term_name": "flexible linker",
                      "start": 3, "end": 6},
                     {"region_id": "DP00001r002", "term_id": "IDPO:0000002", "start": 1, "end": 8},
                 ]}
        rows = extract([entry], {"evidence_quality": "test"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["linker"]["sequence"], "GGSS")
        self.assertEqual(rows[0]["training_eligibility"], "holdout_pending_overlap_audit")

    def test_exact_overlap_is_not_independence_claim(self):
        disprot = [{"region_id": "DP00001r001", "sequence": "AAAGGSSAAA"}]
        dld = [{"source_id": "pdbA", "split": "train", "sequence": "AAAGGSSAAA"}]
        report = audit(disprot, dld)
        self.assertEqual(report["overlap_counts"]["identical_full_sequence"], 1)
        self.assertIn("not_independence_certification", report["status"])


if __name__ == "__main__":
    unittest.main()
