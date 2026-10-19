"""Convert per-residue linker scores to explicit sequence intervals."""

from collections import Counter
from math import isfinite


AMINO_ACIDS = frozenset("ACDEFGHIKLMNPQRSTVWY")


def intervals(sequence: str, scores: list[float], threshold: float) -> list[dict]:
    """Return 1-based inclusive intervals; no smoothing or tuned gap joining."""
    sequence = sequence.upper()
    if not sequence or len(sequence) != len(scores):
        raise ValueError("Sequence and score vector must be nonempty and equal-length")
    if set(sequence) - AMINO_ACIDS:
        raise ValueError("Only canonical amino-acid sequences are supported")
    if not isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Threshold must be finite and in [0, 1]")
    if any(not isfinite(float(score)) or not 0 <= score <= 1 for score in scores):
        raise ValueError("Scores must be finite probabilities in [0, 1]")
    spans = []
    start = None
    for index, score in enumerate([*scores, -1], start=1):
        if score >= threshold and start is None:
            start = index
        elif score < threshold and start is not None:
            end = index - 1
            peptide = sequence[start - 1:end]
            counts = dict(sorted(Counter(peptide).items()))
            spans.append({
                "start": start, "end": end, "length": len(peptide),
                "sequence": peptide, "composition_counts": counts,
                "composition_fractions": {aa: count / len(peptide) for aa, count in counts.items()},
                "mean_residue_score": sum(scores[start - 1:end]) / len(peptide),
                "max_residue_score": max(scores[start - 1:end]),
            })
            start = None
    return spans
