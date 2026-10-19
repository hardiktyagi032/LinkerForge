"""Frozen region-level diagnostics for DLD linker identification."""


def spans(flags: list[bool]) -> list[tuple[int, int]]:
    """1-based inclusive contiguous positive intervals."""
    result = []
    start = None
    for position, value in enumerate([*flags, False], start=1):
        if value and start is None:
            start = position
        elif not value and start is not None:
            result.append((start, position - 1))
            start = None
    return result


def region_metrics(truth_by_protein: dict[str, list[bool]],
                   score_by_protein: dict[str, list[float]], threshold: float,
                   minimum_iou: float = 0.5) -> dict:
    """Greedy one-to-one matching, ranked by interval IoU, across proteins."""
    if not 0 < minimum_iou <= 1 or truth_by_protein.keys() != score_by_protein.keys():
        raise ValueError("Invalid region evaluation inputs")
    true_total = predicted_total = matched = 0
    start_errors, end_errors = [], []
    for protein in truth_by_protein:
        truth = truth_by_protein[protein]
        scores = score_by_protein[protein]
        if len(truth) != len(scores):
            raise ValueError("Truth/score lengths differ")
        true_spans = spans(truth)
        predicted_spans = spans([value >= threshold for value in scores])
        true_total += len(true_spans)
        predicted_total += len(predicted_spans)
        possible = []
        for i, (a, b) in enumerate(true_spans):
            for j, (c, d) in enumerate(predicted_spans):
                intersection = max(0, min(b, d) - max(a, c) + 1)
                union = (b - a + 1) + (d - c + 1) - intersection
                iou = intersection / union
                if iou >= minimum_iou:
                    possible.append((iou, i, j))
        used_truth, used_prediction = set(), set()
        for _, i, j in sorted(possible, reverse=True):
            if i in used_truth or j in used_prediction:
                continue
            used_truth.add(i)
            used_prediction.add(j)
            matched += 1
            start_errors.append(abs(true_spans[i][0] - predicted_spans[j][0]))
            end_errors.append(abs(true_spans[i][1] - predicted_spans[j][1]))
    return {"iou_threshold": minimum_iou, "true_regions": true_total,
            "predicted_regions": predicted_total, "matched_regions": matched,
            "region_precision": matched / predicted_total if predicted_total else 0.0,
            "region_recall": matched / true_total if true_total else 0.0,
            "matched_start_mae": sum(start_errors) / matched if matched else None,
            "matched_end_mae": sum(end_errors) / matched if matched else None}
