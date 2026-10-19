"""K-mer/local-alignment screen of DLD blind chains against development chains.

This is a fast contamination screen, not all-vs-all homology certification.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

from Bio import __version__ as biopython_version
from Bio.Align import PairwiseAligner


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def read(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def kmers(sequence: str, k: int) -> set[str]:
    return {sequence[i:i+k] for i in range(max(0, len(sequence) - k + 1))}


def alignment_stats(query: str, reference: str, aligner: PairwiseAligner) -> tuple[float, float]:
    alignment = aligner.align(query, reference)[0]
    aligned = matched = 0
    for (qa, qb), (ra, rb) in zip(*alignment.aligned):
        left, right = query[qa:qb], reference[ra:rb]
        aligned += len(left)
        matched += sum(a == b for a, b in zip(left, right))
    return aligned / len(query), matched / aligned if aligned else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    parser.add_argument("--blind", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()
    if args.top_k < 1:
        raise ValueError("--top-k must be positive")
    reference = read(args.train) + read(args.validation)
    queries = read(args.blind)
    kmer_size = 5
    index: dict[str, list[int]] = defaultdict(list)
    for idx, row in enumerate(reference):
        for kmer in kmers(row["sequence"], kmer_size):
            index[kmer].append(idx)
    aligner = PairwiseAligner()
    aligner.mode = "local"
    aligner.match_score = 1
    aligner.mismatch_score = -1
    aligner.open_gap_score = -3
    aligner.extend_gap_score = -0.5
    hits = []
    for query in queries:
        candidate_counts = Counter(idx for kmer in kmers(query["sequence"], kmer_size)
                                   for idx in index.get(kmer, ()))
        for idx, shared in candidate_counts.most_common(args.top_k):
            target = reference[idx]
            coverage, identity = alignment_stats(query["sequence"], target["sequence"], aligner)
            if coverage >= 0.7 and identity >= 0.5:
                hits.append({"query_id": query["source_id"], "reference_id": target["source_id"],
                             "reference_split": target["split"], "shared_5mers": shared,
                             "query_coverage": round(coverage, 4), "aligned_identity": round(identity, 4),
                             "same_cluster_id": query["homology_cluster_id"] == target["homology_cluster_id"]})
    config = {"kmer_size": kmer_size, "top_k": args.top_k,
              "alignment": "local match=1 mismatch=-1 open=-3 extend=-0.5",
              "hit_coverage": 0.7, "hit_identity": 0.5}
    root = Path(__file__).resolve().parents[1]
    result = {"schema_version": "0.1.0", "status": "candidate_screen_not_homology_certification",
              "query_count": len(queries), "reference_count": len(reference),
              "hits": hits,
              "limitations": ["Only top shared-5mer candidates per query were aligned; remote homologs may be missed.",
                              "Local alignment coverage/identity is not a domain-family clustering algorithm.",
                              "Any cross-split hit requires manual and domain-level review before publication-level claims."],
              "provenance": {"source_ids": ["DLD:train", "DLD:validation", "DLD:blind"],
                             "sha256": {str(p): digest(p) for p in (args.train, args.validation, args.blind)},
                             "pipeline_commit": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
                             "script_sha256": digest(Path(__file__).resolve()),
                             "config_hash": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
                             "software": {"biopython": biopython_version},
                             "evidence_quality": "screen_only"}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"queries": len(queries), "references": len(reference),
                      "hits": len(hits), "queries_with_hits": len({item['query_id'] for item in hits})}))


if __name__ == "__main__":
    main()
