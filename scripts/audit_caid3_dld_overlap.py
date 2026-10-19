"""Screen official CAID3 linker proteins against all DLD reference splits."""

from __future__ import annotations

import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from Bio import __version__ as biopython_version
from Bio.Align import PairwiseAligner

SOURCE = "https://caid.idpcentral.org/assets/sections/challenge/static/references/3/linker.fasta"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def caid_records(path: Path) -> list[tuple[str, str, str]]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) % 3:
        raise ValueError("CAID3 linker reference is not three lines per protein")
    records = []
    for index in range(0, len(lines), 3):
        name, sequence, labels = lines[index:index + 3]
        if not name.startswith(">") or len(sequence) != len(labels) or set(labels) - set("01-"):
            raise ValueError(f"Malformed CAID3 record near line {index + 1}")
        records.append((name[1:], sequence, labels))
    return records


def dld_records(paths: list[Path]) -> list[dict]:
    records = []
    for path in paths:
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            records.extend(json.loads(line) for line in stream if line.strip())
    return records


def kmers(sequence: str, k: int) -> set[str]:
    return {sequence[index:index + k] for index in range(len(sequence) - k + 1)}


def overlap(query: str, target: str, aligner: PairwiseAligner) -> tuple[float, float]:
    alignment = aligner.align(query, target)[0]
    matches = aligned = 0
    for (qa, qb), (ta, tb) in zip(*alignment.aligned):
        for q, t in zip(query[qa:qb], target[ta:tb]):
            matches += q == t
            aligned += 1
    return aligned / len(query), matches / aligned if aligned else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--caid3", required=True, type=Path)
    parser.add_argument("--dld", required=True, type=Path, nargs="+")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = caid_records(args.caid3)
    references = dld_records(args.dld)
    k = 5
    top_candidates = 5
    aligner = PairwiseAligner()
    aligner.mode = "local"
    aligner.match_score = 1
    aligner.mismatch_score = -1
    aligner.open_gap_score = -3
    aligner.extend_gap_score = -0.5
    target_kmers = [(row, kmers(row["sequence"], k)) for row in references]
    hits = []
    for name, query, _ in source:
        query_kmers = kmers(query, k)
        nearest = sorted(target_kmers, key=lambda item: len(query_kmers & item[1]), reverse=True)[:top_candidates]
        for row, _ in nearest:
            coverage, identity = overlap(query, row["sequence"], aligner)
            if coverage >= 0.30 and identity >= 0.30:
                hits.append({"caid_id": name, "dld_source_id": row["source_id"],
                             "dld_split": row["split"], "dld_cluster_id": row["homology_cluster_id"],
                             "query_coverage": round(coverage, 4),
                             "aligned_identity": round(identity, 4),
                             "same_full_sequence": query == row["sequence"]})
    config = {"k": k, "top_candidates": top_candidates,
              "alignment": "local match=1 mismatch=-1 open=-3 extend=-0.5",
              "hit_coverage": 0.30, "hit_identity": 0.30}
    report = {"schema_version": "0.1.0",
              "status": "sequence_overlap_screen_not_full_homology_certification",
              "source_url": SOURCE, "source_sha256": sha256(args.caid3),
              "source_records": len(source), "dld_records": len(references),
              "dld_shards_sha256": {str(path): sha256(path) for path in args.dld},
              "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "config_hash": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
              "software": {"python": sys.version.split()[0], "biopython": biopython_version},
              "evidence_quality": "official_caid3_reference_and_curated_dld",
              "hits": hits,
              "hits_with_train": len({item["caid_id"] for item in hits if item["dld_split"] == "train"}),
              "limitations": ["Top-5 k-mer prescreen plus local alignment may miss remote homologs.",
                              "A hit indicates potential benchmark contamination, not functional equivalence.",
                              "No CAID3 model accuracy is claimed by this audit."]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "caid_records": len(source),
                      "hits": len(hits), "hits_with_train": report["hits_with_train"]}), flush=True)


if __name__ == "__main__":
    main()
