"""Convert the official DLD chain archive to temporary detector JSONL streams.

This uses the source-provided homology clusters/folds, removes every repeated
sequence (including conflicting annotations), and keeps fold 5 blind. Domain
tokens are deliberately zero: deriving them from DLD residue labels would leak
the target into the input. Independent domain maps are future work.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

MEMBER = "dld_dataset_raw_data/domainLinker_chain.json"
SOURCE_URL = "https://dld.chemeslab.org/"
LABEL_MAP = {"1": 1, "2": 2}
VALID_REFERENCE = set("012345")
VALID_AA = set("ACDEFGHIKLMNPQRSTVWYX")
SPLITS = {1: "train", 2: "train", 3: "train", 4: "validation", 5: "blind"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def convert(archive: Path, output_dir: Path) -> dict:
    with zipfile.ZipFile(archive) as bundle:
        if MEMBER not in bundle.namelist():
            raise ValueError(f"DLD member missing: {MEMBER}")
        rows = json.loads(bundle.read(MEMBER))
    if not isinstance(rows, list) or not rows:
        raise ValueError("DLD chain member must be a nonempty JSON array")

    archive_hash = sha256(archive)
    config = {"source_member": MEMBER, "split_folds": SPLITS,
              "drop_all_duplicate_sequences": True, "domain_tokens": "zero_unavailable"}
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    versions = {"python": sys.version.split()[0], "converter": "1"}

    by_sequence = defaultdict(list)
    clusters_to_fold = defaultdict(set)
    excluded_unsupported_residues = 0
    for row in rows:
        sequence = row["sequence"].upper()
        reference = row["reference"]
        if not sequence or len(sequence) != len(reference):
            raise ValueError(f"Invalid DLD sequence/alignment: {row.get('id')}")
        if set(sequence) - VALID_AA:
            excluded_unsupported_residues += 1
            continue
        if set(reference) - VALID_REFERENCE:
            raise ValueError(f"Unknown DLD reference code: {row.get('id')}")
        fold = int(row["fold"])
        if fold not in SPLITS or not row.get("clstr_id"):
            raise ValueError(f"Missing DLD fold/cluster: {row.get('id')}")
        clusters_to_fold[row["clstr_id"]].add(fold)
        by_sequence[sequence].append(row)
    crossed = {key: folds for key, folds in clusters_to_fold.items() if len(folds) != 1}
    if crossed:
        raise ValueError(f"Source homology clusters cross folds: {len(crossed)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {split: output_dir / f"dld_{split}.jsonl.gz"
             for split in ("train", "validation", "blind")}
    counts = {split: Counter() for split in paths}
    handles = {split: gzip.open(path, "wt", encoding="utf-8", newline="\n")
               for split, path in paths.items()}
    try:
        for sequence, matches in by_sequence.items():
            if len(matches) != 1:
                continue
            row = matches[0]
            split = SPLITS[int(row["fold"])]
            labels = [LABEL_MAP.get(code, 0) for code in row["reference"]]
            record = {
                "schema_version": "0.1.0", "source_id": row["id"],
                "sequence": sequence, "labels": labels,
                "domain_tokens": [0] * len(sequence),
                "homology_cluster_id": row["clstr_id"], "split": split,
                "label_tier": "curated_reference", "evidence_quality": "curated_dataset",
                "observation_type": "natural_reference_annotation",
                "provenance": {"source_url": SOURCE_URL, "source_member": MEMBER,
                               "source_archive_sha256": archive_hash,
                               "source_fold": int(row["fold"]),
                               "pipeline_commit": commit, "config_hash": config_hash,
                               "software": versions},
            }
            handles[split].write(json.dumps(record, separators=(",", ":")) + "\n")
            counts[split]["records"] += 1
            counts[split]["positive" if any(labels) else "negative"] += 1
    finally:
        for handle in handles.values():
            handle.close()

    report = {
        "status": "converted_not_trained", "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": SOURCE_URL, "source_member": MEMBER,
        "source_archive_sha256": archive_hash, "source_records": len(rows),
        "excluded_unsupported_residue_records": excluded_unsupported_residues,
        "excluded_duplicate_sequence_records": sum(len(group) for group in by_sequence.values() if len(group) > 1),
        "source_cluster_fold_overlap": len(crossed), "config_hash": config_hash,
        "pipeline_commit": commit, "software": versions,
        "domain_tokens": "all_zero_to_prevent_label_leakage",
        "splits": {split: {**dict(counts[split]), "sha256": sha256(path), "path": str(path)}
                   for split, path in paths.items()},
        "limitations": ["Source DLD cluster IDs and folds are trusted; independent homology audit remains required.",
                        "All domain tokens are zero until independent domain boundaries are available.",
                        "Blind fold 5 is prepared but must not be used for tuning."],
    }
    (output_dir / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(convert(args.archive, args.output_dir)), flush=True)


if __name__ == "__main__":
    main()
