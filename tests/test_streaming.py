"""Offline tests for bounded cloud-data loading and stable split routing."""

import unittest
import csv
import gzip
import json
import shutil
from pathlib import Path
from uuid import uuid4

from linkerforge.data.streaming import partition_for_cluster, prefetch_one_batch
from linkerforge.data.provenance_ledger import FIELDS, ProvenanceLedger


class StreamingTests(unittest.TestCase):
    def test_prefetch_preserves_batch_order(self):
        self.assertEqual(list(prefetch_one_batch(([n] for n in range(5)))),
                         [[0], [1], [2], [3], [4]])

    def test_cluster_split_is_stable_and_seeded(self):
        first = partition_for_cluster("UniRef50:P12345", seed="frozen-seed")
        self.assertEqual(first, partition_for_cluster("UniRef50:P12345", seed="frozen-seed"))
        self.assertIn(first, {"train", "validation", "blind"})

    def test_requires_real_cluster_identifier(self):
        with self.assertRaises(ValueError):
            partition_for_cluster("")
        with self.assertRaises(ValueError):
            partition_for_cluster("cluster", train_fraction=0.99, validation_fraction=0.05)

    def test_metadata_only_ledger_is_sharded_and_checksummed(self):
        root = (Path.cwd() / "data" / "processed").resolve()
        root.mkdir(parents=True, exist_ok=True)
        directory = root / f"ledger-test-{uuid4().hex}"
        try:
            base = {name: "x" for name in FIELDS}
            base.update(split="train", label_tier="pseudo",
                        homology_cluster_id="UniRef50:example")
            with ProvenanceLedger(directory, {"source_release": "test-release"},
                                  max_records_per_shard=2) as ledger:
                for index in range(3):
                    ledger.append(dict(base, record_id=str(index)))
            manifest = json.loads((directory / "manifest.json").read_text())
            self.assertEqual(manifest["record_count"], 3)
            self.assertEqual(len(manifest["shards"]), 2)
            self.assertFalse(manifest["raw_sequences_stored"])
            with gzip.open(directory / manifest["shards"][0]["file"], "rt") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["record_id"] for row in rows], ["0", "1"])
        finally:
            if directory.exists():
                if directory.resolve().parent != root:
                    raise RuntimeError("Refusing to clean an unexpected ledger test path")
                shutil.rmtree(directory)


if __name__ == "__main__":
    unittest.main()
