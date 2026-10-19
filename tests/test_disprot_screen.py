import unittest

from scripts.screen_disprot_linker_context import screen_entry


class DisProtScreenTests(unittest.TestCase):
    def test_supported_domain_gap_is_review_candidate_only(self):
        entry = {
            "disprot_id": "DP_TEST", "acc": "P_TEST", "sequence": "A" * 100,
            "features": {"pfam": [
                {"id": "PF_A", "start": 1, "end": 40},
                {"id": "PF_B", "start": 51, "end": 100},
            ]},
            "regions": [{
                "region_id": "DP_TESTr001", "disprot_namespace": "Structural state",
                "term_name": "disorder", "start": 42, "end": 49,
                "ec_id": "ECO:TEST", "reference_id": "PMID:TEST",
            }],
        }
        rows = screen_entry(entry)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["gap"]["length"], 10)
        self.assertEqual(rows[0]["disorder_evidence"][0]["overlap_residues"], 8)
        self.assertEqual(rows[0]["review_status"], "pending")
        self.assertNotIn("natural_linker", rows[0]["record_type"])

    def test_non_disorder_region_does_not_create_candidate(self):
        entry = {
            "sequence": "A" * 100,
            "features": {"pfam": [
                {"id": "PF_A", "start": 1, "end": 40},
                {"id": "PF_B", "start": 51, "end": 100},
            ]},
            "regions": [{"disprot_namespace": "Function", "term_name": "disorder", "start": 41, "end": 50}],
        }
        self.assertEqual(screen_entry(entry), [])


if __name__ == "__main__":
    unittest.main()
