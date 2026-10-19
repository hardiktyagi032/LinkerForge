"""Streaming, metadata-only CSV provenance for large training runs.

Raw sequences and coordinates are deliberately excluded. The ledger is meant
to be archived with a run-level JSON manifest and model checkpoint.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
from pathlib import Path
from typing import Mapping


FIELDS = (
    "record_id", "source_database", "source_release", "source_accession",
    "sequence_sha256", "sequence_length", "domain_a_id", "domain_a_start",
    "domain_a_end", "domain_b_id", "domain_b_start", "domain_b_end",
    "predicted_linker_start", "predicted_linker_end", "predicted_class",
    "prediction_confidence", "label_tier", "homology_cluster_id", "split",
    "classifier_checkpoint_sha256", "config_sha256",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class ProvenanceLedger:
    def __init__(self, directory: Path, run_metadata: Mapping[str, object],
                 max_records_per_shard: int = 100_000) -> None:
        if max_records_per_shard < 1:
            raise ValueError("max_records_per_shard must be positive")
        self.directory = directory
        self.metadata = dict(run_metadata)
        self.limit = max_records_per_shard
        self.total = 0
        self.shards: list[dict[str, object]] = []
        self._handle = None
        self._writer = None
        self._count_in_shard = 0
        self._path: Path | None = None

    def __enter__(self) -> "ProvenanceLedger":
        self.directory.mkdir(parents=True, exist_ok=True)
        if list(self.directory.iterdir()):
            raise FileExistsError("Ledger directory must be empty to prevent overwrite")
        return self

    def _open_shard(self) -> None:
        self._path = self.directory / f"used-records-{len(self.shards):05d}.csv.gz"
        self._handle = gzip.open(self._path, "wt", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._handle, fieldnames=FIELDS, lineterminator="\n")
        self._writer.writeheader()
        self._count_in_shard = 0

    def _close_shard(self) -> None:
        if self._handle is None:
            return
        self._handle.close()
        assert self._path is not None
        self.shards.append({"file": self._path.name, "records": self._count_in_shard,
                            "sha256": file_sha256(self._path)})
        self._handle = None
        self._writer = None
        self._path = None

    def append(self, record: Mapping[str, object]) -> None:
        missing = set(FIELDS) - set(record)
        extra = set(record) - set(FIELDS)
        if missing or extra:
            raise ValueError(f"Ledger columns mismatch: missing={sorted(missing)}, extra={sorted(extra)}")
        if record["split"] not in ("train", "validation", "blind"):
            raise ValueError("Invalid split")
        if record["label_tier"] not in ("experimental_gold", "curated_reference", "pseudo", "unlabeled"):
            raise ValueError("Invalid label tier")
        if not record["homology_cluster_id"]:
            raise ValueError("Homology cluster ID required")
        if self._handle is None:
            self._open_shard()
        assert self._writer is not None
        self._writer.writerow(record)
        self._count_in_shard += 1
        self.total += 1
        if self._count_in_shard >= self.limit:
            self._close_shard()

    def __exit__(self, exc_type, exc, traceback) -> None:
        self._close_shard()
        status = "complete" if exc_type is None else "interrupted"
        manifest = {"schema_version": "1.0.0", "status": status,
                    "raw_sequences_stored": False, "record_count": self.total,
                    "shards": self.shards, "run": self.metadata}
        path = self.directory / "manifest.json"
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
