"""Fail-closed internal coordinate and mask audit for DisProt DFL candidates."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/processed/dfl_positive_candidates_2026_10_12.jsonl"
OUTPUT = ROOT / "reports/dfl_candidate_coordinate_audit_2026-10-17.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines()]
    if len(rows) != 205 or len({row["protein_id"] for row in rows}) != len(rows):
        raise ValueError("Unexpected candidate count or duplicate protein ID")
    problems, evidence, quality = [], Counter(), Counter()
    region_count = positive_count = unknown_count = 0
    for row in rows:
        sequence, labels = row["sequence"], row["labels"]
        if len(sequence) != len(labels) or set(labels) - {"0", "1", "x"}:
            problems.append({"protein_id": row["protein_id"], "issue": "invalid_label_length_or_alphabet"})
            continue
        expected = set()
        for region in row["positive_regions"]:
            a, b = region["start_1based"], region["end_1based"]
            if not (1 <= a <= b <= len(sequence)):
                problems.append({"protein_id": row["protein_id"], "region_id": region["region_id"],
                                 "issue": "out_of_range_region"})
                continue
            positions = set(range(a - 1, b))
            if expected & positions:
                problems.append({"protein_id": row["protein_id"], "region_id": region["region_id"],
                                 "issue": "overlapping_positive_regions"})
            expected |= positions
            region_count += 1
            evidence[region.get("eco_id") or "missing"] += 1
            quality[region.get("evidence_quality") or "missing"] += 1
            if not region.get("reference_id") or not region.get("region_id"):
                problems.append({"protein_id": row["protein_id"], "issue": "missing_region_or_reference_id"})
        observed = {i for i, label in enumerate(labels) if label == "1"}
        if expected != observed:
            problems.append({"protein_id": row["protein_id"], "issue": "mask_region_coordinate_mismatch",
                             "missing_positive_positions": len(expected - observed),
                             "extra_positive_positions": len(observed - expected)})
        if "0" in labels:
            problems.append({"protein_id": row["protein_id"], "issue": "unexpected_negative_label_in_positive_only_catalog"})
        positive_count += len(observed)
        unknown_count += labels.count("x")
    result = {"schema_version": "1.0.0", "created_utc": datetime.now(timezone.utc).isoformat(),
              "status": "internal_consistency_pass" if not problems else "requires_review",
              "source_sha256": sha(SOURCE), "script_sha256": sha(Path(__file__)),
              "proteins": len(rows), "positive_regions": region_count,
              "positive_residues": positive_count, "unknown_residues": unknown_count,
              "evidence_code_region_counts": dict(sorted(evidence.items())),
              "quality_label_region_counts": dict(sorted(quality.items())),
              "problems": problems,
              "limitations": ["This checks internal coordinates, not source-to-current-release sequence mapping.",
                              "Evidence codes are counted, not independently adjudicated.",
                              "Unknown positions remain masked; no negative examples are created.",
                              "Homology/family independence is a separate gate."]}
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("status", "proteins", "positive_regions",
                                                 "positive_residues", "unknown_residues")}, indent=2))


if __name__ == "__main__":
    main()
