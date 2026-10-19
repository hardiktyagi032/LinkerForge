"""Experimental bounded-span DFL head over frozen per-residue embeddings.

Candidate intervals use zero-based half-open coordinates. This is a small
segmental adaptation, not a claim of novel biology or validated performance.
"""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F


class BoundedSpanLinkerSegmenter(nn.Module):
    def __init__(self, embedding_dim: int, width: int = 128, max_span: int = 64) -> None:
        super().__init__()
        if embedding_dim < 1 or width < 1 or max_span < 1:
            raise ValueError("Invalid dimensions")
        self.embedding_dim = embedding_dim
        self.max_span = max_span
        self.project = nn.Sequential(nn.Linear(embedding_dim, width), nn.GELU())
        self.context = nn.Sequential(nn.Conv1d(width, width, 5, padding=2), nn.GELU(),
                                     nn.Conv1d(width, width, 5, padding=2), nn.GELU())
        self.semantic = nn.Linear(width, 1)
        self.length_embedding = nn.Embedding(max_span, width)
        self.span_score = nn.Sequential(nn.Linear(4 * width, width), nn.GELU(),
                                        nn.Linear(width, 1))

    def forward(self, residue_embeddings: torch.Tensor, valid_mask: torch.Tensor) -> dict:
        if residue_embeddings.ndim != 3 or residue_embeddings.shape[-1] != self.embedding_dim:
            raise ValueError("Expected embeddings [batch,length,embedding_dim]")
        batch, length, _ = residue_embeddings.shape
        if valid_mask.shape != (batch, length) or valid_mask.dtype != torch.bool:
            raise ValueError("Expected boolean valid mask")
        if not valid_mask.any(1).all() or ((~valid_mask[:, :-1]) & valid_mask[:, 1:]).any():
            raise ValueError("Validity must be nonempty right-padded sequences")
        if not torch.isfinite(residue_embeddings).all():
            raise ValueError("Nonfinite embeddings")
        hidden = self.project(residue_embeddings)
        hidden = hidden + self.context(hidden.transpose(1, 2)).transpose(1, 2)
        hidden = hidden.masked_fill(~valid_mask.unsqueeze(-1), 0)
        semantic = self.semantic(hidden).squeeze(-1).masked_fill(~valid_mask, -1e4)
        prefix = F.pad(hidden.cumsum(1), (0, 0, 1, 0))
        candidates = []
        for span_len in range(1, min(self.max_span, length) + 1):
            starts = hidden[:, :length - span_len + 1]
            ends = hidden[:, span_len - 1:]
            interior = (prefix[:, span_len:] - prefix[:, :-span_len]) / span_len
            length_feature = self.length_embedding.weight[span_len - 1].expand_as(starts)
            features = torch.cat((starts, ends, interior, length_feature), dim=-1)
            logits = self.span_score(features).squeeze(-1)
            logits = logits.masked_fill(~valid_mask[:, span_len - 1:], -1e4)
            candidates.append(logits)
        return {"semantic_logits": semantic, "span_logits": candidates}


def bounded_span_loss(output: dict, valid_mask: torch.Tensor, residue: torch.Tensor,
                      spans: list[list[tuple[int, int]]]) -> torch.Tensor:
    known = valid_mask & (residue >= 0)
    if not known.any():
        # Weakly annotated windows can contain only unknown residues. They
        # supply no supervision, but must not abort an otherwise valid batch.
        return output["semantic_logits"].sum() * 0
    semantic = F.binary_cross_entropy_with_logits(output["semantic_logits"][known],
                                                    residue[known].float())
    positive, negative = [], []
    max_span = len(output["span_logits"])
    for b, gold in enumerate(spans):
        for start, end in gold:
            if not 0 <= start < end <= int(valid_mask[b].sum()):
                raise ValueError("Invalid gold span")
            if not bool((residue[b, start:end] == 1).all()):
                raise ValueError("Gold span includes nonpositive residues")
            if end - start <= max_span:
                positive.append(output["span_logits"][end - start - 1][b, start])
    zero = ((residue == 0) & valid_mask).long()
    prefix_zero = F.pad(zero.cumsum(1), (1, 0))
    for span_len, logits in enumerate(output["span_logits"], start=1):
        zero_count = prefix_zero[:, span_len:] - prefix_zero[:, :-span_len]
        complete_negative = (zero_count == span_len) & valid_mask[:, span_len - 1:]
        if complete_negative.any():
            negative.append(logits[complete_negative])
    if not positive or not negative:
        return semantic
    pos = torch.stack(positive)
    neg = torch.cat(negative)
    # Keep the hardest negatives and balance their contribution with positives.
    neg = neg.topk(min(neg.numel(), max(32, 4 * len(positive)))).values
    return semantic + 0.25 * (F.softplus(-pos).mean() + F.softplus(neg).mean())
