"""Count conservative DFL/negative/unknown residue masks without training."""

import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/disprot/disprot_2026_06_regions.json"
CAID = ROOT / "artifacts/caid3-linker.fasta"
OUTPUT = ROOT / "reports/disprot_dfl_label_masks_2026-10-12.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    entries = json.loads(SOURCE.read_text(encoding="utf-8"))["data"]
    caid_ids = {line[1:].strip().split()[0] for line in CAID.read_text(encoding="utf-8").splitlines()
                if line.startswith(">")}
    counts = {key: 0 for key in ("proteins", "residues", "positive", "order_candidate",
                                 "other_disorder_function_candidate", "negative_candidate",
                                 "unknown", "positive_order_conflict", "positive_other_function_overlap",
                                 "order_disorder_conflict", "invalid_coordinate_regions")}
    per_protein = []
    for entry in entries:
        if entry["disprot_id"] in caid_ids or not any(r.get("term_id") == "IDPO:0000033" for r in entry.get("regions", [])):
            continue
        sequence = entry.get("sequence", "")
        length = len(sequence)
        positive = bytearray(length)
        ordered = bytearray(length)
        disordered = bytearray(length)
        other_function = bytearray(length)
        for region in entry["regions"]:
            start, end = region.get("start"), region.get("end")
            if not isinstance(start, int) or not isinstance(end, int) or not 1 <= start <= end <= length:
                counts["invalid_coordinate_regions"] += 1
                continue
            term = region.get("term_id")
            mask = (positive if term == "IDPO:0000033" else
                    ordered if term == "IDPO:0000006" else
                    disordered if term == "IDPO:0000002" else
                    other_function if region.get("term_namespace") == "Disorder function" else None)
            if mask is not None:
                mask[start - 1:end] = b"\x01" * (end - start + 1)
        row = {key: 0 for key in ("residues", "positive", "order_candidate",
                                  "other_disorder_function_candidate", "negative_candidate", "unknown",
                                  "positive_order_conflict", "positive_other_function_overlap",
                                  "order_disorder_conflict")}
        row["residues"] = length
        for i in range(length):
            p, o, d, f = positive[i], ordered[i], disordered[i], other_function[i]
            row["positive_order_conflict"] += bool(p and o)
            row["positive_other_function_overlap"] += bool(p and f)
            row["order_disorder_conflict"] += bool(o and d)
            row["positive"] += bool(p)
            # Conflicted annotations stay unknown for negative-label purposes.
            order_candidate = bool(o and not p and not d)
            function_candidate = bool(d and f and not p and not o)
            row["order_candidate"] += order_candidate
            row["other_disorder_function_candidate"] += function_candidate
            row["negative_candidate"] += order_candidate or function_candidate
            row["unknown"] += not (p or order_candidate or function_candidate)
        counts["proteins"] += 1
        for key in row:
            counts[key] += row[key]
        per_protein.append({"disprot_id": entry["disprot_id"], "uniprot_accession": entry.get("acc"), **row})
    if counts["residues"] != counts["positive"] + counts["negative_candidate"] + counts["unknown"]:
        raise AssertionError("Masks do not partition residues")
    result = {"schema_version": "0.1.0", "record_type": "dfl_label_mask_audit",
              "provenance": {"source_sha256": digest(SOURCE), "caid3_sha256": digest(CAID),
                             "script_sha256": digest(Path(__file__)),
                             "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()},
              "status": "candidates_only_not_trainable_homology_and_ontology_review_pending",
              "counts": counts, "proteins": sorted(per_protein, key=lambda row: row["disprot_id"])}
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
