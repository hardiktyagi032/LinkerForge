"""Build sequence-blacklisted DFL development splits without reading CAID3 labels.

The local-alignment rule is an explicit contamination screen, not proof that
remote homology or pretrained-encoder exposure is absent.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import parasail

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "artifacts/caid3-linker.fasta"
SOURCES = {
    "train": ROOT / "data/processed/published_dfl_splits/tr166.jsonl",
    "development": ROOT / "data/processed/published_dfl_splits/te82.jsonl",
    "auxiliary": ROOT / "data/processed/disorder_transfer_pilot_v1/pretrain.jsonl",
}
OUTPUT = ROOT / "data/processed/caid3_protected_dfl_v1"
RULE = {"minimum_identity": 0.25, "minimum_aligned_residues": 50,
        "minimum_shorter_sequence_coverage": 0.50,
        "matrix": "BLOSUM62", "gap_open": 10, "gap_extend": 1}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference_sequences(path: Path) -> list[tuple[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) % 3:
        raise ValueError("Expected three-line CAID3 records")
    result = []
    for at in range(0, len(lines), 3):
        identifier, sequence, _labels = lines[at:at + 3]
        # The third line is deliberately ignored: blacklist uses no test labels.
        if not identifier.startswith(">") or not sequence or len(sequence) != len(_labels):
            raise ValueError("Malformed CAID3 record")
        result.append((identifier[1:].split()[0], sequence.upper()))
    if len(result) != 31:
        raise ValueError("Unexpected CAID3 target count")
    return result


def match(item: dict, references: list[tuple[str, str]]) -> dict | None:
    identifier = item["protein_id"]
    sequence = item["sequence"].upper()
    for target_id, target in references:
        if identifier == target_id or sequence == target or sequence in target or target in sequence:
            return {"protein_id": identifier, "caid3_id": target_id,
                    "reason": "exact_id_sequence_or_containment"}
        alignment = parasail.sw_stats_striped_16(sequence, target, 10, 1, parasail.blosum62)
        if (alignment.length >= RULE["minimum_aligned_residues"] and
                alignment.length / min(len(sequence), len(target)) >= RULE["minimum_shorter_sequence_coverage"] and
                alignment.matches / alignment.length >= RULE["minimum_identity"]):
            return {"protein_id": identifier, "caid3_id": target_id,
                    "reason": "candidate_local_similarity",
                    "aligned_residues": alignment.length,
                    "identity": round(alignment.matches / alignment.length, 6),
                    "shorter_sequence_coverage": round(alignment.length / min(len(sequence), len(target)), 6)}
    return None


def build() -> dict:
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    references = reference_sequences(REFERENCE)
    retained_by_source: dict[str, list[dict]] = {}
    excluded_by_source: dict[str, list[dict]] = {}
    for name, source in SOURCES.items():
        retained, excluded = [], []
        for line in source.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if len(row["sequence"]) != len(row["labels"]):
                raise ValueError(f"Sequence/label length mismatch: {name} {row['protein_id']}")
            hit = match(row, references)
            if hit:
                excluded.append(hit)
            else:
                retained.append(row)
        retained_by_source[name] = retained
        excluded_by_source[name] = excluded
    OUTPUT.mkdir(parents=True)
    file_info = {}
    for name, rows in retained_by_source.items():
        path = OUTPUT / f"{name}.jsonl"
        path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
        file_info[name] = {"path": str(path.relative_to(ROOT)), "sha256": sha(path),
                           "retained_proteins": len(rows),
                           "excluded_proteins": len(excluded_by_source[name]),
                           "positive_residues": sum(row["labels"].count("1") for row in rows),
                           "negative_residues": sum(row["labels"].count("0") for row in rows),
                           "unknown_residues": sum(row["labels"].count("x") for row in rows)}
    blacklist = OUTPUT / "blacklist.json"
    blacklist.write_text(json.dumps(excluded_by_source, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {"schema_version": "1.0.0", "status": "sequence_screened_not_full_homology_certification",
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "reference_sha256": sha(REFERENCE), "reference_proteins": len(references),
                "source_sha256": {name: sha(path) for name, path in SOURCES.items()},
                "rule": RULE, "files": file_info, "blacklist_sha256": sha(blacklist),
                "blacklist_reasons": dict(Counter(hit["reason"] for hits in excluded_by_source.values() for hit in hits)),
                "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "script_sha256": sha(Path(__file__)),
                "software": {"python": sys.version.split()[0], "parasail": parasail.__version__},
                "limitations": ["Only explicit IDs, exact sequence/containment, and the declared local-alignment rule are excluded.",
                                "This is not a full family/remote-homology certification.",
                                "A public CAID3 evaluation remains retrospective because its labels were viewed before this round.",
                                "ESM-2 pretraining corpus exposure is not controlled by this filtering step."]}
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build()["files"], indent=2))
