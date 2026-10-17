"""Screen published DFL sets against CAID3 with local BLOSUM62 alignment.

This is a candidate homology screen, not BLASTClust equivalence or proof of
independence. It never modifies the source labels.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

import parasail


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "artifacts/transdfl-benchmark-original"
CAID = ROOT / "artifacts/caid3-linker.fasta"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_three_line(path: Path) -> list[tuple[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) % 3 == 0
    return [(lines[i][1:].split()[0], lines[i + 1].strip()) for i in range(0, len(lines), 3)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=("TR166", "TE82", "TE64"), required=True)
    parser.add_argument("--max-seconds", type=float, default=120)
    args = parser.parse_args()
    source = DATA / f"{args.dataset}.txt"
    queries = read_three_line(source)
    references = read_three_line(CAID)
    begin = time.monotonic()
    hits = []
    pairs = 0
    incomplete = False
    for query_id, query in queries:
        for reference_id, reference in references:
            if time.monotonic() - begin > args.max_seconds:
                incomplete = True
                break
            alignment = parasail.sw_stats_striped_16(query, reference, 10, 1, parasail.blosum62)
            pairs += 1
            identity = alignment.matches / max(alignment.length, 1)
            # Threshold is a review trigger, not a declaration of homologs.
            if alignment.length >= 50 and identity >= 0.25:
                hits.append({"query_id": query_id, "caid3_id": reference_id,
                             "identity": round(identity, 5), "aligned_length": alignment.length,
                             "shorter_sequence_coverage_proxy": round(min(1.0, alignment.length / min(len(query), len(reference))), 5),
                             "matches": alignment.matches, "score": alignment.score})
        if incomplete:
            break
    result = {"schema_version": "0.1.0", "record_type": "transdfl_caid3_local_similarity_screen",
              "dataset": args.dataset, "status": "partial_time_limit" if incomplete else "complete_candidate_screen",
              "provenance": {"source_sha256": digest(source), "caid3_sha256": digest(CAID),
                             "script_sha256": digest(Path(__file__)),
                             "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                             "parasail_version": parasail.__version__},
              "method": {"aligner": "parasail.sw_stats_striped_16", "matrix": "blosum62",
                         "gap_open": 10, "gap_extend": 1,
                         "review_threshold": "identity >= 0.25 over aligned length >= 50"},
              "queries": len(queries), "references": len(references), "pairs_scored": pairs,
              "elapsed_seconds": round(time.monotonic() - begin, 3),
              "flagged_pairs": sorted(hits, key=lambda x: (-x["identity"], -x["aligned_length"], x["query_id"]))}
    output = ROOT / "reports" / f"transdfl_{args.dataset.lower()}_caid3_similarity_2026-10-12.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "pairs_scored": pairs,
                      "flagged_pairs": len(hits), "seconds": result["elapsed_seconds"]}))


if __name__ == "__main__":
    main()
