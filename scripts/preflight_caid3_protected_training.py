"""Fail closed before CAID3-protected DFL training; never reads CAID3 labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_caid3_protected_dfl_splits import OUTPUT, REFERENCE, ROOT, RULE, match, reference_sequences, sha


PROSPECTIVE = ROOT / "data/processed/prospective_dfl_holdout_dp94_v1"


def prospective_references() -> list[tuple[str, str]]:
    """Read benchmark sequences only; never read its labels during training."""
    manifest_path = PROSPECTIVE / "manifest.json"
    fasta_path = PROSPECTIVE / "sequences.fasta"
    if not manifest_path.exists() or not fasta_path.exists():
        raise ValueError("Prospective benchmark sequence firewall is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "candidate_not_certified_independent":
        raise ValueError("Unreviewed prospective benchmark manifest state")
    # The manifest hashes the canonical UTF-8 text with LF line endings; on
    # Windows the saved file can have CRLF bytes.
    import hashlib
    canonical = fasta_path.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != manifest["sequence_fasta_sha256"]:
        raise ValueError("Prospective benchmark sequence hash changed")
    lines = fasta_path.read_text(encoding="utf-8").splitlines()
    if len(lines) % 2:
        raise ValueError("Malformed prospective benchmark FASTA")
    references = []
    for at in range(0, len(lines), 2):
        if not lines[at].startswith(">") or not lines[at + 1]:
            raise ValueError("Malformed prospective benchmark FASTA record")
        references.append((lines[at][1:].split()[0], lines[at + 1].upper()))
    if len(references) != manifest["holdout_proteins"] or [r[0] for r in references] != manifest["holdout_ids"]:
        raise ValueError("Prospective benchmark IDs/count changed")
    return references


def verify(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["status"] != "sequence_screened_not_full_homology_certification":
        raise ValueError("Unexpected data status")
    if manifest["rule"] != RULE or manifest["reference_sha256"] != sha(REFERENCE):
        raise ValueError("Blacklist rule or CAID3 reference changed")
    refs = reference_sequences(REFERENCE)
    future_refs = prospective_references()
    counts = {}
    ids = {}
    sequences = {}
    for name in ("train", "development", "auxiliary"):
        info = manifest["files"][name]
        path = ROOT / info["path"]
        if sha(path) != info["sha256"]:
            raise ValueError(f"Data hash changed: {name}")
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        if len(rows) != info["retained_proteins"] or not rows:
            raise ValueError(f"Unexpected row count: {name}")
        for row in rows:
            if len(row["sequence"]) != len(row["labels"]):
                raise ValueError(f"Sequence/label mismatch: {name} {row['protein_id']}")
            if set(row["labels"]) - {"0", "1", "x"}:
                raise ValueError(f"Unknown label code: {name} {row['protein_id']}")
            hit = match(row, refs)
            if hit:
                raise ValueError(f"CAID3 blacklist violation in {name}: {hit}")
            future_hit = match(row, future_refs)
            if future_hit:
                future_hit["benchmark_id"] = future_hit.pop("caid3_id")
                raise ValueError(f"Prospective DP94 benchmark sequence overlap in {name}: {future_hit}")
        ids[name] = {row["protein_id"] for row in rows}
        sequences[name] = {row["sequence"].upper() for row in rows}
        counts[name] = len(rows)
    if ids["train"] & ids["development"] or sequences["train"] & sequences["development"]:
        raise ValueError("Exact train/development overlap")
    blacklist = manifest_path.parent / "blacklist.json"
    if sha(blacklist) != manifest["blacklist_sha256"]:
        raise ValueError("Blacklist file hash changed")
    return {"status": "pass_under_declared_sequence_screen", "reference_sha256": sha(REFERENCE),
            "prospective_reference_sha256": sha(PROSPECTIVE / "sequences.fasta"),
            "counts": counts, "limitations": manifest["limitations"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=OUTPUT / "manifest.json")
    args = parser.parse_args()
    print(json.dumps(verify(args.manifest), indent=2))


if __name__ == "__main__":
    main()
