"""Task-stratified development metrics, conservative ties and paired clusters."""
import math
import random

from .model import TASKS, allowed_positions
from linkerforge.generation.contracts import family_components


def binary_metrics(labels, scores):
    if len(labels) != len(scores) or any(y not in (0, 1) for y in labels) or any(not math.isfinite(s) for s in scores):
        raise ValueError("Metrics need aligned finite known binary labels/scores")
    positives, negatives = sum(labels), len(labels)-sum(labels)
    groups = {}
    for label, score in zip(labels, scores):
        groups.setdefault(score, []).append(label)
    tp, fp, average_precision = 0, 0, 0.
    for score in sorted(groups, reverse=True):
        group = groups[score]
        added = sum(group)
        tp, fp = tp + added, fp + len(group)-added
        average_precision += added * tp / (tp+fp)
    below, favorable = 0, 0.
    for score in sorted(groups):
        group = groups[score]
        pos, neg = sum(group), len(group)-sum(group)
        favorable += pos * (below + .5 * neg)
        below += neg
    return {"positive": positives, "negative": negatives,
            "auroc": favorable/(positives*negatives) if positives and negatives else None,
            "average_precision": average_precision/positives if positives else None}


def summarize(rows, predictions, coverage_fraction):
    known_labels, known_scores, candidates, failures = [], [], [], []
    expected_known = sum(y != -1 for row in rows for y in row.labels)
    expected_sites = sum(len(allowed_positions(row.task, len(row.sequence))) for row in rows)
    for row in rows:
        scores = predictions.get(row.record_id)
        valid = isinstance(scores, list) and len(scores) == len(row.sequence) and all(type(x) in (int, float) and math.isfinite(x) for x in scores)
        if not valid:
            failures.append(row.record_id)
            continue
        for i in allowed_positions(row.task, len(row.sequence)):
            label, score = row.labels[i-1], scores[i-1]
            candidates.append((score, label))
            if label != -1:
                known_labels.append(label)
                known_scores.append(score)
    metrics = binary_metrics(known_labels, known_scores)
    budget = math.floor(coverage_fraction * expected_sites)
    grouped = {}
    for score, label in candidates:
        grouped.setdefault(score, []).append(label)
    selected = []
    for score in sorted(grouped, reverse=True):
        group = grouped[score]
        if len(selected) + len(group) > budget:
            break  # never cherry-pick within a tied score group
        selected += group
    tp, fp, unknown = selected.count(1), selected.count(0), selected.count(-1)
    return {"attempted_records": len(rows), "valid_records": len(rows)-len(failures), "failed_record_ids": failures,
            "reference_positive": sum(y == 1 for row in rows for y in row.labels),
            "reference_negative": sum(y == 0 for row in rows for y in row.labels),
            "reference_unknown": sum(y == -1 for row in rows for y in row.labels),
            "expected_known_sites": expected_known, "covered_known_sites": len(known_labels),
            "known_subset_auroc": metrics["auroc"], "known_subset_average_precision": metrics["average_precision"],
            "auroc": metrics["auroc"] if not failures else None,
            "average_precision": metrics["average_precision"] if not failures else None,
            "requested_coverage_fraction": coverage_fraction, "expected_candidate_sites": expected_sites,
            "selection_budget": budget, "selected_sites": len(selected), "selected_positive": tp, "selected_negative": fp,
            "selected_unknown": unknown, "actual_coverage": len(selected)/expected_sites if expected_sites else None,
            "precision": tp/(tp+fp) if tp+fp and not unknown and not failures else None,
            "known_subset_precision": tp/(tp+fp) if tp+fp else None,
            "recall_known_positive": tp/metrics["positive"] if metrics["positive"] and not failures else None,
            "annotation_scope": "Known labels only; unknown calls make exhaustive precision unidentifiable."}


def compare(rows, methods, coverage_fraction=.1, bootstrap_draws=200, seed=17):
    if not 0 < coverage_fraction <= 1 or type(bootstrap_draws) is not int or not 0 <= bootstrap_draws <= 1000:
        raise ValueError("Invalid frozen coverage/bootstrap settings")
    if not methods:
        raise ValueError("At least one method is required")
    output = {}
    for task in TASKS:
        subset = [row for row in rows if row.task == task]
        if not subset:
            continue
        full = {name: summarize(subset, values, coverage_fraction) for name, values in methods.items()}
        failed = {identity for value in full.values() for identity in value["failed_record_ids"]}
        common = [row for row in subset if row.record_id not in failed]
        common_metrics = {name: summarize(common, values, coverage_fraction) for name, values in methods.items()}
        components = family_components(common)
        uncertainty = {}
        names = list(methods)
        for name in names[1:]:
            deltas, rng = [], random.Random(seed)
            if len(components) >= 2:
                for _ in range(bootstrap_draws):
                    sampled = [row for _ in components for row in components[rng.randrange(len(components))]]
                    left = summarize(sampled, methods[names[0]], coverage_fraction)["average_precision"]
                    right = summarize(sampled, methods[name], coverage_fraction)["average_precision"]
                    if left is not None and right is not None:
                        deltas.append(left-right)
            deltas.sort()
            uncertainty[name] = {"contrast": f"{names[0]} minus {name}", "metric": "known-label average_precision",
                "independent_family_components": len(components), "requested_draws": bootstrap_draws, "valid_draws": len(deltas),
                "paired_percentile_95_interval": [deltas[int(.025*(len(deltas)-1))], deltas[int(.975*(len(deltas)-1))]] if deltas else None,
                "seed": seed, "limitation": "Descriptive cluster bootstrap; not calibration or a guarantee."}
        output[task] = {"full_attempted_coverage": full, "common_coverage": common_metrics,
                        "common_records": len(common), "paired_family_uncertainty": uncertainty}
    return {"format": "attachment-development-benchmark.v0", "tasks": output,
            "coverage_fraction": coverage_fraction, "bootstrap_draws": bootstrap_draws,
            "limitations": ["Task endpoints are not pooled.", "No labels or thresholds selected by this evaluator.",
                            "Unknown annotations are excluded, never converted to negatives.",
                            "This is a development harness; independent benchmark reveal requires a separately frozen protocol."]}
