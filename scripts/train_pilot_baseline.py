"""Train and evaluate an explicitly provisional real-data linker ranker.

This is a smoke-study on unreviewed CATH/RCSB observations. It is not a paper
result and does not claim ESM/GNN, biological function, or independent test data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from linkerforge.baselines import score_candidates
from linkerforge.candidates import candidate_pool
from linkerforge.models.context import ContextQuery, LocalPort, NaturalTrainingPair, PairwiseHandFeatureRanker
from linkerforge.splits import audit_split, grouped_split


def context(record: dict) -> ContextQuery:
    ports = record.get("connection_features", {})
    if not all(name in ports for name in ("port_a", "port_b")):
        raise ValueError("Both local port features are required")
    a, b = ports["port_a"], ports["port_b"]
    return ContextQuery(
        record["domain_a"]["sequence"], record["domain_b"]["sequence"],
        LocalPort(a["accessibility_proxy"], a["contact_density"]),
        LocalPort(b["accessibility_proxy"], b["contact_density"]),
    )


def rank_of(scores: list[dict] | tuple[dict, ...], target_id: str) -> int:
    return next(i for i, item in enumerate(scores, 1) if item["candidate_id"] == target_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    payload = args.records.read_bytes()
    records = [json.loads(line) for line in payload.splitlines() if line.strip()]
    usable = [r for r in records if r.get("connection_features", {}).get("port_a") and r.get("connection_features", {}).get("port_b")]
    if len(usable) < 6:
        raise RuntimeError(f"Only {len(usable)} port-complete provisional examples; need at least 6 for a pilot")
    assignment = grouped_split(usable, seed=args.seed)
    counts = audit_split(usable, assignment)
    train = [dict(r, split="train") for r in usable if assignment[r["example_id"]] == "train"]
    blind = [r for r in usable if assignment[r["example_id"]] == "blind"]
    if len(train) < 3 or not blind:
        raise RuntimeError(f"Insufficient separated groups: {counts}")
    model_examples = []
    for record in train:
        native = record["linker"]["sequence"]
        alternatives = tuple(sorted({
            other["linker"]["sequence"] for other in train
            if other["example_id"] != record["example_id"] and other["linker"]["sequence"] != native
        }))[:5]
        if not alternatives:
            continue
        model_examples.append(NaturalTrainingPair(context(record), native, alternatives))
    if not model_examples:
        raise RuntimeError("No distinct linker alternatives available for training")
    model = PairwiseHandFeatureRanker().fit(model_examples)
    rows = []
    for record in blind:
        reference = record["linker"]["sequence"]
        production = candidate_pool(record["example_id"], train)
        covered = any(c["linker_sequence"] == reference for c in production)
        # Reference injection is evaluation-only and is not used in production.
        benchmark = candidate_pool(record["example_id"], train, reference_sequence=reference)
        ref_id = next(c["candidate_id"] for c in benchmark if c["linker_sequence"] == reference)
        query = {key: value for key, value in record.items() if key != "linker"}
        baseline_ranks = {}
        for method in ("fixed_gs", "length_heuristic", "nearest_training", "hand_features"):
            baseline_ranks[method] = rank_of(
                score_candidates(query, benchmark, train, method), ref_id)
        model_scores = sorted(
            ({"candidate_id": c["candidate_id"], "score": model.score(context(record), c["linker_sequence"])} for c in benchmark),
            key=lambda item: (-item["score"], item["candidate_id"]),
        )
        rows.append({
            "example_id": record["example_id"], "group": record["homology_cluster_id"],
            "candidate_count": len(benchmark), "production_reference_covered": covered,
            "baseline_ranks": baseline_ranks,
            "retrieval_rank": baseline_ranks["nearest_training"],
            "hand_feature_rank": rank_of(model_scores, ref_id),
            "reference_length": len(reference),
        })
    metrics = {}
    for name, key in (("retrieval", "retrieval_rank"), ("hand_feature", "hand_feature_rank")):
        metrics[name] = {
            "mrr": sum(1 / row[key] for row in rows) / len(rows),
            "top1": sum(row[key] == 1 for row in rows) / len(rows),
            "top5": sum(row[key] <= 5 for row in rows) / len(rows),
        }
    for method in ("fixed_gs", "length_heuristic", "hand_features"):
        ranks = [row["baseline_ranks"][method] for row in rows]
        metrics[method] = {
            "mrr": sum(1 / rank for rank in ranks) / len(ranks),
            "top1": sum(rank == 1 for rank in ranks) / len(ranks),
            "top5": sum(rank <= 5 for rank in ranks) / len(ranks),
        }
    report = {
        "status": "provisional_unreviewed_pilot_not_for_publication",
        "source_file_sha256": hashlib.sha256(payload).hexdigest(),
        "seed": args.seed, "split_counts": counts,
        "training_pairs": model.training_pairs, "model_name": model.name,
        "evaluation_note": "Reference is injected into an identical benchmark pool for every scorer; production coverage is reported separately. No functional labels exist.",
        "metrics": metrics, "production_reference_coverage": sum(r["production_reference_covered"] for r in rows) / len(rows),
        "per_example": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"train={len(train)} blind={len(blind)} reference_coverage={report['production_reference_coverage']:.3f} retrieval_mrr={metrics['retrieval']['mrr']:.3f} hand_feature_mrr={metrics['hand_feature']['mrr']:.3f}")


if __name__ == "__main__":
    main()
