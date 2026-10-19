"""Audit whether no-positive proteins have enough scored residues for specificity."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/caid3_protected_dfl_v1"
OUTPUT = ROOT / "reports/dfl_protected_no_positive_coverage_2026-10-17.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    manifest_path = DATA / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sections = {}
    for split in ("train", "development", "auxiliary"):
        path = DATA / f"{split}.jsonl"
        if sha(path) != manifest["files"][split]["sha256"]:
            raise ValueError(f"Split hash mismatch: {split}")
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        if len(rows) != manifest["files"][split]["retained_proteins"]:
            raise ValueError(f"Split count mismatch: {split}")
        negative = []
        for row in rows:
            labels = row["labels"]
            if len(labels) != len(row["sequence"]) or set(labels) - {"0", "1", "x"}:
                raise ValueError(f"Invalid label mask: {row['protein_id']}")
            if "1" not in labels:
                negative.append({"protein_id": row["protein_id"], "source": row["source"],
                                 "sequence_length": len(labels), "known_negative_residues": labels.count("0"),
                                 "unknown_residues": labels.count("x"),
                                 "known_fraction": labels.count("0") / len(labels)})
        sections[split] = {"proteins": len(rows), "no_positive_proteins": len(negative),
                           "records": negative}
    result = {"schema_version": "1.0.0", "created_utc": datetime.now(timezone.utc).isoformat(),
              "status": "coverage_audit_not_negative_adjudication",
              "data_manifest_sha256": sha(manifest_path), "script_sha256": sha(Path(__file__)),
              "definition": "No-positive means zero label-1 residues; zeros are source-published negatives, not independent absence adjudication.",
              "sections": sections}
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: {"no_positive_proteins": row["no_positive_proteins"],
                              "minimum_known_fraction": min((r["known_fraction"] for r in row["records"]), default=None),
                              "median_known_fraction": sorted((r["known_fraction"] for r in row["records"]))[len(row["records"]) // 2]
                              if row["records"] else None}
                      for name, row in sections.items()}, indent=2))


if __name__ == "__main__":
    main()
