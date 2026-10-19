"""Conservative TR166-to-TE82 similarity screen; not homology certification."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

from Bio import __version__ as biopython_version
from Bio.Align import PairwiseAligner


ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "data/processed/published_dfl_splits/tr166.jsonl"
DEV = ROOT / "data/processed/published_dfl_splits/te82.jsonl"
OUT = ROOT / "reports/dfl_tr166_te82_similarity_screen_2026-10-12.json"


def read(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def kmers(sequence, size=5):
    return {sequence[i:i + size] for i in range(max(0, len(sequence) - size + 1))}


def alignment_stats(query, target, aligner):
    match = aligner.align(query, target)[0]
    aligned = identical = 0
    for (qa, qb), (ta, tb) in zip(*match.aligned):
        a, b = query[qa:qb], target[ta:tb]
        aligned += len(a)
        identical += sum(x == y for x, y in zip(a, b))
    return aligned / len(query), aligned / len(target), identical / aligned if aligned else 0


def main():
    train, dev = read(TRAIN), read(DEV)
    aligner = PairwiseAligner()
    aligner.mode = "local"
    aligner.match_score, aligner.mismatch_score = 1, -1
    aligner.open_gap_score, aligner.extend_gap_score = -3, -0.5
    indexed = [kmers(r["sequence"]) for r in train]
    hits = []
    exact = []
    for query in dev:
        for target in train:
            if query["sequence"] == target["sequence"]:
                exact.append([query["protein_id"], target["protein_id"]])
        candidates = Counter({i: len(kmers(query["sequence"]) & words) for i, words in enumerate(indexed)})
        for idx, shared in candidates.most_common(20):
            if not shared:
                break
            target = train[idx]
            qcoverage, tcoverage, identity = alignment_stats(query["sequence"], target["sequence"], aligner)
            if (qcoverage >= 0.7 or tcoverage >= 0.7) and identity >= 0.5:
                hits.append({"dev_id": query["protein_id"], "train_id": target["protein_id"],
                             "shared_5mers": shared, "dev_coverage": round(qcoverage, 4),
                             "train_coverage": round(tcoverage, 4), "aligned_identity": round(identity, 4)})
    result = {"schema_version": "0.1.0", "status": "candidate_screen_not_homology_certification",
              "train_proteins": len(train), "dev_proteins": len(dev), "exact_sequence_overlaps": exact,
              "candidate_hits": hits, "dev_proteins_with_hits": len({x["dev_id"] for x in hits}),
              "configuration": {"top_candidates_per_dev": 20, "kmer_size": 5,
                                "local_alignment": "match=1 mismatch=-1 gap_open=-3 gap_extend=-0.5",
                                "flag": "(dev_coverage>=0.7 or train_coverage>=0.7) and aligned_identity>=0.5"},
              "limitations": ["Top-20 shared-kmer candidates can miss remote homologs.",
                              "Low-complexity sequence can create spurious local matches.",
                              "A negative screen does not establish family independence."],
              "provenance": {"train_sha256": hashlib.sha256(TRAIN.read_bytes()).hexdigest(),
                             "dev_sha256": hashlib.sha256(DEV.read_bytes()).hexdigest(),
                             "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                             "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                             "biopython": biopython_version}}
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"exact_overlaps": len(exact), "candidate_hits": len(hits),
                      "dev_proteins_with_hits": result["dev_proteins_with_hits"]}))


if __name__ == "__main__":
    main()
