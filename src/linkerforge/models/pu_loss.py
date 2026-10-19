"""Positive-unlabeled (uPU / nnPU) residue loss for the DFL SAM-like head.

Label semantics (matching ``train_dfl_promptable_segmenter.targets``):
``1`` = labeled positive, ``0`` = UNLABELED (a mixture with positive prior
``class_prior``, not a verified negative), ``-1`` (character ``x``) = unknown
and masked out of the risk entirely. Unknown residues are never negatives.

The class prior is a REQUIRED explicit value with no default. It must be
estimated from training-split labels only, never from any benchmark labels.

The numpy implementation is the reference; the torch implementation uses the
same formulas and imports torch lazily so this module (config validation and
the reference risk) is usable where torch is not installed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

import numpy as np

MODES = ("upu", "nnpu")
EMPTY_POLICIES = ("raise", "skip")
_KEYS = {"mode", "class_prior", "beta", "gamma", "on_empty_class"}


@dataclass(frozen=True)
class PUConfig:
    mode: str
    class_prior: float
    beta: float
    gamma: float
    on_empty_class: str

    @classmethod
    def from_dict(cls, data: Mapping) -> "PUConfig":
        """Fail closed: every field required, no unknown fields, strict types."""
        if not isinstance(data, Mapping):
            raise ValueError("PU config must be a mapping")
        missing, extra = _KEYS - set(data), set(data) - _KEYS
        if missing:
            raise ValueError(f"PU config missing required keys: {sorted(missing)}")
        if extra:
            raise ValueError(f"PU config has unknown keys: {sorted(extra)}")
        if data["mode"] not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        if data["on_empty_class"] not in EMPTY_POLICIES:
            raise ValueError(f"on_empty_class must be one of {EMPTY_POLICIES}")
        numbers = {}
        for key in ("class_prior", "beta", "gamma"):
            value = data[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{key} must be an explicit finite number (got {value!r})")
            numbers[key] = float(value)
        if not 0.0 < numbers["class_prior"] < 1.0:
            raise ValueError("class_prior must lie strictly in (0, 1)")
        if numbers["beta"] < 0.0:
            raise ValueError("beta must be >= 0")
        if not 0.0 < numbers["gamma"] <= 1.0:
            raise ValueError("gamma must lie in (0, 1]")
        return cls(data["mode"], numbers["class_prior"], numbers["beta"],
                   numbers["gamma"], data["on_empty_class"])


def _check_targets(residue, valid):
    residue, valid = np.asarray(residue), np.asarray(valid)
    if residue.shape != valid.shape:
        raise ValueError("Targets and valid mask shapes differ")
    if valid.dtype != bool:
        raise ValueError("valid mask must be boolean")
    if not np.isin(residue, (-1, 0, 1)).all():
        raise ValueError("Residue targets must be -1, 0, or 1")
    if (residue[~valid] != -1).any():
        raise ValueError("Padding targets must be unknown (-1)")
    return residue, valid


def _softplus(z):
    return np.logaddexp(0.0, z)


def pu_risk_numpy(logits, residue, valid, config: PUConfig) -> dict:
    """Reference PU risk with logistic loss. Returns floats, no autograd.

    ``objective`` is the value optimized (nnPU switches to -gamma*neg_risk
    when the negative-class risk estimate falls below -beta); ``risk`` is the
    unconstrained uPU risk for monitoring.
    """
    residue, valid = _check_targets(residue, valid)
    logits = np.asarray(logits, dtype=np.float64)
    if logits.shape != residue.shape or not np.isfinite(logits[valid]).all():
        raise ValueError("Logits must match targets and be finite on valid residues")
    pos, unl = valid & (residue == 1), valid & (residue == 0)
    n_pos, n_unl = int(pos.sum()), int(unl.sum())
    if n_pos == 0 or n_unl == 0:
        if config.on_empty_class == "raise":
            raise ValueError(f"PU risk needs positives and unlabeled residues (P={n_pos}, U={n_unl})")
        return {"objective": 0.0, "risk": 0.0, "neg_risk": 0.0, "clamped": False,
                "n_pos": n_pos, "n_unlabeled": n_unl, "skipped": True}
    pos_z, unl_z = logits[pos], logits[unl]
    pi = config.class_prior
    pos_risk = pi * _softplus(-pos_z).mean()
    neg_risk = _softplus(unl_z).mean() - pi * _softplus(pos_z).mean()
    clamped = config.mode == "nnpu" and neg_risk < -config.beta
    objective = -config.gamma * neg_risk if clamped else pos_risk + neg_risk
    return {"objective": float(objective), "risk": float(pos_risk + neg_risk),
            "neg_risk": float(neg_risk), "clamped": bool(clamped),
            "n_pos": n_pos, "n_unlabeled": n_unl, "skipped": False}


def pu_semantic_loss(logits, residue, valid, config: PUConfig) -> dict:
    """Torch version of ``pu_risk_numpy`` (differentiable ``objective``).

    ``logits``/``residue``/``valid`` are (batch, length) tensors; ``x`` and
    padding must already be encoded as -1 in ``residue``.
    """
    import torch
    import torch.nn.functional as F

    if residue.shape != valid.shape or logits.shape != residue.shape or valid.dtype != torch.bool:
        raise ValueError("Targets, logits and boolean valid mask must share a shape")
    if not torch.isin(residue, torch.tensor([-1, 0, 1], device=residue.device)).all():
        raise ValueError("Residue targets must be -1, 0, or 1")
    if (residue[~valid] != -1).any():
        raise ValueError("Padding targets must be unknown (-1)")
    pos, unl = valid & (residue == 1), valid & (residue == 0)
    n_pos, n_unl = int(pos.sum()), int(unl.sum())
    zero = logits.sum() * 0
    if n_pos == 0 or n_unl == 0:
        if config.on_empty_class == "raise":
            raise ValueError(f"PU risk needs positives and unlabeled residues (P={n_pos}, U={n_unl})")
        return {"objective": zero, "risk": zero.detach(), "neg_risk": zero.detach(),
                "clamped": False, "n_pos": n_pos, "n_unlabeled": n_unl, "skipped": True}
    if not torch.isfinite(logits[valid]).all():
        raise ValueError("Logits must be finite on valid residues")
    pos_z, unl_z = logits[pos], logits[unl]
    pi = config.class_prior
    pos_risk = pi * F.softplus(-pos_z).mean()
    neg_risk = F.softplus(unl_z).mean() - pi * F.softplus(pos_z).mean()
    clamped = config.mode == "nnpu" and bool(neg_risk.detach() < -config.beta)
    objective = -config.gamma * neg_risk if clamped else pos_risk + neg_risk
    return {"objective": objective, "risk": (pos_risk + neg_risk).detach(),
            "neg_risk": neg_risk.detach(), "clamped": clamped,
            "n_pos": n_pos, "n_unlabeled": n_unl, "skipped": False}
