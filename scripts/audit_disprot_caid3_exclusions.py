"""Audit exact CAID3/DisProt overlap; never infer negatives from missing labels."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


TERM = "IDPO:0000033"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def caid_ids(path: Path) -> set[str]:
    return {line[1:].strip().split()[0] for line in path.read_text(encoding="utf-8").splitlines()
            if line.startswith(">")}


def audit(disprot: Path, caid: Path) -> dict:
    entries = json.loads(disprot.read_text(encoding="utf-8"))["data"]
    reference = caid_ids(caid)
    positive = [entry for entry in entries if any(region.get("term_id") == TERM for region in entry.get("regions", []))]
    indexed = {entry["disprot_id"]: entry for entry in entries}
    missing = sorted(reference - indexed.keys())
    if missing:
        raise ValueError(f"CAID3 proteins absent from DisProt release: {missing}")
    reference_clusters = {field: {indexed[id_].get(field) for id_ in reference} - {None, ""}
                          for field in ("uniref50", "uniref90")}
    rows = []
    for entry in positive:
        id_ = entry["disprot_id"]
        exact = id_ in reference
        shared = [field for field, values in reference_clusters.items()
                  if entry.get(field) and entry.get(field) in values and not exact]
        regions = [r for r in entry["regions"] if r.get("term_id") == TERM]
        rows.append({"disprot_id": id_, "uniprot_accession": entry.get("acc"),
                     "explicit_dfl_region_ids": sorted(r["region_id"] for r in regions),
                     "caid3_exact_id": exact, "shared_caid3_uniref_cluster_fields": shared,
                     "training_status": "exclude_public_benchmark" if exact else "pending_homology_and_label_audit"})
    rows.sort(key=lambda row: row["disprot_id"])
    return {"schema_version": "0.1.0", "record_type": "dfl_training_exclusion_audit",
            "provenance": {"disprot_sha256": sha256(disprot), "caid3_reference_sha256": sha256(caid),
                           "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                           "script_sha256": sha256(Path(__file__))},
            "semantics": {"positive": "explicit DisProt IDPO:0000033 annotation",
                          "negative": "none_verified_by_this_audit",
                          "unannotated": "unknown_not_negative"},
            "counts": {"disprot_entries": len(entries), "caid3_reference_entries": len(reference),
                       "explicit_dfl_entries": len(rows),
                       "exact_caid3_overlap_entries": sum(row["caid3_exact_id"] for row in rows),
                       "exact_caid3_overlap_regions": sum(len(row["explicit_dfl_region_ids"]) for row in rows if row["caid3_exact_id"]),
                       "remaining_entries": sum(not row["caid3_exact_id"] for row in rows),
                       "remaining_regions": sum(len(row["explicit_dfl_region_ids"]) for row in rows if not row["caid3_exact_id"]),
                       "remaining_shared_uniref_entries": sum(bool(row["shared_caid3_uniref_cluster_fields"]) for row in rows)},
            "limitations": ["UniRef IDs are a partial homology screen, not independence certification",
                            "No verified residue negatives or no-linker proteins are created"],
            "entries": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--disprot", type=Path, default=Path("data/raw/disprot/disprot_2026_06_regions.json"))
    parser.add_argument("--caid3", type=Path, default=Path("artifacts/caid3-linker.fasta"))
    parser.add_argument("--output", type=Path, default=Path("reports/disprot_caid3_exclusions_2026-10-11.json"))
    args = parser.parse_args()
    result = audit(args.disprot, args.caid3)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], indent=2))


if __name__ == "__main__":
    main()
