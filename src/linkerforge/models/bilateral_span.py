"""Sequence-only bilateral linker interval scorer (untrained research module).

Coordinates are zero-based, half-open. This module consumes residue embeddings;
it never consumes reference labels or native structure as prediction features.
"""

from __future__ import annotations

import math

import torch
from torch import nn


def propose_intervals(
    start_logits: torch.Tensor,
    end_logits: torch.Tensor,
    *,
    min_length: int = 8,
    max_length: int = 100,
    top_boundaries: int = 64,
    max_candidates: int = 512,
    forced_intervals: tuple[tuple[int, int], ...] = (),
) -> torch.Tensor:
    """Select bounded [start,end) spans; always retain valid forced positives.

    A forced span is a training candidate only. Calling inference must pass an
    empty `forced_intervals`, so reference coordinates cannot leak into input.
    """
    if start_logits.ndim != 1 or end_logits.shape != start_logits.shape:
        raise ValueError("Boundary logits must be matching 1-D tensors")
    length = start_logits.numel()
    if not (1 <= min_length <= max_length and top_boundaries >= 1 and max_candidates >= 1):
        raise ValueError("Invalid proposal bounds")
    count = min(length, top_boundaries)
    starts = torch.topk(start_logits, count).indices.tolist()
    ends = torch.topk(end_logits, count).indices.tolist()
    ranked = []
    for start in starts:
        for end_index in ends:
            end = end_index + 1
            if min_length <= end - start <= max_length:
                ranked.append((float(start_logits[start] + end_logits[end_index]), start, end))
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    chosen = {(start, end) for _, start, end in ranked[:max_candidates]}
    for start, end in forced_intervals:
        if not (0 <= start < end <= length and min_length <= end - start <= max_length):
            raise ValueError("Invalid forced interval")
        chosen.add((start, end))
    if not chosen:
        return torch.empty((0, 2), dtype=torch.long, device=start_logits.device)
    return torch.tensor(sorted(chosen), dtype=torch.long, device=start_logits.device)


class BilateralSpanScorer(nn.Module):
    """Scores a candidate interior against its independent left/right flanks."""

    def __init__(self, embedding_dim: int, width: int = 64, flank_width: int = 32, min_flank: int = 8):
        super().__init__()
        if embedding_dim < 1 or width < 1 or flank_width < min_flank or min_flank < 1:
            raise ValueError("Invalid scorer dimensions")
        self.flank_width = flank_width
        self.min_flank = min_flank
        self.project = nn.Linear(embedding_dim, width)
        self.boundaries = nn.Linear(width, 2)
        self.score = nn.Sequential(nn.Linear(7 * width + 1, width), nn.GELU(), nn.Linear(width, 1))
        self.null_logit = nn.Parameter(torch.zeros(()))

    def forward(self, embeddings: torch.Tensor, intervals: torch.Tensor) -> dict[str, torch.Tensor]:
        if embeddings.ndim != 2 or intervals.ndim != 2 or intervals.shape[1] != 2:
            raise ValueError("Expected embeddings [L,H] and intervals [N,2]")
        length = embeddings.shape[0]
        if length == 0:
            raise ValueError("Empty protein")
        x = self.project(embeddings)
        boundary_logits = self.boundaries(x)
        values = []
        eligible = []
        for start_tensor, end_tensor in intervals:
            start, end = int(start_tensor), int(end_tensor)
            if not (0 <= start < end <= length):
                raise ValueError("Interval outside protein")
            left = x[max(0, start - self.flank_width):start]
            middle = x[start:end]
            right = x[end:min(length, end + self.flank_width)]
            has_flanks = len(left) >= self.min_flank and len(right) >= self.min_flank
            eligible.append(has_flanks)
            # Zero placeholders retain a finite diagnostic score for terminal
            # candidates; the decoder must reject ineligible spans.
            left_mean = left.mean(0) if len(left) else torch.zeros_like(x[0])
            right_mean = right.mean(0) if len(right) else torch.zeros_like(x[0])
            center = middle.mean(0)
            variation = middle.var(0, unbiased=False).sqrt()
            features = torch.cat((left_mean, center, right_mean,
                                  (left_mean - right_mean).abs(),
                                  (left_mean - center).abs(),
                                  (center - right_mean).abs(), variation,
                                  x.new_tensor([math.log1p(end - start)])))
            values.append(self.score(features).squeeze(0))
        interval_logits = torch.stack(values) if values else x.new_empty((0,))
        return {"interval_logits": interval_logits,
                "eligible": torch.tensor(eligible, dtype=torch.bool, device=x.device),
                "start_logits": boundary_logits[:, 0],
                "end_logits": boundary_logits[:, 1],
                "null_logit": self.null_logit}
