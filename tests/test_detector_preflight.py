import json
import unittest
from io import BytesIO
from unittest.mock import patch

from scripts.preflight_detector_data import preflight


def row(source, sequence, labels, cluster, split):
    return {"source_id": source, "sequence": sequence, "labels": labels,
            "domain_tokens": [0] * len(sequence), "homology_cluster_id": cluster,
            "split": split, "label_tier": "curated_reference"}


class DetectorPreflightTests(unittest.TestCase):
    def setUp(self):
        train = [row("t1", "AGGGS", [0, 1, 1, 1, 0], "c1", "train"),
                 row("t2", "ACDEF", [0] * 5, "c2", "train")]
        valid = [row("v1", "SGGGS", [0, 1, 1, 1, 0], "c3", "validation"),
                 row("v2", "LMNPQ", [0] * 5, "c4", "validation")]
        self.sources = {"train": b"".join((json.dumps(r) + "\n").encode() for r in train),
                        "valid": b"".join((json.dumps(r) + "\n").encode() for r in valid)}

    def test_valid_reference_splits(self):
        with patch("scripts.preflight_detector_data._open",
                   side_effect=lambda source: BytesIO(self.sources[source])):
            report = preflight("train", "valid")
        self.assertEqual(report["status"], "reference_data_preflight_pass")
        self.assertEqual(report["train"]["records"], 2)

    def test_cluster_leak_is_rejected(self):
        rows = self.sources["valid"].decode().splitlines()
        first = json.loads(rows[0])
        first["homology_cluster_id"] = "c1"
        self.sources["valid"] = (json.dumps(first) + "\n" + rows[1] + "\n").encode()
        with patch("scripts.preflight_detector_data._open",
                   side_effect=lambda source: BytesIO(self.sources[source])):
            with self.assertRaisesRegex(ValueError, "split leakage"):
                preflight("train", "valid")

    def test_pseudo_label_is_rejected(self):
        rows = self.sources["train"].decode().splitlines()
        first = json.loads(rows[0])
        first["label_tier"] = "pseudo"
        self.sources["train"] = (json.dumps(first) + "\n" + rows[1] + "\n").encode()
        with patch("scripts.preflight_detector_data._open",
                   side_effect=lambda source: BytesIO(self.sources[source])):
            with self.assertRaisesRegex(ValueError, "not a reference label tier"):
                preflight("train", "valid")


if __name__ == "__main__":
    unittest.main()
