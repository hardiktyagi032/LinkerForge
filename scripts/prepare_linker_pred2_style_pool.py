"""Reproducible DLD/DisProt preparation inspired by LINKER-Pred2's sources.

This is NOT the authors' unreleased row-level training split. It deliberately
keeps structural DLD, masked published DFL, and positive-only DisProt separate.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "dld_train": ROOT / "data/processed/dld_reference/dld_train.jsonl.gz",
    "dld_validation": ROOT / "data/processed/dld_reference/dld_validation.jsonl.gz",
    "dld_blind": ROOT / "data/processed/dld_reference/dld_blind.jsonl.gz",
    "tr166": ROOT / "data/processed/published_dfl_splits/tr166.jsonl",
    "te82": ROOT / "data/processed/published_dfl_splits/te82.jsonl",
    "te64": ROOT / "data/processed/published_dfl_splits/te64.jsonl",
    "disprot": ROOT / "data/processed/disprot_2026_06_flexible_linkers.jsonl",
    "caid3": ROOT / "artifacts/caid3-linker.fasta",
    "disprot_dld_homology_screen": ROOT / "reports/disprot_dld_homology_screen_2026-10-11.json",
}
CONFIG = {
    "schema_version": "1.0.0",
    "label_policy": {
        "published_dfl": "preserve 1=DFL, 0=published negative, x=unknown",
        "dld": "separate structural IDL/DDL task; converted 0 is not CAID DFL negative",
        "disprot": "only explicitly annotated flexible-linker spans are 1; all other residues unknown",
    },
    "split_policy": "retain source splits; quarantine cross-source exact sequence and protected CAID3 overlap",
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rows(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def fasta_sequences(path: Path) -> tuple[set[str], set[str]]:
    ids, sequences = set(), set()
    pieces = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(">"):
            if pieces:
                sequences.add("".join(pieces).upper())
                pieces = []
            ids.add(line[1:].split()[0])
        else:
            pieces.append(line.strip())
    if pieces:
        sequences.add("".join(pieces).upper())
    return ids, sequences


def build(source_paths: dict[str, Path], output_dir: Path) -> dict:
    missing = [str(p) for p in source_paths.values() if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing inputs: {missing}")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    config_hash = hashlib.sha256(json.dumps(CONFIG, sort_keys=True).encode()).hexdigest()
    protected_ids, protected_sequences = fasta_sequences(source_paths["caid3"])
    homology_screen = json.loads(source_paths["disprot_dld_homology_screen"].read_text(encoding="utf-8"))
    flagged_disprot_ids = {hit["disprot_id"] for hit in homology_screen["hits"]}
    source_hashes = {k: digest(p) for k, p in source_paths.items()}
    output_dir.mkdir(parents=True, exist_ok=True)

    source_rows = {}
    for name in ("dld_train", "dld_validation", "dld_blind", "tr166", "te82", "te64"):
        source_rows[name] = list(rows(source_paths[name]))
    grouped = defaultdict(list)
    for region in rows(source_paths["disprot"]):
        grouped[region["disprot_id"]].append(region)

    protected_sequences.update(r["sequence"].upper() for name in
                               ("dld_validation", "dld_blind", "te82", "te64")
                               for r in source_rows[name])
    protected_ids.update(r["protein_id"] for name in ("te82", "te64") for r in source_rows[name])
    counts = Counter()
    outputs = {name: [] for name in ("published_dfl_train", "dld_auxiliary_candidate", "disprot_positive_only", "quarantine")}
    training_sequences = set()

    def provenance(name: str, original: dict) -> dict:
        return {"source_id": original, "input_sha256": source_hashes[name],
                "pipeline_commit": commit, "config_hash": config_hash,
                "software": {"python": sys.version.split()[0], "preparer": "1.0.0"}}

    tr166_sequence_counts = Counter(row["sequence"].upper() for row in source_rows["tr166"])
    for row in source_rows["tr166"]:
        sequence, labels = row["sequence"].upper(), row["labels"]
        if len(sequence) != len(labels) or set(labels) - set("01x"):
            raise ValueError(f"Bad TR166 record {row['protein_id']}")
        dest = "quarantine" if sequence in protected_sequences or row["protein_id"] in protected_ids or tr166_sequence_counts[sequence] > 1 else "published_dfl_train"
        if dest != "quarantine":
            training_sequences.add(sequence)
        outputs[dest].append({"schema_version": "1.0.0", "source": "TransDFL_TR166",
                              "protein_id": row["protein_id"], "sequence": sequence,
                              "labels": labels, "task": "DFL", "training_role": dest,
                              "reason": "protected_exact_or_duplicate_sequence" if dest == "quarantine" else None,
                              "provenance": provenance("tr166", row["protein_id"])})

    for row in source_rows["dld_train"]:
        sequence = row["sequence"].upper()
        labels = row["labels"]
        if len(sequence) != len(labels) or set(labels) - {0, 1, 2}:
            raise ValueError(f"Bad DLD record {row['source_id']}")
        dest = "quarantine" if sequence in protected_sequences or sequence in training_sequences else "dld_auxiliary_candidate"
        if dest != "quarantine":
            training_sequences.add(sequence)
        outputs[dest].append({"schema_version": "1.0.0", "source": "DLD",
                              "protein_id": row["source_id"], "sequence": sequence,
                              "labels": "".join(str(value) if value else "x" for value in labels), "task": "structural_IDL_DDL",
                              "training_role": dest,
                              "reason": "protected_or_cross_source_exact_overlap" if dest == "quarantine" else None,
                              "provenance": provenance("dld_train", row["source_id"])})

    for protein_id, regions in sorted(grouped.items()):
        sequence = regions[0]["sequence"].upper()
        if any(r["sequence"].upper() != sequence for r in regions):
            raise ValueError(f"Conflicting DisProt sequence: {protein_id}")
        labels = ["x"] * len(sequence)
        for region in regions:
            start, end = region["linker"]["start"], region["linker"]["end"]
            if not (1 <= start <= end <= len(sequence)) or sequence[start - 1:end] != region["linker"]["sequence"].upper():
                raise ValueError(f"Invalid DisProt span: {region['region_id']}")
            labels[start - 1:end] = ["1"] * (end - start + 1)
        dest = "quarantine" if protein_id in protected_ids or protein_id in flagged_disprot_ids or sequence in protected_sequences or sequence in training_sequences else "disprot_positive_only"
        outputs[dest].append({"schema_version": "1.0.0", "source": "DisProt_2026_06",
                              "protein_id": protein_id, "sequence": sequence,
                              "labels": "".join(labels), "task": "DFL_positive_unlabeled",
                              "training_role": dest, "reason": "protected_exact_or_candidate_DLD_homology" if dest == "quarantine" else None,
                              "provenance": provenance("disprot", [r["region_id"] for r in regions])})

    files = {}
    for name, records in outputs.items():
        target = output_dir / f"{name}.jsonl"
        with target.open("w", encoding="utf-8", newline="\n") as f:
            for record in records:
                f.write(json.dumps(record, sort_keys=True) + "\n")
        files[name] = {"records": len(records), "sha256": digest(target),
                       "positive_residues": sum(r["labels"].count("1") +
                                                (r["labels"].count("2") if r["task"] == "structural_IDL_DDL" else 0)
                                                for r in records)}
        counts[name] = len(records)
    manifest = {"schema_version": "1.0.0", "status": "prepared_not_linker_pred2_exact_split_not_training_cleared",
                "config": CONFIG, "config_hash": config_hash, "pipeline_commit": commit,
                "source_sha256": source_hashes, "files": files,
                "protected_sets": ["CAID3", "DLD validation/blind", "TE82", "TE64", "candidate DisProt-DLD homology hits"],
                "limitations": ["Only exact overlap and the existing candidate DisProt-DLD screen are quarantined; a homology/family audit remains required.",
                                "DisProt non-positive positions are unknown; they are not negatives.",
                                "DLD converted zero includes raw source code 0 and other classes; all zeros are masked until raw classes can be recovered.",
                                "This does not reconstruct LINKER-Pred2's unreleased row-level split."]}
    target = output_dir / "manifest.json"
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/processed/linker_pred2_style_pool_v1")
    args = parser.parse_args()
    result = build(SOURCES, args.output_dir)
    print(json.dumps({name: value["records"] for name, value in result["files"].items()}, sort_keys=True))


if __name__ == "__main__":
    main()
