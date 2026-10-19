"""Ensure domain-gap-only candidates never enter the annotated catalog."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_annotated_only_linker_catalog.py"
spec = spec_from_file_location("annotated_only_catalog", SCRIPT)
module = module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
CONFIG = json.loads((ROOT / "configs/annotated_only_linker_catalog_v1.json").read_text())
KEYS = set(CONFIG["qualifying_source_keys"])
PROVENANCE = {"input_sha256": "a" * 64, "config_sha256": "b" * 64,
              "pipeline_commit": "c" * 40, "pipeline_sha256": "d" * 64}


class AnnotatedFilterTests(unittest.TestCase):
    def test_inferred_gap_alone_is_excluded(self):
        row = {"sequence": "GGGGS", "sources": {"uniprot_reviewed": {"accession": "P12345"}}}
        self.assertIsNone(module.annotated_record(row, KEYS, CONFIG, PROVENANCE))

    def test_explicit_annotation_qualifies_without_gap_source(self):
        row = {"sequence": "GGGGS", "sources": {
            "uniprot_reviewed": {"accession": "P12345"},
            "uniprot_explicit_linker_region": {"accession": "Q12345", "note": "Linker"}}}
        record = module.annotated_record(row, KEYS, CONFIG, PROVENANCE)
        self.assertEqual(record["qualifying_source_keys"],
                         ["uniprot_explicit_linker_region"])
        self.assertNotIn("uniprot_reviewed", record["qualifying_sources"])

    def test_protected_and_quarantined_are_not_training_ready(self):
        for raw_status, expected in [("protected_blind", "protected_benchmark"),
                                     ("quarantine_pending_overlap_audit", "quarantined")]:
            row = {"sequence": "GGGGS", "sources": {
                "existing_catalog": {"usage_statuses": [raw_status]}}}
            record = module.annotated_record(row, KEYS, CONFIG, PROVENANCE)
            self.assertEqual(record["usage_status"], expected)


if __name__ == "__main__":
    unittest.main()
