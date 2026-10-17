"""Intersect curated DisProt linker regions with Pfam gap screens for review."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPLICIT = ROOT / "data/processed/disprot_2026_06_flexible_linkers.jsonl"
GAPS = ROOT / "data/processed/disprot_2026_06_domain_gap_screen.jsonl"
HOMOLOGY = ROOT / "reports/disprot_dld_homology_screen_2026-10-11.json"
OUTPUT = ROOT / "reports/disprot_domain_context_review_queue_2026-10-11.json"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rows(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def overlap(a: dict, b: dict) -> int:
    return max(0, min(a["end"], b["end"]) - max(a["start"], b["start"]) + 1)


def main() -> None:
    explicit = rows(EXPLICIT)
    gaps = rows(GAPS)
    screen = json.loads(HOMOLOGY.read_text(encoding="utf-8"))
    if screen["status"] != "candidate_homology_screen_not_independence_certification":
        raise ValueError("Homology screen status changed")
    flagged = {region for hit in screen["hits"] for region in hit["disprot_region_ids"]}
    gaps_by_protein = defaultdict(list)
    for gap in gaps:
        gaps_by_protein[gap["disprot_id"]].append(gap)
    config = {"minimum_explicit_linker_coverage_by_gap": 0.8,
              "minimum_gap_coverage_by_explicit_linker": 0.8,
              "exclude_any_candidate_homology_screen_hit": True,
              "length_range_residues": [5, 30]}
    candidates = []
    for row in explicit:
        if row["region_id"] in flagged or not 5 <= row["linker"]["length"] <= 30:
            continue
        for gap_row in gaps_by_protein.get(row["disprot_id"], []):
            gap = gap_row["gap"]
            common = overlap(row["linker"], gap)
            if common / row["linker"]["length"] < 0.8 or common / gap["length"] < 0.8:
                continue
            candidates.append({
                "disprot_region_id": row["region_id"], "disprot_id": row["disprot_id"],
                "uniprot_accession": row["uniprot_accession"],
                "domain_a": gap_row["domain_a"], "domain_b": gap_row["domain_b"],
                "gap": gap, "explicit_linker": row["linker"],
                "shared_residues": common,
                "disprot_evidence": row["evidence"],
                "review_status": "pending_manual_domain_and_coordinate_adjudication",
                "evidence_quality": "curated_disprot_term_plus_pfam_gap_screen_not_independent",
            })
    report = {
        "schema_version": "0.1.0", "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "review_queue_not_validated_linkers_or_independent_test",
        "config": config,
        "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
        "source_sha256": {str(path.relative_to(ROOT)): file_hash(path) for path in (EXPLICIT, GAPS, HOMOLOGY)},
        "script_sha256": file_hash(Path(__file__)),
        "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "software": {"python": sys.version.split()[0], "extractor": "0.1.0"},
        "explicit_regions": len(explicit), "screened_gaps": len(gaps),
        "homology_flagged_regions_excluded": len(flagged),
        "candidate_pairs": len(candidates),
        "candidate_regions": len({item["disprot_region_id"] for item in candidates}),
        "candidates": candidates,
        "limitations": [
            "The top-20 local-alignment homology screen can miss remote relatives; unflagged is not independent.",
            "Pfam assignments and gap boundaries are not manually adjudicated; two-domain context is unproven.",
            "UniProt region coordinates are not mapped to PDB atoms; no record is eligible for validation or training.",
            "The same protein can contribute multiple candidate domain-gap pairs."
        ]
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("candidate_pairs", "candidate_regions", "homology_flagged_regions_excluded")}))


if __name__ == "__main__":
    main()
