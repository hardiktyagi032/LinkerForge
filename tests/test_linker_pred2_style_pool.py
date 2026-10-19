"""Integrity checks for the source-aware LINKER-Pred2-style preparation."""

import gzip
import json
from pathlib import Path
import tempfile
import unittest

from scripts.prepare_linker_pred2_style_pool import ROOT, SOURCES, build


class PoolPreparationTests(unittest.TestCase):
    def test_source_separation_and_masks(self):
        if not all(path.is_file() for path in SOURCES.values()):
            self.skipTest("Local source snapshots are unavailable")
        with tempfile.TemporaryDirectory() as folder:
            manifest = build(SOURCES, Path(folder))
            self.assertEqual(manifest["status"], "prepared_not_linker_pred2_exact_split_not_training_cleared")
            records = {}
            for name in manifest["files"]:
                records[name] = [json.loads(line) for line in (Path(folder) / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()]
                self.assertEqual(len(records[name]), manifest["files"][name]["records"])
                for row in records[name]:
                    self.assertEqual(len(row["sequence"]), len(row["labels"]))
                    self.assertEqual(row["training_role"], name)
            self.assertTrue(records["published_dfl_train"])
            self.assertTrue(records["dld_auxiliary_candidate"])
            self.assertTrue(records["disprot_positive_only"])
            self.assertTrue(all(set(row["labels"]) <= {"1", "x"} for row in records["disprot_positive_only"]))
            self.assertTrue(all(row["task"] == "structural_IDL_DDL" for row in records["dld_auxiliary_candidate"]))
            self.assertTrue(all(set(row["labels"]) <= {"1", "2", "x"} for row in records["dld_auxiliary_candidate"]))
            train_sequences = [row["sequence"] for name in ("published_dfl_train", "dld_auxiliary_candidate") for row in records[name]]
            self.assertEqual(len(train_sequences), len(set(train_sequences)))
            with gzip.open(SOURCES["dld_blind"], "rt", encoding="utf-8") as stream:
                blind = {json.loads(line)["sequence"] for line in stream}
            self.assertFalse(set(train_sequences) & blind)


if __name__ == "__main__":
    unittest.main()
