"""YOLO-style *one-dimensional* protein span segmenter; no YOLO image weights.

Dense center/extent proposals and prototype masks are adapted to residue
positions. Only classes supported by explicit annotations may be trained or
decoded. Coordinates are zero-based half-open internally.
"""

from __future__ import annotations

from collections import Counter
from typing import Sequence

import torch
from torch import nn
from torch.nn import functional as F


class _ConvBlock(nn.Module):
    def __init__(self, width: int, kernel: int):
        super().__init__()
        self.net = nn.Sequential(nn.Conv1d(width, width, kernel, padding=kernel // 2),
                                 nn.BatchNorm1d(width), nn.GELU(),
                                 nn.Conv1d(width, width, kernel, padding=kernel // 2),
                                 nn.BatchNorm1d(width))

    def forward(self, value):
        return F.gelu(value + self.net(value))


class Yolo1DLinkerSegmenter(nn.Module):
    """Multi-scale 1D backbone, dense center head, and instance-mask prototypes.

    The first experiment has one class: disordered_flexible_linker. A future
    multi-class model must provide separately adjudicated labels for each class.
    """

    def __init__(self, embedding_dim: int, *, width: int = 128,
                 prototypes: int = 16, classes: int = 1):
        super().__init__()
        if min(embedding_dim, width, prototypes, classes) < 1:
            raise ValueError("All model dimensions must be positive")
        self.classes = classes
        self.prototypes = prototypes
        self.stem = nn.Conv1d(embedding_dim, width, 1)
        self.fine = _ConvBlock(width, 5)
        self.mid = _ConvBlock(width, 5)
        self.coarse = _ConvBlock(width, 5)
        self.fuse = nn.Sequential(nn.Conv1d(3 * width, width, 1),
                                  nn.BatchNorm1d(width), nn.GELU())
        self.semantic = nn.Conv1d(width, classes, 1)
        self.objectness = nn.Conv1d(width, 1, 1)
        self.extents = nn.Conv1d(width, 2, 1)
        self.prototype_head = nn.Conv1d(width, prototypes, 3, padding=1)
        self.coefficient_head = nn.Conv1d(width, prototypes, 1)

    def forward(self, embeddings: torch.Tensor, valid_mask: torch.Tensor):
        if embeddings.ndim != 3 or valid_mask.shape != embeddings.shape[:2]:
            raise ValueError("Expected embeddings [B,L,D] and valid_mask [B,L]")
        if valid_mask.dtype != torch.bool or not valid_mask.any(dim=1).all():
            raise ValueError("Each protein needs a nonempty boolean valid mask")
        if ((~valid_mask[:, :-1]) & valid_mask[:, 1:]).any():
            raise ValueError("Padding must be a right-hand suffix")
        # ESM can emit nonzero vectors for padded tokens. Zero them before
        # convolutions so trailing padding cannot perturb real boundary sites.
        x = self.stem(embeddings.masked_fill(~valid_mask.unsqueeze(-1), 0).transpose(1, 2))
        fine = self.fine(x)
        mid = self.mid(F.avg_pool1d(fine, 4, stride=4, ceil_mode=True))
        coarse = self.coarse(F.avg_pool1d(mid, 4, stride=4, ceil_mode=True))
        mid_up = F.interpolate(mid, size=x.shape[-1], mode="linear", align_corners=False)
        coarse_up = F.interpolate(coarse, size=x.shape[-1], mode="linear", align_corners=False)
        fused = self.fuse(torch.cat((fine, mid_up, coarse_up), dim=1))
        padding = ~valid_mask
        return {
            "semantic_logits": self.semantic(fused).transpose(1, 2).masked_fill(
                padding.unsqueeze(-1), -1e4),
            "objectness_logits": self.objectness(fused).squeeze(1).masked_fill(padding, -1e4),
            "extent_raw": self.extents(fused).transpose(1, 2),
            "prototypes": self.prototype_head(fused),
            "coefficients": self.coefficient_head(fused).transpose(1, 2),
        }


def yolo1d_loss(outputs: dict[str, torch.Tensor], valid_mask: torch.Tensor,
                residue_targets: torch.Tensor,
                gold_spans: Sequence[Sequence[tuple[int, int]]],
                *, class_id: int = 0) -> dict[str, torch.Tensor]:
    """Train on known 0/1 residues; -1 is unknown, not a negative.

    gold_spans are complete, non-overlapping, zero-based half-open intervals.
    Objectness negatives use only known zero residues, never unknown regions.
    """
    batch, length = valid_mask.shape
    if (residue_targets.shape != (batch, length) or len(gold_spans) != batch
            or not 0 <= class_id < outputs["semantic_logits"].shape[-1]):
        raise ValueError("Target shape or class mismatch")
    if not torch.isin(residue_targets, torch.tensor([-1, 0, 1], device=residue_targets.device)).all():
        raise ValueError("Residue targets must be -1, 0, or 1")
    if (residue_targets[~valid_mask] != -1).any():
        raise ValueError("Padding labels must be unknown")
    known = valid_mask & (residue_targets >= 0)
    zero = outputs["semantic_logits"].sum() * 0
    semantic = (F.binary_cross_entropy_with_logits(
        outputs["semantic_logits"][:, :, class_id][known], residue_targets[known].float())
        if known.any() else zero)
    object_targets = torch.zeros_like(outputs["objectness_logits"])
    object_known = valid_mask & (residue_targets == 0)
    extent_terms, mask_terms = [], []
    for b, spans in enumerate(gold_spans):
        n = int(valid_mask[b].sum())
        last_end = 0
        for start, end in sorted(spans):
            if not last_end <= start < end <= n or not (residue_targets[b, start:end] == 1).all():
                raise ValueError("Spans must be disjoint, in bounds, and labeled positive")
            last_end = end
            center = (start + end - 1) // 2
            object_targets[b, center] = 1
            object_known[b, center] = True
            left_target = center - start + 1
            right_target = end - center
            extents = F.softplus(outputs["extent_raw"][b, center])
            extent_terms.append(F.smooth_l1_loss(extents,
                torch.tensor([left_target, right_target], dtype=extents.dtype, device=extents.device)))
            coefficients = outputs["coefficients"][b, center]
            instance_logits = torch.einsum("p,pl->l", coefficients, outputs["prototypes"][b, :, :n])
            instance_target = torch.zeros(n, dtype=instance_logits.dtype, device=instance_logits.device)
            instance_target[start:end] = 1
            mask_terms.append(F.binary_cross_entropy_with_logits(
                instance_logits[known[b, :n]], instance_target[known[b, :n]]))
    objectness = (F.binary_cross_entropy_with_logits(
        outputs["objectness_logits"][object_known], object_targets[object_known])
        if object_known.any() else zero)
    extent = torch.stack(extent_terms).mean() if extent_terms else zero
    instance = torch.stack(mask_terms).mean() if mask_terms else zero
    return {"total": semantic + 0.5 * objectness + 0.1 * extent + 0.25 * instance,
            "semantic": semantic, "objectness": objectness, "extent": extent,
            "instance_mask": instance}


@torch.no_grad()
def decode_yolo1d(outputs: dict[str, torch.Tensor], sequences: Sequence[str],
                  valid_mask: torch.Tensor, *, class_name: str = "disordered_flexible_linker",
                  score_threshold: float = 0.5, top_k: int = 32,
                  min_length: int = 4, max_length: int = 200,
                  nms_iou: float = 0.5) -> list[dict]:
    """Decode dense proposals with 1D IoU NMS; scores are uncalibrated."""
    if not 0 <= score_threshold <= 1 or top_k < 1 or not 0 < nms_iou <= 1:
        raise ValueError("Invalid decoder settings")
    if len(sequences) != valid_mask.shape[0]:
        raise ValueError("Sequence count mismatch")
    results = []
    for b, sequence in enumerate(sequences):
        n = int(valid_mask[b].sum())
        if len(sequence) != n or set(sequence) - set("ACDEFGHIKLMNPQRSTVWY"):
            raise ValueError("Expected canonical sequence matching valid mask")
        semantic = outputs["semantic_logits"][b, :n, 0].sigmoid()
        objectness = outputs["objectness_logits"][b, :n].sigmoid()
        scores = semantic * objectness
        candidates = []
        for center in scores.topk(min(top_k, n)).indices.tolist():
            score = float(scores[center])
            if score < score_threshold:
                continue
            left, right = F.softplus(outputs["extent_raw"][b, center]).tolist()
            start = max(0, center - round(left) + 1)
            end = min(n, center + round(right))
            if not min_length <= end - start <= max_length:
                continue
            candidates.append((score, start, end, center))
        candidates.sort(key=lambda item: (-item[0], item[1]))
        kept = []
        for score, start, end, center in candidates:
            def iou(prior):
                intersection = max(0, min(end, prior[2]) - max(start, prior[1]))
                union = max(end, prior[2]) - min(start, prior[1])
                return intersection / union
            if any(iou(prior) >= nms_iou for prior in kept):
                continue
            kept.append((score, start, end, center))
        spans = []
        for score, start, end, center in kept:
            peptide = sequence[start:end]
            coefficients = outputs["coefficients"][b, center]
            mask_scores = torch.einsum("p,pl->l", coefficients,
                                       outputs["prototypes"][b, :, :n]).sigmoid()
            spans.append({"start_1based": start + 1, "end_1based": end,
                          "sequence": peptide, "length": len(peptide),
                          "composition_counts": dict(sorted(Counter(peptide).items())),
                          "score_uncalibrated": score,
                          "instance_mask_scores": mask_scores.tolist()})
        results.append({"class": class_name, "status": "proposed_spans" if spans else "abstained",
                        "spans": spans, "residue_scores": semantic.tolist()})
    return results
