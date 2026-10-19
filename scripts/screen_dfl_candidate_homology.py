"""Conservative local-alignment review screen; NOT homology certification."""

import hashlib
import json
from pathlib import Path
import subprocess
import time

import parasail


ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data/processed/dfl_positive_candidates_2026_10_12.jsonl"
SPLITS = {name: ROOT / f"data/processed/published_dfl_splits/{name}.jsonl"
          for name in ("tr166", "te82", "te64")}
CAID = ROOT / "artifacts/caid3-linker.fasta"
OUTPUT = ROOT / "reports/dfl_positive_candidate_similarity_screen_2026-10-12.json"
MAX_SECONDS = 180


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def caid_sequences(path):
    result, current, chunks = {}, None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(">"):
            if current is not None:
                result[current] = "".join(chunks)
            current, chunks = line[1:].split()[0], []
        elif line and line[0] in "ACDEFGHIKLMNPQRSTVWYX":
            chunks.append(line.strip())
    if current is not None:
        result[current] = "".join(chunks)
    # CAID reference is three-line FASTA-like: sequence followed by 0/1 label
    # line. The parser above would append labels only if they began with an
    # amino-acid letter, which 0/1 strings do not.
    return result


def main():
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    candidates = [json.loads(line) for line in CANDIDATES.read_text(encoding="utf-8").splitlines()]
    protected = {}
    for name, path in SPLITS.items():
        protected[name] = [(r["protein_id"], r["sequence"]) for line in path.read_text(encoding="utf-8").splitlines()
                           if (r := json.loads(line))]
    protected["caid3"] = list(caid_sequences(CAID).items())
    if len(protected["caid3"]) != 31:
        raise ValueError("CAID3 parser coverage error")
    started = time.monotonic()
    hits, counts = [], {name: 0 for name in protected}
    counts["within_candidates"] = 0
    compared = 0
    incomplete = False

    def check(aid, aseq, bid, bseq, source):
        nonlocal compared
        compared += 1
        if aseq == bseq:
            identity, length, score = 1.0, len(aseq), None
        else:
            aln = parasail.sw_stats_striped_16(aseq.replace("X", "A"), bseq.replace("X", "A"),
                                                10, 1, parasail.blosum62)
            identity = aln.matches / max(aln.length, 1)
            length, score = aln.length, aln.score
        coverage = min(1.0, length / min(len(aseq), len(bseq)))
        if length >= 50 and identity >= 0.25:
            counts[source] += 1
            hits.append({"candidate_id": aid, "other_id": bid, "other_source": source,
                         "identity": round(identity, 6), "aligned_length": length,
                         "shorter_coverage_proxy": round(coverage, 6), "score": score,
                         "strong_review_flag": bool(identity >= 0.30 and length >= 80 and coverage >= 0.70)})

    for index, record in enumerate(candidates):
        aid, aseq = record["protein_id"], record["sequence"]
        for source, rows in protected.items():
            for bid, bseq in rows:
                if time.monotonic() - started > MAX_SECONDS:
                    incomplete = True
                    break
                check(aid, aseq, bid, bseq, source)
            if incomplete:
                break
        if incomplete:
            break
        for other in candidates[index + 1:]:
            if time.monotonic() - started > MAX_SECONDS:
                incomplete = True
                break
            check(aid, aseq, other["protein_id"], other["sequence"], "within_candidates")
        if incomplete:
            break
    report = {"schema_version": "0.1.0", "status": "partial_time_limit" if incomplete else "complete_local_similarity_candidate_screen",
              "method": {"algorithm": "parasail.sw_stats_striped_16", "matrix": "BLOSUM62", "gap_open": 10,
                         "gap_extend": 1, "review_trigger": "identity>=0.25 and aligned_length>=50",
                         "strong_review_trigger": "identity>=0.30 and aligned_length>=80 and shorter_coverage_proxy>=0.70",
                         "x_handling": "X substituted A for scoring only; affected pairs need manual review"},
              "candidates": len(candidates), "protected_counts": {name: len(rows) for name, rows in protected.items()},
              "pairs_compared": compared, "elapsed_seconds": round(time.monotonic() - started, 3),
              "hit_counts": counts, "strong_flagged_candidates": sorted({r["candidate_id"] for r in hits if r["strong_review_flag"]}),
              "all_flagged_candidates": sorted({r["candidate_id"] for r in hits}),
              "hits": sorted(hits, key=lambda r: (r["candidate_id"], r["other_source"], -r["identity"])),
              "provenance": {"candidate_sha256": sha(CANDIDATES), "protected_sha256": {n: sha(p) for n, p in SPLITS.items()},
                             "caid3_sha256": sha(CAID), "script_sha256": sha(Path(__file__)),
                             "parasail_version": parasail.__version__,
                             "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()},
              "limitations": ["Local alignment and the shorter-coverage proxy do not certify absence of remote homology or domain-family overlap.",
                              "Low-complexity matches and X substitutions can cause spurious flags; inspect sequences and domains.",
                              "No candidate becomes trainable solely by passing this screen."]}
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("status", "candidates", "protected_counts", "pairs_compared", "elapsed_seconds", "hit_counts")}, indent=2))


if __name__ == "__main__":
    main()
