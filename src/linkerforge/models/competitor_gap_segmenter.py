"""Five fail-closed, competitor-inspired DFL feature ablations.

These are original experimental adaptations, not reproductions of any
published predictor. External feature/function modes require separately
provenanced, aligned inputs and cannot silently fall back to zeros.
"""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F

from .promptable_linker_segmenter import PromptableLinkerSegmenter

VARIANTS = ("global_context", "dilated_local", "predicted_disorder_gate",
            "external_representation", "function_interaction")


class CompetitorGapSegmenter(PromptableLinkerSegmenter):
    def __init__(self, embedding_dim: int, variant: str, *, external_dim: int | None = None,
                 function_count: int | None = None) -> None:
        if variant not in VARIANTS:
            raise ValueError(f"Unknown variant: {variant}")
        super().__init__(embedding_dim)
        self.variant = variant
        self.stage = "dfl"
        if variant == "global_context":
            self.global_fusion = nn.Linear(embedding_dim * 2, embedding_dim)
        elif variant == "dilated_local":
            self.local_short = nn.Conv1d(embedding_dim, embedding_dim, 3, padding=2,
                                         dilation=2, groups=embedding_dim)
            self.local_long = nn.Conv1d(embedding_dim, embedding_dim, 3, padding=8,
                                        dilation=8, groups=embedding_dim)
            self.local_fusion = nn.Linear(embedding_dim * 2, embedding_dim)
        elif variant == "predicted_disorder_gate":
            self.disorder_head = nn.Sequential(nn.Linear(embedding_dim, 64), nn.GELU(),
                                               nn.Linear(64, 1))
            self.disorder_scale = nn.Parameter(torch.zeros(()))
        elif variant == "external_representation":
            if external_dim is None or external_dim < 1:
                raise ValueError("Versioned external residue feature dimension is required")
            self.external_dim = external_dim
            self.external_fusion = nn.Linear(embedding_dim + external_dim, embedding_dim)
        elif variant == "function_interaction":
            if function_count is None or function_count < 2:
                raise ValueError("At least two ontology-aligned function channels are required")
            self.function_count = function_count
            self.function_graph = nn.Linear(function_count, function_count, bias=False)
            self.function_fusion = nn.Linear(embedding_dim + function_count, embedding_dim)

    def forward(self, residue_embeddings: torch.Tensor, valid_mask: torch.Tensor,
                concept_ids: torch.Tensor, *, exemplar_labels: torch.Tensor | None = None,
                external_features: torch.Tensor | None = None,
                function_scores: torch.Tensor | None = None) -> dict[str, torch.Tensor]:
        source = residue_embeddings.masked_fill(~valid_mask.unsqueeze(-1), 0)
        if self.variant == "global_context":
            pooled = source.sum(1, keepdim=True) / valid_mask.sum(1, keepdim=True).clamp_min(1).unsqueeze(-1)
            context = pooled.expand_as(source)
            source = source + self.global_fusion(torch.cat((source, context), -1))
        elif self.variant == "dilated_local":
            transposed = source.transpose(1, 2)
            short = F.gelu(self.local_short(transposed)).transpose(1, 2)
            long = F.gelu(self.local_long(transposed)).transpose(1, 2)
            source = source + self.local_fusion(torch.cat((short, long), -1))
        elif self.variant == "external_representation":
            if external_features is None or external_features.shape != (*source.shape[:2], self.external_dim):
                raise ValueError("Aligned, versioned external residue features are required")
            if not torch.isfinite(external_features).all():
                raise ValueError("Nonfinite external features")
            source = source + self.external_fusion(torch.cat((source, external_features), -1))
        elif self.variant == "function_interaction":
            if function_scores is None or function_scores.shape != (*source.shape[:2], self.function_count):
                raise ValueError("Aligned predicted function scores are required")
            if not torch.isfinite(function_scores).all():
                raise ValueError("Nonfinite function scores")
            interactions = torch.sigmoid(self.function_graph(function_scores))
            source = source + self.function_fusion(torch.cat((source, interactions), -1))
        source = source.masked_fill(~valid_mask.unsqueeze(-1), 0)
        output = super().forward(source, valid_mask, concept_ids, exemplar_labels=exemplar_labels)
        if self.variant == "predicted_disorder_gate":
            disorder = self.disorder_head(source).squeeze(-1)
            output["predicted_disorder_logits"] = disorder.masked_fill(~valid_mask, -1e4)
            if self.stage == "auxiliary_idr":
                output["semantic_logits"] = output["predicted_disorder_logits"]
            elif self.stage == "dfl":
                output["semantic_logits"] = (output["semantic_logits"] +
                                             self.disorder_scale * torch.tanh(disorder)).masked_fill(
                                                 ~valid_mask, -1e4)
            else:
                raise ValueError("Unknown training stage")
        return output
