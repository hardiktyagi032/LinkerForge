"""Ensemble of already-trained DFL checkpoints scored from saved per-residue scores.

Each member is one ``.npz`` written by :func:`save_member` after scoring a
checkpoint on protected development. Members are read ONE AT A TIME and folded
into running accumulators (sum of probabilities, sum of logits, Welford
mean/M2 of probabilities), so memory is O(residues), never O(members x residues)
and no model or GPU is touched here.

Binding rules enforced: the split must be the protected development split (any
other split label, including anything CAID3, is refused); all members must
share identical protein ids, order, label strings and lengths; seeds must be
distinct; at least ``min_members`` (default 3) members are required.
Unknown residues (label ``x``) are never negatives: they are dropped from every
metric.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

REQUIRED_SPLIT = "protected_development"
EPS = 1e-7


class EnsembleError(ValueError):
    """Raised on any inconsistency; the evaluation fails closed."""


def save_member(path, *, protein_ids, labels, scores, seed, arch, split=REQUIRED_SPLIT,
                checkpoint_sha256="", logits=None):
    """Save one member. ``labels``/``scores``: per-protein strings of 0/1/x and float arrays."""
    if not (len(protein_ids) == len(labels) == len(scores)):
        raise EnsembleError("protein_ids, labels and scores must align")
    lengths = np.array([len(s) for s in labels], dtype=np.int64)
    for text, array in zip(labels, scores):
        if len(array) != len(text) or set(text) - set("01x"):
            raise EnsembleError("score/label length mismatch or invalid label character")
    flat = np.concatenate([np.asarray(a, dtype=np.float64) for a in scores]) if len(scores) else np.zeros(0)
    arrays = {"protein_ids": np.asarray(protein_ids, dtype=str), "lengths": lengths,
              "labels": np.asarray("".join(labels)), "probs": flat,
              "seed": np.asarray(int(seed)), "arch": np.asarray(arch), "split": np.asarray(split),
              "checkpoint_sha256": np.asarray(checkpoint_sha256)}
    if logits is not None:
        arrays["logits"] = np.concatenate([np.asarray(a, dtype=np.float64) for a in logits])
    np.savez(path, **arrays)


def load_member(path) -> dict:
    with np.load(Path(path), allow_pickle=False) as z:
        member = {k: z[k] for k in z.files}
    split = str(member["split"])
    if split != REQUIRED_SPLIT:
        raise EnsembleError(f"{path}: split {split!r} is not {REQUIRED_SPLIT!r}; "
                            "benchmark/CAID3 or other splits are refused")
    probs = member["probs"]
    if not np.isfinite(probs).all() or probs.min(initial=0) < 0 or probs.max(initial=0) > 1:
        raise EnsembleError(f"{path}: probabilities must be finite and in [0, 1]")
    labels = str(member["labels"])
    if int(member["lengths"].sum()) != len(labels) or len(labels) != len(probs):
        raise EnsembleError(f"{path}: lengths, labels and scores disagree")
    if set(labels) - set("01x"):
        raise EnsembleError(f"{path}: invalid label characters")
    if "logits" in member and (len(member["logits"]) != len(probs) or not np.isfinite(member["logits"]).all()):
        raise EnsembleError(f"{path}: invalid logits")
    member["path"] = str(path)
    return member


def _logit(p):
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def stream_ensemble(paths, *, min_members: int = 3) -> dict:
    """Fold members sequentially. Returns reference data + combined scores."""
    paths = list(paths)
    if len(paths) < min_members:
        raise EnsembleError(f"need at least {min_members} members, got {len(paths)}")
    ref = None
    seeds, hashes = [], []
    n = 0
    sum_p = sum_l = mean = m2 = None
    for path in paths:
        m = load_member(path)
        if ref is None:
            ref = {k: m[k] for k in ("protein_ids", "lengths", "labels", "arch")}
            sum_p = np.zeros(len(m["probs"]))
            sum_l = np.zeros_like(sum_p)
            mean = np.zeros_like(sum_p)
            m2 = np.zeros_like(sum_p)
        else:
            if (list(m["protein_ids"]) != list(ref["protein_ids"]) or
                    not np.array_equal(m["lengths"], ref["lengths"]) or
                    str(m["labels"]) != str(ref["labels"])):
                raise EnsembleError(f"{path}: protein ids/order/lengths/labels differ from first member")
            if str(m["arch"]) != str(ref["arch"]):
                raise EnsembleError(f"{path}: architecture differs (matched members only)")
        seeds.append(int(m["seed"]))
        hashes.append(str(m["checkpoint_sha256"]))
        p = m["probs"]
        l = m["logits"] if "logits" in m else _logit(p)
        n += 1
        sum_p += p
        sum_l += l
        delta = p - mean
        mean += delta / n
        m2 += delta * (p - mean)
        del m
    if len(set(seeds)) != len(seeds):
        raise EnsembleError(f"duplicate seeds among members: {seeds}")
    return {"protein_ids": [str(x) for x in ref["protein_ids"]], "lengths": ref["lengths"],
            "labels": str(ref["labels"]), "n_members": n, "seeds": seeds,
            "checkpoint_sha256": hashes, "arch": str(ref["arch"]),
            "mean_prob": sum_p / n, "mean_logit_prob": _sigmoid(sum_l / n),
            "variance": m2 / n}  # population variance across members, per residue


def metrics(labels: str, lengths, scores, *, min_tp: int = 50) -> dict:
    """APS, AUROC, Fmax, recall@precision>=.90/.99 and no-positive proxy specificity.

    Semantics follow the repo's development evaluators: unknown ('x') residues
    dropped; exact score ties handled by evaluating only at distinct thresholds;
    recall at precision needs >= ``min_tp`` true positives; proxy specificity is
    the fraction of proteins without any '1' whose max known score is below the
    precision>=0.90 threshold (None when no threshold or no such protein).
    """
    lab = np.frombuffer(labels.encode("ascii"), dtype=np.uint8)
    known = lab != ord("x")
    truth = (lab[known] == ord("1")).astype(np.int64)
    allscores = np.asarray(scores, dtype=np.float64)
    s = allscores[known]
    pos = int(truth.sum())
    neg = int(len(truth) - pos)
    if pos == 0 or neg == 0:
        raise EnsembleError("metrics need positive and negative known residues")
    order = np.argsort(-s, kind="stable")
    ss = s[order]
    t = truth[order]
    tp = np.cumsum(t)
    fp = np.cumsum(1 - t)
    ends = np.r_[ss[1:] != ss[:-1], True]
    tp_e, fp_e, thr = tp[ends], fp[ends], ss[ends]
    precision = tp_e / (tp_e + fp_e)
    recall = tp_e / pos
    aps = float(np.sum(np.diff(np.r_[0.0, recall]) * precision))
    tpr = np.r_[0.0, tp_e / pos]
    fpr = np.r_[0.0, fp_e / neg]
    auroc = float(np.sum(np.diff(fpr) * (tpr[1:] + tpr[:-1]) / 2))
    f1 = 2 * precision * recall / (precision + recall)
    best = int(np.argmax(f1))
    out = {"aps": aps, "auroc": auroc, "fmax": float(f1[best]), "fmax_threshold": float(thr[best]),
           "positive_residues": pos, "negative_residues": neg}
    point90 = None
    for target in (0.90, 0.99):
        ok = np.flatnonzero((precision >= target) & (tp_e >= min_tp))
        if len(ok):
            i = int(ok[np.argmax(tp_e[ok])])
            row = {"threshold": float(thr[i]), "recall": float(recall[i]), "precision": float(precision[i]),
                   "true_positives": int(tp_e[i]), "false_positives": int(fp_e[i])}
        else:
            row = {"threshold": None, "recall": 0.0, "precision": None,
                   "true_positives": 0, "false_positives": 0}
        out[f"recall_at_precision_{int(round(target * 100))}"] = row
        if target == 0.90:
            point90 = row
    offsets = np.r_[0, np.cumsum(lengths)]
    total = clean = 0
    thr90 = point90["threshold"]
    for a, b in zip(offsets[:-1], offsets[1:]):
        seg = labels[a:b]
        if "1" in seg:
            continue
        total += 1
        vals = [x for x, c in zip(allscores[a:b], seg) if c != "x"]
        if thr90 is not None and max(vals, default=0.0) < thr90:
            clean += 1
    out["no_positive_proxy"] = {"proteins": total, "clean": clean,
                                "specificity": (clean / total if total and thr90 is not None else None),
                                "note": "partial-label proxy, not verified no-linker specificity"}
    return out


def evaluate_ensemble(paths, *, min_members: int = 3, min_tp: int = 50) -> dict:
    ens = stream_ensemble(paths, min_members=min_members)
    result = {"status": "protected_development_only", "n_members": ens["n_members"],
              "seeds": ens["seeds"], "checkpoint_sha256": ens["checkpoint_sha256"],
              "arch": ens["arch"], "split": REQUIRED_SPLIT}
    for name, key in (("mean_probability", "mean_prob"), ("mean_logit", "mean_logit_prob")):
        result[name] = metrics(ens["labels"], ens["lengths"], ens[key], min_tp=min_tp)
    lab = np.frombuffer(ens["labels"].encode("ascii"), dtype=np.uint8)
    known = lab != ord("x")
    truth = lab[known] == ord("1")
    var = ens["variance"][known]
    result["uncertainty"] = {
        "definition": "population variance of member probabilities per residue, known residues only",
        "mean_variance_known_residues": float(var.mean()),
        "mean_variance_positive": float(var[truth].mean()),
        "mean_variance_negative": float(var[~truth].mean()),
        "max_variance": float(var.max())}
    result["mean_prob_sha256"] = hashlib.sha256(ens["mean_prob"].tobytes()).hexdigest()
    return result
