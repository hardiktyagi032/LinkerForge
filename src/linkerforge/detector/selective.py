"""Selective prediction with a calibrated, precision-targeted threshold.

Residue-level DFL scores are thresholded so that the model abstains (predicts
nothing) below a threshold chosen on a *calibration* half of the development
proteins. The threshold is the lowest score whose calibration precision has a
one-sided Clopper-Pearson lower confidence bound >= the target. It is then
applied once to the disjoint *evaluation* half.

Conventions (binding, see the DFL untouched-comparison contract):
  * labels: 1 = linker, 0 = negative, -1 = unknown ('x'); unknown residues are
    masked everywhere and never counted as negatives.
  * Only development proteins are used. No benchmark (e.g. CAID3) labels,
    scores or thresholds may be passed in here.
  * Labels are incomplete, so a "false positive" may be an unannotated true
    linker: measured precision is a LOWER BOUND on true precision.

Pure numpy / stdlib (no scipy).
"""
from __future__ import annotations

import math
from typing import Dict, List, Mapping, Sequence, Tuple

import numpy as np

UNKNOWN = -1


# --------------------------------------------------------------------------
# Clopper-Pearson (exact binomial) lower bound, stdlib only
# --------------------------------------------------------------------------
_LF = np.zeros(1)


def _log_factorials(n: int) -> np.ndarray:
    global _LF
    if len(_LF) <= n:
        m = max(n, 2 * len(_LF))
        _LF = np.r_[0.0, np.cumsum(np.log(np.arange(1, m + 1)))]
    return _LF


def _upper_tail(n: int, k: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p)."""
    if k <= 0:
        return 1.0
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    ks = np.arange(k, n + 1)
    lf = _log_factorials(n)
    lg = lf[n] - lf[ks] - lf[n - ks]
    lp = lg + ks * math.log(p) + (n - ks) * math.log1p(-p)
    m = lp.max()
    return float(min(1.0, math.exp(m) * np.exp(lp - m).sum()))


def clopper_pearson_lower(successes: int, trials: int, alpha: float = 0.05) -> float:
    """One-sided (1-alpha) exact lower confidence bound for a binomial proportion.

    Solves P(X >= successes | trials, p) = alpha for p by bisection.
    Returns 0.0 when successes == 0 or trials == 0.
    """
    if trials <= 0 or successes <= 0:
        return 0.0
    if successes > trials:
        raise ValueError("successes > trials")
    if successes == trials:
        return float(alpha ** (1.0 / trials))
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if _upper_tail(trials, successes, mid) < alpha:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# --------------------------------------------------------------------------
# Data handling
# --------------------------------------------------------------------------
def split_proteins(ids: Sequence[str], seed: int = 0, calibration_fraction: float = 0.5
                   ) -> Tuple[List[str], List[str]]:
    """Deterministic split BY PROTEIN into (calibration, evaluation)."""
    ids = sorted(set(ids))
    if len(ids) < 2:
        raise ValueError("need at least two proteins to split")
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(ids))
    n_cal = min(max(1, int(round(len(ids) * calibration_fraction))), len(ids) - 1)
    cal = sorted(ids[i] for i in order[:n_cal])
    ev = sorted(ids[i] for i in order[n_cal:])
    return cal, ev


def _stack(proteins: Sequence[str], scores: Mapping[str, Sequence[float]],
           labels: Mapping[str, Sequence[int]]) -> Tuple[np.ndarray, np.ndarray]:
    s_parts, y_parts = [], []
    for p in proteins:
        s = np.asarray(scores[p], dtype=float)
        y = np.asarray(labels[p], dtype=int)
        if s.shape != y.shape:
            raise ValueError(f"score/label length mismatch for {p}")
        if not np.all(np.isfinite(s)):
            raise ValueError(f"non-finite score for {p}")
        keep = y != UNKNOWN
        s_parts.append(s[keep])
        y_parts.append(y[keep])
    if not s_parts:
        return np.zeros(0), np.zeros(0, dtype=int)
    return np.concatenate(s_parts), np.concatenate(y_parts)


def counts_at(scores: np.ndarray, y: np.ndarray, threshold: float) -> Dict[str, int]:
    """Raw counts over known residues; predicted positive iff score >= threshold."""
    pred = scores >= threshold
    pos = y == 1
    return {"tp": int(np.sum(pred & pos)), "fp": int(np.sum(pred & ~pos)),
            "fn": int(np.sum(~pred & pos)), "tn": int(np.sum(~pred & ~pos))}


def _prec(c: Mapping[str, int]) -> float:
    d = c["tp"] + c["fp"]
    return c["tp"] / d if d else float("nan")


def _rec(c: Mapping[str, int]) -> float:
    d = c["tp"] + c["fn"]
    return c["tp"] / d if d else float("nan")


# --------------------------------------------------------------------------
# Temperature scaling (optional)
# --------------------------------------------------------------------------
def _logit(p: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    p = np.clip(p, eps, 1 - eps)
    return np.log(p / (1 - p))


def _nll(logits: np.ndarray, y: np.ndarray, t: float) -> float:
    z = logits / t
    return float(np.mean(np.maximum(z, 0) - z * y + np.log1p(np.exp(-np.abs(z)))))


def fit_temperature(scores: np.ndarray, y: np.ndarray, lo: float = 0.05, hi: float = 20.0) -> float:
    """Fit T>0 minimising calibration NLL of sigmoid(logit(score)/T).

    Fit on the CALIBRATION split only (golden-section search in log T).
    Returns 1.0 if only one class is present.
    """
    if len(y) == 0 or y.min() == y.max():
        return 1.0
    z = _logit(scores)
    a, b = math.log(lo), math.log(hi)
    g = (math.sqrt(5) - 1) / 2
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = _nll(z, y, math.exp(c)), _nll(z, y, math.exp(d))
    for _ in range(100):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = _nll(z, y, math.exp(c))
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = _nll(z, y, math.exp(d))
    return math.exp(0.5 * (a + b))


def apply_temperature(scores: np.ndarray, t: float) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-_logit(np.asarray(scores, dtype=float)) / t))


# --------------------------------------------------------------------------
# Threshold selection
# --------------------------------------------------------------------------
def select_threshold(scores: np.ndarray, y: np.ndarray, target: float,
                     alpha: float = 0.05, min_tp: int = 1) -> Dict[str, object]:
    """Lowest threshold whose calibration precision lower bound >= target.

    Candidates are the distinct calibration scores (ties included together).
    A threshold needs at least ``min_tp`` calibration true positives. If none
    qualifies the threshold is +inf (abstain on everything); this is reported.
    """
    if not 0.0 < target < 1.0:
        raise ValueError("target must be in (0, 1)")
    if len(scores) == 0:
        return {"threshold": math.inf, "feasible": False, "calibration": None}
    order = np.argsort(-scores, kind="stable")
    s, pos = scores[order], (y[order] == 1)
    cum_tp = np.cumsum(pos)
    cum_n = np.arange(1, len(s) + 1)
    last = np.r_[s[1:] != s[:-1], True]
    for i in np.nonzero(last)[0][::-1]:  # lowest threshold first
        tp, n = int(cum_tp[i]), int(cum_n[i])
        if tp < min_tp:
            continue
        # LCB >= target  <=>  P(X >= tp | n, target) <= alpha (tail is increasing in p)
        if _upper_tail(n, tp, target) <= alpha:
            lb = clopper_pearson_lower(tp, n, alpha)
            return {"threshold": float(s[i]), "feasible": True,
                    "calibration": {"tp": tp, "fp": n - tp, "precision": tp / n, "precision_lcb": lb}}
    return {"threshold": math.inf, "feasible": False, "calibration": None}


# --------------------------------------------------------------------------
# Bootstrap over proteins
# --------------------------------------------------------------------------
def bootstrap_over_proteins(per_protein: Mapping[str, Mapping[str, int]], n_boot: int = 1000,
                            seed: int = 0, ci: float = 0.95) -> Dict[str, object]:
    ids = sorted(per_protein)
    arr = np.array([[per_protein[p][k] for k in ("tp", "fp", "fn")] for p in ids], dtype=float)
    rng = np.random.default_rng(seed)
    precs, recs = [], []
    for _ in range(n_boot):
        idx = rng.integers(0, len(ids), len(ids))
        tp, fp, fn = arr[idx].sum(axis=0)
        if tp + fp > 0:
            precs.append(tp / (tp + fp))
        if tp + fn > 0:
            recs.append(tp / (tp + fn))
    q = [100 * (1 - ci) / 2, 100 * (1 + ci) / 2]

    def interval(v):
        return [float(x) for x in np.percentile(v, q)] if v else [float("nan")] * 2

    return {"n_boot": n_boot, "ci": ci, "precision_ci": interval(precs), "recall_ci": interval(recs),
            "precision_undefined_resamples": n_boot - len(precs)}


# --------------------------------------------------------------------------
# End to end
# --------------------------------------------------------------------------
LOWER_BOUND_NOTE = (
    "Labels are incomplete: residues without an annotation that are scored positive "
    "count as false positives even if they are true linkers, so measured precision "
    "is a LOWER BOUND on true precision. Unknown ('x') residues are masked."
)


def selective_report(scores: Mapping[str, Sequence[float]], labels: Mapping[str, Sequence[int]],
                     targets: Sequence[float] = (0.99, 0.90), seed: int = 0, alpha: float = 0.05,
                     calibration_fraction: float = 0.5, temperature_scaling: bool = False,
                     min_tp: int = 1, n_boot: int = 1000) -> Dict[str, object]:
    """Split by protein, calibrate thresholds, report evaluation precision/recall."""
    if set(scores) != set(labels):
        raise ValueError("scores and labels must cover identical protein ids")
    cal_ids, ev_ids = split_proteins(list(scores), seed, calibration_fraction)
    cs, cy = _stack(cal_ids, scores, labels)
    temperature = fit_temperature(cs, cy) if temperature_scaling else 1.0
    tf = (lambda a: apply_temperature(a, temperature)) if temperature_scaling else (lambda a: a)
    cs_t = tf(cs)
    out = {"calibration_proteins": cal_ids, "evaluation_proteins": ev_ids, "seed": seed,
           "alpha": alpha,
           "interval_method": "Clopper-Pearson one-sided exact lower bound on calibration "
                              "precision (residue-level; ignores within-protein dependence)",
           "temperature_scaling": temperature_scaling, "temperature": temperature,
           "min_calibration_tp": min_tp, "note": LOWER_BOUND_NOTE, "targets": {}}
    ev_scores = {p: tf(np.asarray(scores[p], dtype=float)) for p in ev_ids}
    for tgt in targets:
        sel = select_threshold(cs_t, cy, tgt, alpha, min_tp)
        thr = sel["threshold"]
        per, tot = {}, {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
        for p in ev_ids:
            y = np.asarray(labels[p], dtype=int)
            keep = y != UNKNOWN
            c = counts_at(ev_scores[p][keep], y[keep], thr)
            per[p] = c
            for k in tot:
                tot[k] += c[k]
        known = sum(tot.values())
        entry = {"threshold": thr if math.isfinite(thr) else None, "feasible": sel["feasible"],
                 "calibration": sel["calibration"], "evaluation_counts": tot,
                 "evaluation_precision_lower_bound_on_true": _prec(tot),
                 "evaluation_recall": _rec(tot),
                 "coverage_predicted_fraction": (tot["tp"] + tot["fp"]) / known if known else float("nan"),
                 "meets_target_empirically": (not math.isnan(_prec(tot))) and _prec(tot) >= tgt,
                 "bootstrap_over_proteins": bootstrap_over_proteins(per, n_boot, seed + 1)}
        out["targets"][f"{tgt:g}"] = entry
    return out
