"""Post-processing decoders: per-residue probabilities -> contiguous spans.

Decoders use probabilities only (no labels). ``hysteresis_decode`` is a
two-threshold run builder with gap-merge and min-length; ``viterbi_decode`` is
a two-state smoother with a switch penalty. Evaluation reuses
``evaluation.region_metrics`` (greedy one-to-one IoU matching, matched
start/end MAE) and adds a pooled residue-level overlap IoU.
"""

from __future__ import annotations

import numpy as np

from .evaluation import region_metrics, spans


def _check(probabilities) -> np.ndarray:
    p = np.asarray(probabilities, dtype=np.float64)
    if p.ndim != 1 or not np.all(np.isfinite(p)) or p.min(initial=0.0) < 0 or p.max(initial=0.0) > 1:
        raise ValueError("probabilities must be a finite 1-D vector in [0, 1]")
    return p


def hysteresis_decode(probabilities, high: float = 0.5, low: float = 0.3,
                      min_length: int = 1, max_gap: int = 0) -> np.ndarray:
    """Boolean mask. Runs of p>=low are kept only if they contain p>=high;
    gaps of <=max_gap residues between kept runs are merged; runs shorter
    than min_length are then dropped."""
    p = _check(probabilities)
    if not 0 <= low <= high <= 1 or min_length < 1 or max_gap < 0:
        raise ValueError("require 0<=low<=high<=1, min_length>=1, max_gap>=0")
    mask = np.zeros(len(p), dtype=bool)
    for a, b in spans((p >= low).tolist()):
        if p[a - 1:b].max() >= high:
            mask[a - 1:b] = True
    runs = spans(mask.tolist())
    for (_, b1), (a2, _) in zip(runs[:-1], runs[1:]):
        if a2 - b1 - 1 <= max_gap:
            mask[b1:a2 - 1] = True
    for a, b in spans(mask.tolist()):
        if b - a + 1 < min_length:
            mask[a - 1:b] = False
    return mask


def viterbi_decode(probabilities, switch_penalty: float = 2.0, prior: float = 0.5,
                   eps: float = 1e-6) -> np.ndarray:
    """Exact two-state Viterbi path maximizing the summed per-residue log
    evidence (log p or log 1-p, minus the log prior) minus switch_penalty per
    state change."""
    p = np.clip(_check(probabilities), eps, 1 - eps)
    if switch_penalty < 0 or not 0 < prior < 1:
        raise ValueError("switch_penalty>=0 and 0<prior<1 required")
    n = len(p)
    if n == 0:
        return np.zeros(0, dtype=bool)
    emit = np.stack([np.log(1 - p) - np.log(1 - prior), np.log(p) - np.log(prior)], axis=1)
    score = emit[0].copy()
    back = np.zeros((n, 2), dtype=np.int8)
    states = np.arange(2)
    for i in range(1, n):
        move = score[::-1] - switch_penalty
        switch = move > score
        back[i] = np.where(switch, 1 - states, states)
        score = np.maximum(score, move) + emit[i]
    state = int(np.argmax(score))
    path = np.zeros(n, dtype=bool)
    for i in range(n - 1, -1, -1):
        path[i] = bool(state)
        state = int(back[i, state])
    return path


def residue_overlap_iou(truth_by_protein: dict, mask_by_protein: dict) -> float:
    """Pooled residue-level IoU; 1.0 if both are empty."""
    if truth_by_protein.keys() != mask_by_protein.keys():
        raise ValueError("Protein sets differ")
    inter = union = 0
    for key, truth in truth_by_protein.items():
        t = np.asarray(truth, dtype=bool)
        m = np.asarray(mask_by_protein[key], dtype=bool)
        if t.shape != m.shape:
            raise ValueError("Truth/mask lengths differ")
        inter += int(np.count_nonzero(t & m))
        union += int(np.count_nonzero(t | m))
    return inter / union if union else 1.0


def evaluate_decoding(truth_by_protein: dict, probabilities_by_protein: dict,
                      decoder, minimum_iou: float = 0.5) -> dict:
    """Apply ``decoder`` (probabilities -> bool mask) per protein; report the
    repo's region_metrics (recall/precision at IoU>=minimum_iou, matched
    start/end MAE) plus pooled residue IoU."""
    masks = {k: np.asarray(decoder(probabilities_by_protein[k]), dtype=bool)
             for k in truth_by_protein}
    result = region_metrics({k: [bool(v) for v in truth_by_protein[k]] for k in masks},
                            {k: m.astype(float).tolist() for k, m in masks.items()},
                            0.5, minimum_iou)
    result["residue_overlap_iou"] = residue_overlap_iou(truth_by_protein, masks)
    return result
