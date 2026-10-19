"""Rigid-versus-flexible classification from composition.

This is the one axis of the two that is a genuine learning problem, and the
model is a plain L2-regularised logistic regression on six compositional
features.  It is deliberately the smallest model that can express the published
composition rule, because the labelled set is tiny: anything with more capacity
would report a better number without being better.

The evaluation here is leave-one-out plus a label-permutation null.  With a set
this size those are the only honest statements available: a single held-out
split would be one or two sequences wide, and a reported calibration curve would
be noise.  :func:`leave_one_out_report` therefore returns the out-of-fold
probabilities themselves so a reader can see the spread rather than trusting a
summary.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .features import featurise, feature_names

# "rigid" is the positive class.
POSITIVE_LABEL = "rigid"
NEGATIVE_LABEL = "flexible"


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    expz = math.exp(z)
    return expz / (1.0 + expz)


@dataclass
class RigidityModel:
    weights: List[float]
    bias: float
    feature_names: List[str]
    l2: float
    n_train: int

    def decision(self, sequence: str) -> float:
        x = featurise(sequence)
        return self.bias + sum(w * xi for w, xi in zip(self.weights, x))

    def predict_proba(self, sequence: str) -> float:
        """Probability that ``sequence`` is rigid."""
        return _sigmoid(self.decision(sequence))

    def predict(self, sequence: str) -> str:
        return POSITIVE_LABEL if self.predict_proba(sequence) >= 0.5 else NEGATIVE_LABEL

    def coefficients(self) -> Dict[str, float]:
        return dict(zip(self.feature_names, self.weights))


def fit_rigidity_model(
    sequences: Sequence[str],
    labels: Sequence[str],
    l2: float = 1.0,
    learning_rate: float = 0.5,
    epochs: int = 20000,
) -> RigidityModel:
    """Fit logistic regression by full-batch gradient descent.

    ``l2`` defaults to 1.0, which is strong for six features.  That is on
    purpose: with a handful of examples the regularised solution is the one that
    does not run its weights off to infinity on a separable set.
    """
    if len(sequences) != len(labels):
        raise ValueError("sequences and labels differ in length")
    if not sequences:
        raise ValueError("no training data")
    unknown = sorted(set(labels) - {POSITIVE_LABEL, NEGATIVE_LABEL})
    if unknown:
        raise ValueError(
            "labels must be %r or %r; got %s"
            % (POSITIVE_LABEL, NEGATIVE_LABEL, ", ".join(unknown))
        )

    names = feature_names()
    xs = [featurise(s) for s in sequences]
    ys = [1.0 if label == POSITIVE_LABEL else 0.0 for label in labels]
    n = len(xs)
    dim = len(names)

    weights = [0.0] * dim
    bias = 0.0

    for _ in range(epochs):
        grad_w = [0.0] * dim
        grad_b = 0.0
        for x, y in zip(xs, ys):
            p = _sigmoid(bias + sum(w * xi for w, xi in zip(weights, x)))
            err = p - y
            grad_b += err
            for j in range(dim):
                grad_w[j] += err * x[j]
        grad_b /= n
        for j in range(dim):
            grad_w[j] = grad_w[j] / n + l2 * weights[j] / n
        bias -= learning_rate * grad_b
        for j in range(dim):
            weights[j] -= learning_rate * grad_w[j]

    return RigidityModel(
        weights=weights, bias=bias, feature_names=names, l2=l2, n_train=n
    )


@dataclass
class LeaveOneOutReport:
    n: int
    n_rigid: int
    n_flexible: int
    accuracy: float
    majority_baseline: float
    out_of_fold: List[Dict[str, object]]
    permutation_p: Optional[float]
    permutation_rounds: int
    separable_in_sample: bool
    interpretation: str


def _loo_accuracy(
    sequences: Sequence[str], labels: Sequence[str], l2: float, epochs: int
) -> Tuple[float, List[Dict[str, object]]]:
    rows: List[Dict[str, object]] = []
    correct = 0
    for i in range(len(sequences)):
        train_x = [s for j, s in enumerate(sequences) if j != i]
        train_y = [y for j, y in enumerate(labels) if j != i]
        if len(set(train_y)) < 2:
            # Cannot fit a two-class model; record as an abstention, not a hit.
            rows.append(
                {
                    "index": i,
                    "sequence": sequences[i],
                    "true": labels[i],
                    "predicted": None,
                    "p_rigid": None,
                    "correct": False,
                    "note": "fold left only one class in training",
                }
            )
            continue
        model = fit_rigidity_model(train_x, train_y, l2=l2, epochs=epochs)
        p = model.predict_proba(sequences[i])
        pred = POSITIVE_LABEL if p >= 0.5 else NEGATIVE_LABEL
        hit = pred == labels[i]
        correct += int(hit)
        rows.append(
            {
                "index": i,
                "sequence": sequences[i],
                "true": labels[i],
                "predicted": pred,
                "p_rigid": round(p, 4),
                "correct": hit,
                "note": None,
            }
        )
    return correct / float(len(sequences)), rows


def leave_one_out_report(
    sequences: Sequence[str],
    labels: Sequence[str],
    l2: float = 1.0,
    epochs: int = 4000,
    permutation_rounds: int = 200,
    seed: int = 20261017,
) -> LeaveOneOutReport:
    """Leave-one-out accuracy with a label-permutation null."""
    accuracy, rows = _loo_accuracy(sequences, labels, l2=l2, epochs=epochs)

    n = len(sequences)
    n_rigid = sum(1 for label in labels if label == POSITIVE_LABEL)
    n_flexible = n - n_rigid
    majority = max(n_rigid, n_flexible) / float(n)

    permutation_p: Optional[float] = None
    if permutation_rounds > 0 and n_rigid and n_flexible:
        rng = random.Random(seed)
        shuffled_labels = list(labels)
        at_least = 0
        for _ in range(permutation_rounds):
            rng.shuffle(shuffled_labels)
            perm_accuracy, _ = _loo_accuracy(
                sequences, shuffled_labels, l2=l2, epochs=epochs
            )
            if perm_accuracy >= accuracy:
                at_least += 1
        permutation_p = (at_least + 1) / float(permutation_rounds + 1)

    full = fit_rigidity_model(sequences, labels, l2=l2, epochs=epochs)
    separable = all(full.predict(s) == y for s, y in zip(sequences, labels))

    if accuracy >= 0.999 and separable:
        interpretation = (
            "The two classes are linearly separable in composition space and "
            "leave-one-out is perfect. Read this as confirming that the "
            "published composition rule holds on the curated entries, NOT as "
            "evidence that a learned model adds anything: a hand-written rule "
            "on the same features would score the same. The number says the "
            "task is easy, not that the model is good."
        )
    elif permutation_p is not None and _permutation_significant(permutation_p):
        interpretation = (
            "Leave-one-out beats the majority baseline and the permutation "
            "null, so composition carries real signal on this axis, but the "
            "labelled set is too small to estimate calibration."
        )
    else:
        interpretation = (
            "Leave-one-out does not clearly beat the permutation null. On a "
            "set this size that is a statement about the sample, not a refutation "
            "of the composition rule."
        )

    return LeaveOneOutReport(
        n=n,
        n_rigid=n_rigid,
        n_flexible=n_flexible,
        accuracy=accuracy,
        majority_baseline=majority,
        out_of_fold=rows,
        permutation_p=permutation_p,
        permutation_rounds=permutation_rounds,
        separable_in_sample=separable,
        interpretation=interpretation,
    )


def _permutation_significant(p: float) -> bool:
    return p <= 0.05
