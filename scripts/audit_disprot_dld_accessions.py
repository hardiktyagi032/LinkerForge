"""Conservative UniProt-accession and direct-coordinate overlap screen."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import subprocess
import sys

from train_esm2_linker_detector import file_hash


def rows(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def mapping(disprot: dict, dld: dict) -> dict:
    query, target = disprot["sequence"], dld["sequence"]
    start, end = disprot["linker"]["start"], disprot["linker"]["end"]
    if query == target:
        kind, target_start, target_end = "identical_full_sequence", start, end
    elif target in query:
        offset = query.find(target)
        target_start, target_end = start - offset, end - offset
        kind = "dld_contained_in_disprot_sequence"
    elif query in target:
        offset = target.find(query)
        target_start, target_end = start + offset, end + offset
        kind = "disprot_contained_in_dld_sequence"
    else:
        return {"mapping": "same_accession_sequence_mapping_unresolved",
                "mapped_region_start": None, "mapped_region_end": None,
                "region_within_dld_sequence": None}
    return {"mapping": kind, "mapped_region_start": target_start,
            "mapped_region_end": target_end,
            "region_within_dld_sequence": 1 <= target_start <= target_end <= len(target)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disprot", type=Path,
                        default=Path("data/processed/disprot_2026_06_flexible_linkers.jsonl"))
    parser.add_argument("--dld", type=Path, nargs="+", default=[
        Path("data/processed/dld_reference/dld_train.jsonl.gz"),
        Path("data/processed/dld_reference/dld_validation.jsonl.gz"),
        Path("data/processed/dld_reference/dld_blind.jsonl.gz")])
    parser.add_argument("--output", type=Path,
                        default=Path("reports/disprot_dld_accession_overlap_2026-10-11.json"))
    args = parser.parse_args()
    disprot = list(rows(args.disprot))
    dld = [row for path in args.dld for row in rows(path)]
    by_accession = defaultdict(list)
    for row in dld:
        by_accession[row["source_id"].split("_")[-1]].append(row)
    hits = []
    counts = Counter()
    for region in disprot:
        for row in by_accession.get(region["uniprot_accession"], []):
            mapped = mapping(region, row)
            counts[mapped["mapping"]] += 1
            hits.append({"disprot_region_id": region["region_id"],
                         "uniprot_accession": region["uniprot_accession"],
                         "dld_source_id": row["source_id"], "dld_split": row["split"],
                         "dld_cluster_id": row["homology_cluster_id"], **mapped})
    report = {
        "schema_version": "0.1.0", "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "same_accession_overlap_screen_not_homology_certification",
        "disprot_regions": len(disprot), "dld_records": len(dld),
        "source_sha256": {str(path): file_hash(path) for path in [args.disprot, *args.dld]},
        "script_sha256": file_hash(Path(__file__)),
        "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "python": sys.version.split()[0],
        "same_accession_region_count": len({hit["disprot_region_id"] for hit in hits}),
        "same_accession_hit_pairs": len(hits),
        "hits_by_split": dict(Counter(hit["dld_split"] for hit in hits)),
        "mapping_counts": dict(counts), "hits": hits,
        "limitations": [
            "The DLD accession is inferred from the source_id suffix; verify source metadata before definitive exclusion.",
            "Same accession may refer to different isoforms; direct containment does not adjudicate domain context.",
            "Different accessions can still be homologous; this is not an independence certification.",
            "A contained DLD fragment outside the curated region is still a protein-level contamination risk."
        ]
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("status", "same_accession_region_count",
                                                  "same_accession_hit_pairs", "hits_by_split", "mapping_counts")}))


if __name__ == "__main__":
    main()
