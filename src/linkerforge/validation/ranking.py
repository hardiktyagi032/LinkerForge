"""Frozen-metric primitives for linker candidate ranking.

These functions operate on scored candidate pools; they do not infer that a
natural linker is experimentally optimal or that decoys are failed fusions.
"""

from __future__ import annotations

from collections import defaultdict
from math import isfinite


def evaluate_queries(rows):
    """Return tie-aware retrieval metrics, one observed natural linker/query.

    Each row must contain query_id, candidate_id, score, observed (bool), and
    split_group_id. Equal-score observed candidates receive the average rank
    of their tie block, avoiding favorable tie-breaking.
    """
    by_query = defaultdict(list)
    for row in rows:
        if not isinstance(row.get("score"), (float, int)) or not isfinite(row["score"]):
            raise ValueError("all candidate scores must be finite")
        by_query[row["query_id"]].append(row)
    if not by_query:
        raise ValueError("no scored queries")
    per_query = []
    for query_id, candidates in sorted(by_query.items()):
        if len({row["candidate_id"] for row in candidates}) != len(candidates):
            raise ValueError(f"duplicate candidate ID in {query_id}")
        positives = [row for row in candidates if row["observed"] is True]
        if len(positives) != 1 or len(candidates) < 2:
            raise ValueError(f"{query_id} needs one observed linker and >=2 candidates")
        if len({row["split_group_id"] for row in candidates}) != 1:
            raise ValueError(f"mixed leakage groups in {query_id}")
        observed_score = positives[0]["score"]
        ahead = sum(row["score"] > observed_score for row in candidates)
        tied = sum(row["score"] == observed_score for row in candidates)
        average_rank = ahead + (tied + 1) / 2
        per_query.append({"query_id": query_id, "split_group_id": candidates[0]["split_group_id"], "rank": average_rank, "reciprocal_rank": 1 / average_rank, "top1": float(average_rank <= 1), "top5": float(average_rank <= 5), "candidate_count": len(candidates)})
    count = len(per_query)
    return {"query_count": count, "mean_reciprocal_rank": sum(row["reciprocal_rank"] for row in per_query) / count, "top1": sum(row["top1"] for row in per_query) / count, "top5": sum(row["top5"] for row in per_query) / count, "per_query": per_query}
