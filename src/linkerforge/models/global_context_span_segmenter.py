"""Experimental global-context encoder followed by bounded interval scoring."""

import torch
from torch import nn

from .coupled_bounded_span_segmenter import CoupledBoundedSpanSegmenter
from .promptable_linker_segmenter import _positional_encoding


class GlobalContextSpanSegmenter(nn.Module):
    def __init__(self, embedding_dim: int, *, width: int = 128,
                 max_span: int = 192, layers: int = 2, heads: int = 4) -> None:
        super().__init__()
        if embedding_dim < 1 or width % heads or layers < 1:
            raise ValueError("Invalid context dimensions")
        self.embedding_dim = embedding_dim
        self.input_projection = nn.Linear(embedding_dim, width)
        block = nn.TransformerEncoderLayer(
            d_model=width, nhead=heads, dim_feedforward=2 * width,
            dropout=0.1, activation="gelu", batch_first=True, norm_first=True)
        self.global_encoder = nn.TransformerEncoder(block, num_layers=layers,
                                                     enable_nested_tensor=False)
        self.interval_head = CoupledBoundedSpanSegmenter(width, width=width,
                                                          max_span=max_span)

    def forward(self, residue_embeddings: torch.Tensor, valid_mask: torch.Tensor) -> dict:
        if residue_embeddings.ndim != 3 or residue_embeddings.shape[-1] != self.embedding_dim:
            raise ValueError("Expected [batch,length,embedding_dim]")
        if valid_mask.shape != residue_embeddings.shape[:2] or valid_mask.dtype != torch.bool:
            raise ValueError("Expected boolean validity mask")
        if not valid_mask.any(1).all() or ((~valid_mask[:, :-1]) & valid_mask[:, 1:]).any():
            raise ValueError("Validity must be nonempty right-padded sequences")
        if not torch.isfinite(residue_embeddings).all():
            raise ValueError("Nonfinite embeddings")
        hidden = self.input_projection(residue_embeddings)
        hidden = hidden + _positional_encoding(hidden.shape[1], hidden.shape[2],
                                               hidden.device, hidden.dtype)[None]
        hidden = self.global_encoder(hidden, src_key_padding_mask=~valid_mask)
        hidden = hidden.masked_fill(~valid_mask.unsqueeze(-1), 0)
        return self.interval_head(hidden, valid_mask)
