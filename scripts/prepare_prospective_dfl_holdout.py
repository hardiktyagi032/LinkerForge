"""Seal a sequence-only candidate DFL holdout and audit local training overlap.

The source's label lines are neither parsed nor written. A later evaluator must
re-download the exact source digest only after model/threshold selection freezes.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

import parasail


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/processed/prospective_dfl_holdout_dp94_v1"
SOURCE_URL = "https://raw.githubusercontent.com/YihePang/DisoFLAG/main/dataset/DP94.txt"
PROTECTED = ROOT / "data/processed/caid3_protected_dfl_v1"
RULE = {"matrix": "BLOSUM62", "gap_open": 10, "gap_extend": 1,
        "minimum_identity": 0.25, "minimum_aligned_residues": 50,
        "minimum_shorter_sequence_coverage": 0.50}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    return digest(path.read_bytes())


def fetch_sequences() -> tuple[bytes, list[dict]]:
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "LinkerForge-holdout-audit/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
    lines = raw.decode("utf-8").splitlines()
    if len(lines) % 9:
        raise ValueError("Unexpected DisoFLAG nine-line block count")
    rows = []
    for at in range(0, len(lines), 9):
        header, sequence = lines[at], lines[at + 1].upper()
        if not header.startswith(">") or not sequence or set(sequence) - set("ACDEFGHIKLMNPQRSTVWYXBZUO"):
            raise ValueError(f"Malformed sequence-only record at block {at // 9}")
        # Deliberately do not inspect lines at+2 through at+8 (labels/tracks).
        rows.append({"protein_id": header[1:].split()[0], "sequence": sequence})
    if len(rows) != 98 or len({row["protein_id"] for row in rows}) != len(rows):
        raise ValueError("Unexpected DP94 protein count or duplicate ID")
    return raw, rows


def local_match(a: str, b: str) -> dict | None:
    result = parasail.sw_stats_striped_16(a, b, RULE["gap_open"], RULE["gap_extend"], parasail.blosum62)
    if not result.length:
        return None
    identity = result.matches / result.length
    coverage = result.length / min(len(a), len(b))
    if (result.length >= RULE["minimum_aligned_residues"]
            and identity >= RULE["minimum_identity"]
            and coverage >= RULE["minimum_shorter_sequence_coverage"]):
        return {"aligned_residues": result.length, "identity": round(identity, 5),
                "shorter_sequence_coverage": round(coverage, 5)}
    return None


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Immutable output already exists: {OUTPUT}")
    raw, rows = fetch_sequences()
    training = []
    input_hashes = {}
    for split in ("train", "development", "auxiliary"):
        path = PROTECTED / f"{split}.jsonl"
        input_hashes[split] = file_sha(path)
        for line in path.read_text(encoding="utf-8").splitlines():
            if line:
                record = json.loads(line)
                training.append({"split": split, "protein_id": record["protein_id"],
                                 "sequence": record["sequence"].upper()})
    hits = []
    for held in rows:
        for item in training:
            reasons = []
            if held["protein_id"] == item["protein_id"]:
                reasons.append("exact_id")
            if held["sequence"] == item["sequence"]:
                reasons.append("exact_sequence")
            elif held["sequence"] in item["sequence"] or item["sequence"] in held["sequence"]:
                reasons.append("sequence_containment")
            alignment = local_match(held["sequence"], item["sequence"])
            if alignment:
                reasons.append("declared_local_similarity")
            if reasons:
                hits.append({"holdout_id": held["protein_id"], "split": item["split"],
                             "training_id": item["protein_id"], "reasons": reasons,
                             "alignment": alignment})
    connected = sorted({hit["holdout_id"] for hit in hits})
    fasta = "".join(f">{row['protein_id']}\n{row['sequence']}\n" for row in rows)
    payload = {
        "schema_version": "1.0.0", "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "candidate_not_certified_independent",
        "source_url": SOURCE_URL, "source_sha256": digest(raw),
        "label_policy": "Source label lines were not parsed, saved, scored, or viewed by this script",
        "holdout_proteins": len(rows), "holdout_ids": [row["protein_id"] for row in rows],
        "sequence_fasta_sha256": digest(fasta.encode("utf-8")),
        "training_file_sha256": input_hashes,
        "local_similarity_rule": RULE,
        "connected_holdout_proteins": len(connected),
        "connected_holdout_ids": connected,
        "hits": hits,
        "limitations": [
            "Published DP94 is a candidate local holdout, not a newly adjudicated prospective benchmark.",
            "Declared local alignment does not certify remote homology/domain-family separation.",
            "Competitor training-set exposure and obtainable equal-coverage predictions are not audited.",
            "No-linker labels and annotation completeness require source-level adjudication.",
            "Protein-language-model pretraining exposure is not controlled."
        ],
        "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "software": {"parasail": parasail.__version__},
    }
    OUTPUT.mkdir(parents=True)
    (OUTPUT / "sequences.fasta").write_text(fasta, encoding="utf-8")
    (OUTPUT / "manifest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "holdout_proteins": len(rows),
                      "connected_holdout_proteins": len(connected), "hit_pairs": len(hits),
                      "source_sha256": payload["source_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
