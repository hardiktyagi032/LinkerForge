"""Validate reference JSONL streams before a CUDA linker-detector run.

This is a small-reference-set gate, not a million-row dataset cache. It reads
streams once, retains only cluster IDs and hashes, and writes aggregate results.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

ALLOWED_TIERS = {"experimental_gold", "curated_reference"}
AA = set("ACDEFGHIKLMNPQRSTVWYX")


def _open(source: str):
    if source.startswith("https://"):
        handle = urlopen(Request(source, headers={"User-Agent": "LinkerForge-preflight/0.1"}), timeout=60)
    else:
        handle = open(source, "rb")
    return handle


def scan(source: str, expected_split: str) -> tuple[dict, set[str], set[str]]:
    clusters: set[str] = set()
    sequence_hashes: set[str] = set()
    counts = {"records": 0, "positive_proteins": 0, "negative_proteins": 0,
              "idl_residues": 0, "ddl_residues": 0, "tiers": {}}
    with _open(source) as handle:
        stream = gzip.GzipFile(fileobj=handle) if source.endswith(".gz") else handle
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{source}:{line_number}: invalid JSON") from exc
            required = ("source_id", "sequence", "labels", "domain_tokens",
                        "homology_cluster_id", "split", "label_tier")
            missing = [key for key in required if key not in row]
            if missing:
                raise ValueError(f"{source}:{line_number}: missing {missing}")
            sequence = row["sequence"].upper()
            labels, domains = row["labels"], row["domain_tokens"]
            if not sequence or any(aa not in AA for aa in sequence):
                raise ValueError(f"{source}:{line_number}: invalid amino-acid sequence")
            if len(sequence) != len(labels) or len(sequence) != len(domains):
                raise ValueError(f"{source}:{line_number}: misaligned residue arrays")
            if any(label not in (0, 1, 2) for label in labels):
                raise ValueError(f"{source}:{line_number}: invalid residue label")
            if any(token not in (0, 1, 2, 3) for token in domains):
                raise ValueError(f"{source}:{line_number}: invalid domain token")
            if row["split"] != expected_split or not row["homology_cluster_id"]:
                raise ValueError(f"{source}:{line_number}: split or cluster invalid")
            tier = row["label_tier"]
            if tier not in ALLOWED_TIERS:
                raise ValueError(f"{source}:{line_number}: {tier!r} is not a reference label tier")
            digest = hashlib.sha256(sequence.encode()).hexdigest()
            if digest in sequence_hashes:
                raise ValueError(f"{source}:{line_number}: duplicate sequence")
            sequence_hashes.add(digest)
            clusters.add(row["homology_cluster_id"])
            counts["records"] += 1
            counts["positive_proteins" if any(labels) else "negative_proteins"] += 1
            counts["idl_residues"] += labels.count(1)
            counts["ddl_residues"] += labels.count(2)
            counts["tiers"][tier] = counts["tiers"].get(tier, 0) + 1
    if not counts["records"]:
        raise ValueError(f"{source}: no records")
    return counts, clusters, sequence_hashes


def preflight(train: str, validation: str) -> dict:
    train_counts, train_clusters, train_sequences = scan(train, "train")
    valid_counts, valid_clusters, valid_sequences = scan(validation, "validation")
    overlap_clusters = train_clusters & valid_clusters
    overlap_sequences = train_sequences & valid_sequences
    if overlap_clusters or overlap_sequences:
        raise ValueError(f"split leakage: {len(overlap_clusters)} clusters, "
                         f"{len(overlap_sequences)} exact sequences shared")
    if not train_counts["positive_proteins"] or not train_counts["negative_proteins"]:
        raise ValueError("training needs both linker-present and explicitly linker-absent proteins")
    if not valid_counts["positive_proteins"] or not valid_counts["negative_proteins"]:
        raise ValueError("validation needs both linker-present and explicitly linker-absent proteins")
    return {"status": "reference_data_preflight_pass", "train": train_counts,
            "validation": valid_counts, "train_clusters": len(train_clusters),
            "validation_clusters": len(valid_clusters),
            "warning": "Cluster IDs are trusted metadata here; create and audit them independently before using this gate."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", required=True)
    parser.add_argument("--validation", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = preflight(args.train, args.validation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
