"""GPU-first residue linker detector; no CPU training fallback.

Labels: 0=non-linker, 1=independent domain linker, 2=dependent domain linker.
The model predicts residue classes, region boundaries, and sequence presence.
"""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F


AA = "ACDEFGHIKLMNPQRSTVWYX"
AA_TO_ID = {aa: index + 1 for index, aa in enumerate(AA)}


class ResidualDilatedBlock(nn.Module):
    def __init__(self, width: int, dilation: int) -> None:
        super().__init__()
        self.depthwise = nn.Conv1d(width, width, 7, padding=3 * dilation,
                                   dilation=dilation, groups=width)
        self.pointwise = nn.Conv1d(width, width, 1)
        self.norm = nn.BatchNorm1d(width)

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        return hidden + F.gelu(self.norm(self.pointwise(self.depthwise(hidden))))


class LinkerDetector(nn.Module):
    def __init__(self, width: int = 96) -> None:
        super().__init__()
        self.aa_embedding = nn.Embedding(len(AA_TO_ID) + 1, 32, padding_idx=0)
        self.domain_embedding = nn.Embedding(4, 8, padding_idx=0)
        self.input = nn.Conv1d(40, width, 1)
        self.blocks = nn.Sequential(*(ResidualDilatedBlock(width, d)
                                      for d in (1, 2, 4, 8, 16, 32)))
        self.class_head = nn.Conv1d(width, 3, 1)
        self.boundary_head = nn.Conv1d(width, 2, 1)
        self.presence_head = nn.Linear(width, 1)

    def forward(self, amino_acids: torch.Tensor, domain_tokens: torch.Tensor,
                valid_mask: torch.Tensor) -> dict[str, torch.Tensor]:
        if amino_acids.shape != domain_tokens.shape or amino_acids.shape != valid_mask.shape:
            raise ValueError("Residue, domain, and padding tensors must align")
        embedded = torch.cat((self.aa_embedding(amino_acids),
                              self.domain_embedding(domain_tokens)), dim=-1)
        hidden = self.blocks(self.input(embedded.transpose(1, 2)))
        residue_logits = self.class_head(hidden).transpose(1, 2)
        boundary_logits = self.boundary_head(hidden).transpose(1, 2)
        pooled = hidden.masked_fill(~valid_mask.unsqueeze(1), -1e4).amax(dim=-1)
        presence_logit = self.presence_head(pooled).squeeze(-1)
        return {"residue_logits": residue_logits,
                "boundary_logits": boundary_logits,
                "presence_logit": presence_logit}


def detector_loss(output: dict[str, torch.Tensor], labels: torch.Tensor,
                  starts: torch.Tensor, ends: torch.Tensor,
                  valid_mask: torch.Tensor) -> torch.Tensor:
    if not valid_mask.any(dim=1).all():
        raise ValueError("Every sequence needs at least one real residue")
    residue = F.cross_entropy(output["residue_logits"].transpose(1, 2), labels,
                              weight=torch.tensor([1.0, 5.0, 5.0], device=labels.device),
                              ignore_index=-100)
    boundaries = output["boundary_logits"]
    boundary_targets = torch.stack((starts, ends), dim=-1).float()
    boundary_per_position = F.binary_cross_entropy_with_logits(
        boundaries, boundary_targets, reduction="none")
    boundary = (boundary_per_position * valid_mask.unsqueeze(-1)).sum() / (2 * valid_mask.sum())
    presence = (labels > 0).any(dim=1).float()
    presence_loss = F.binary_cross_entropy_with_logits(output["presence_logit"], presence)
    return residue + 0.5 * boundary + 0.5 * presence_loss
