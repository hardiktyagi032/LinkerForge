"""Pre-registered 1D SAM-like ablations for DFL development.

The mechanisms are adaptations of boundary refinement, query-localized
attention, and multi-scale features. None imports image-model weights.
"""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F

from .promptable_linker_segmenter import PromptableLinkerSegmenter


VARIANTS = (
    "boundary_refine", "query_local_attention", "multiscale_features",
    "boundary_plus_query", "boundary_plus_multiscale",
)


class QueryLocalizedAttention(nn.Module):
    """Top-k query support before the ordinary cross-attention operator."""

    def __init__(self, width: int, heads: int = 4, top_k: int = 64) -> None:
        super().__init__()
        self.heads = heads
        self.top_k = top_k
        self.query_key = nn.Linear(width, width, bias=False)
        self.residue_key = nn.Linear(width, width, bias=False)
        self.attention = nn.MultiheadAttention(width, heads, dropout=0.1, batch_first=True)

    def forward(self, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor,
                *, key_padding_mask: torch.Tensor, need_weights: bool = False):
        scores = torch.matmul(self.query_key(query), self.residue_key(key).transpose(1, 2))
        scores = scores.masked_fill(key_padding_mask[:, None, :], -torch.inf)
        keep = torch.zeros_like(scores, dtype=torch.bool)
        top = scores.topk(min(self.top_k, key.shape[1]), dim=-1).indices
        keep.scatter_(2, top, True)
        keep = keep & ~key_padding_mask[:, None, :]
        # Every nonempty right-padded protein retains at least one key/query.
        bias = (scores / (key.shape[-1] ** 0.5)).masked_fill(~keep, -1e4)
        bias = bias.repeat_interleave(self.heads, dim=0)
        return self.attention(query, key, value, attn_mask=bias,
                              need_weights=need_weights)


class SAMLinkerVariant(PromptableLinkerSegmenter):
    def __init__(self, embedding_dim: int, variant: str) -> None:
        if variant not in VARIANTS:
            raise ValueError(f"Unknown variant: {variant}")
        super().__init__(embedding_dim)
        self.variant = variant
        self.use_boundary = variant.startswith("boundary")
        self.use_query = variant in ("query_local_attention", "boundary_plus_query")
        self.use_multiscale = variant in ("multiscale_features", "boundary_plus_multiscale")
        if self.use_query:
            self.query_attention = QueryLocalizedAttention(128)
        if self.use_multiscale:
            self.short_conv = nn.Conv1d(embedding_dim, embedding_dim, 3, padding=1,
                                        groups=embedding_dim)
            self.long_conv = nn.Conv1d(embedding_dim, embedding_dim, 15, padding=7,
                                       groups=embedding_dim)
            self.scale_fusion = nn.Linear(2 * embedding_dim, embedding_dim)
        if self.use_boundary:
            self.boundary_projection = nn.Linear(embedding_dim, 16)
            self.boundary_refiner = nn.Sequential(
                nn.Conv1d(17, 32, 5, padding=2), nn.GELU(),
                nn.Conv1d(32, 1, 3, padding=1))

    def forward(self, residue_embeddings: torch.Tensor, valid_mask: torch.Tensor,
                concept_ids: torch.Tensor, *, exemplar_labels: torch.Tensor | None = None) -> dict:
        source = residue_embeddings.masked_fill(~valid_mask.unsqueeze(-1), 0)
        if self.use_multiscale:
            transposed = source.transpose(1, 2)
            short = F.gelu(self.short_conv(transposed)).transpose(1, 2)
            long = F.gelu(self.long_conv(transposed)).transpose(1, 2)
            source = source + self.scale_fusion(torch.cat((short, long), dim=-1))
            source = source.masked_fill(~valid_mask.unsqueeze(-1), 0)
        output = super().forward(source, valid_mask, concept_ids,
                                 exemplar_labels=exemplar_labels)
        if self.use_boundary:
            semantic = output["semantic_logits"].masked_fill(~valid_mask, 0)
            features = torch.cat((semantic.unsqueeze(-1),
                                  self.boundary_projection(source)), dim=-1)
            correction = self.boundary_refiner(features.transpose(1, 2)).squeeze(1)
            # Refine uncertain positions most; no labels or gold prompts enter.
            uncertainty = torch.exp(-semantic.detach().abs())
            output["semantic_logits"] = (semantic + uncertainty * correction).masked_fill(
                ~valid_mask, -1e4)
        return output
