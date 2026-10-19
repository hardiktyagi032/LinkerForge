"""Conservative candidate homology screen, not independence certification."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from Bio import __version__ as biopython_version
from Bio.Align import PairwiseAligner

from train_esm2_linker_detector import file_hash


def rows(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def kmers(sequence: str, k: int) -> set[str]:
    return {sequence[index:index + k] for index in range(max(0, len(sequence) - k + 1))}


def local_overlap(query: str, target: str, aligner: PairwiseAligner) -> tuple[float, float, int]:
    alignments = aligner.align(query, target)
    if not alignments:
        return 0.0, 0.0, 0
    alignment = alignments[0]
    aligned = matches = 0
    for (qa, qb), (ta, tb) in zip(*alignment.aligned):
        qpart, tpart = query[qa:qb], target[ta:tb]
        aligned += min(len(qpart), len(tpart))
        matches += sum(q == t for q, t in zip(qpart, tpart))
    shorter = min(len(query), len(target))
    return aligned / shorter if shorter else 0.0, matches / aligned if aligned else 0.0, aligned


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disprot", type=Path,
                        default=Path("data/processed/disprot_2026_06_flexible_linkers.jsonl"))
    parser.add_argument("--dld", type=Path, nargs="+", default=[
        Path("data/processed/dld_reference/dld_train.jsonl.gz"),
        Path("data/processed/dld_reference/dld_validation.jsonl.gz"),
        Path("data/processed/dld_reference/dld_blind.jsonl.gz")])
    parser.add_argument("--output", type=Path,
                        default=Path("reports/disprot_dld_homology_screen_2026-10-11.json"))
    parser.add_argument("--limit-query", type=int, default=0, help="Smoke only; zero screens all unique proteins")
    args = parser.parse_args()
    disprot_regions = list(rows(args.disprot))
    references = [row for path in args.dld for row in rows(path)]
    proteins = {}
    regions_by_protein = defaultdict(list)
    for row in disprot_regions:
        name = row["disprot_id"]
        if name in proteins and proteins[name]["sequence"] != row["sequence"]:
            raise ValueError(f"Conflicting sequences for {name}")
        proteins[name] = row
        regions_by_protein[name].append(row["region_id"])
    queries = list(proteins.items())
    if args.limit_query:
        queries = queries[:args.limit_query]
    k, top_n = 5, 20
    target_kmers = [kmers(row["sequence"], k) for row in references]
    index = defaultdict(list)
    for target_index, words in enumerate(target_kmers):
        for word in words:
            index[word].append(target_index)
    aligner = PairwiseAligner()
    aligner.mode = "local"
    aligner.match_score = 1
    aligner.mismatch_score = -1
    aligner.open_gap_score = -3
    aligner.extend_gap_score = -0.5
    hits = []
    for name, row in queries:
        counts = Counter(target_index for word in kmers(row["sequence"], k)
                         for target_index in index.get(word, []))
        candidates = [target_index for target_index, _ in counts.most_common(top_n)]
        for target_index in candidates:
            target = references[target_index]
            coverage, identity, aligned = local_overlap(row["sequence"], target["sequence"], aligner)
            if coverage >= 0.30 and identity >= 0.30 and aligned >= 40:
                hits.append({"disprot_id": name, "disprot_region_ids": regions_by_protein[name],
                             "disprot_uniprot_accession": row["uniprot_accession"],
                             "dld_source_id": target["source_id"], "dld_split": target["split"],
                             "dld_cluster_id": target["homology_cluster_id"],
                             "same_accession": row["uniprot_accession"] == target["source_id"].split("_")[-1],
                             "shorter_sequence_coverage": round(coverage, 4),
                             "aligned_identity": round(identity, 4), "aligned_residues": aligned})
    config = {"kmer_size": k, "top_candidates": top_n,
              "alignment": "local match=1 mismatch=-1 open=-3 extend=-0.5",
              "hit_min_shorter_coverage": 0.30, "hit_min_identity": 0.30,
              "hit_min_aligned_residues": 40, "limit_query": args.limit_query}
    report = {
        "schema_version": "0.1.0", "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "candidate_homology_screen_not_independence_certification",
        "source_sha256": {str(path): file_hash(path) for path in [args.disprot, *args.dld]},
        "script_sha256": file_hash(Path(__file__)),
        "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
        "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "software": {"python": sys.version.split()[0], "biopython": biopython_version},
        "config": config, "disprot_regions": len(disprot_regions),
        "unique_disprot_proteins": len(proteins), "screened_proteins": len(queries),
        "dld_records": len(references), "hits": hits,
        "hit_proteins": len({hit["disprot_id"] for hit in hits}),
        "hit_regions": len({region for hit in hits for region in hit["disprot_region_ids"]}),
        "hit_proteins_by_split": {split: len({hit["disprot_id"] for hit in hits if hit["dld_split"] == split})
                                  for split in ("train", "validation", "blind")},
        "limitations": [
            "Top-20 5-mer prescreen can miss remote homologs or low-complexity alignments.",
            "Local 30% identity/coverage is a candidate flag, not a verified family assignment.",
            "Full-length, isoform, domain-pair, and residue-coordinate mapping remain unadjudicated.",
            "No unflagged record is certified independent or eligible for blind evaluation."
        ]
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("status", "screened_proteins", "hit_proteins",
                                                  "hit_regions", "hit_proteins_by_split")}))


if __name__ == "__main__":
    main()
