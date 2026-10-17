"""SAM-3-inspired, *untrained* promptable sequence-span detector.

This adapts presence/localization decoupling and exemplar prompts to one
protein chain. It neither imports SAM weights nor produces validated biology.
Inputs are per-residue embeddings from a separately versioned protein encoder.
Coordinates throughout this module are zero-based half-open until decoding.
"""

from __future__ import annotations

from collections import Counter
from itertools import permutations
import math
from typing import Sequence

import torch
from torch import nn
from torch.nn import functional as F


CONCEPTS = ("disordered_flexible_linker", "independent_domain_linker",
            "dependent_domain_linker")


def _positional_encoding(length: int, width: int, device: torch.device,
                         dtype: torch.dtype) -> torch.Tensor:
    position = torch.arange(length, device=device, dtype=torch.float32).unsqueeze(1)
    scale = torch.exp(torch.arange(0, width, 2, device=device, dtype=torch.float32)
                      * (-math.log(10000.0) / width))
    encoding = torch.zeros(length, width, device=device, dtype=torch.float32)
    encoding[:, 0::2] = torch.sin(position * scale)
    encoding[:, 1::2] = torch.cos(position * scale[:encoding[:, 1::2].shape[1]])
    return encoding.to(dtype=dtype)


def _validate_mask(mask: torch.Tensor, batch: int, length: int) -> None:
    if mask.shape != (batch, length) or mask.dtype != torch.bool:
        raise ValueError("valid_mask must be boolean [batch,length]")
    if not mask.any(dim=1).all():
        raise ValueError("Every protein requires at least one valid residue")
    if ((~mask[:, :-1]) & mask[:, 1:]).any():
        raise ValueError("Padding must be a right-hand suffix")


class PromptableLinkerSegmenter(nn.Module):
    """Small prompt-conditioned span head over frozen pLM residue embeddings.

    The three concept IDs belong to separate label ontologies. A training job
    must supervise each concept from its matching source, never interpret an
    unlabeled concept as a true negative for another concept.
    """

    def __init__(self, embedding_dim: int, *, width: int = 128, heads: int = 4,
                 layers: int = 2, queries: int = 4, dropout: float = 0.1) -> None:
        super().__init__()
        if (embedding_dim < 1 or width < 2 or width % heads or heads < 1
                or layers < 1 or not 1 <= queries <= 8 or not 0 <= dropout < 1):
            raise ValueError("Invalid segmenter dimensions")
        self.embedding_dim = embedding_dim
        self.queries = queries
        self.input_projection = nn.Linear(embedding_dim, width)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=width, nhead=heads, dim_feedforward=2 * width,
            dropout=dropout, activation="gelu", batch_first=True, norm_first=True)
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=layers,
                                             enable_nested_tensor=False)
        self.concept_embedding = nn.Embedding(len(CONCEPTS), width)
        self.exemplar_projection = nn.Linear(2 * width, width)
        self.presence = nn.Sequential(nn.Linear(2 * width, width), nn.GELU(),
                                      nn.Linear(width, 1))
        self.semantic = nn.Sequential(nn.Linear(2 * width, width), nn.GELU(),
                                      nn.Linear(width, 1))
        self.query_embedding = nn.Parameter(torch.randn(queries, width) * 0.02)
        self.query_attention = nn.MultiheadAttention(width, heads, dropout=dropout,
                                                      batch_first=True)
        self.query_norm = nn.LayerNorm(width)
        self.query_match = nn.Linear(width, 1)
        self.start_query = nn.Linear(width, width)
        self.end_query = nn.Linear(width, width)
        self.mask_query = nn.Linear(width, width)
        self.residue_key = nn.Linear(width, width)

    def forward(self, residue_embeddings: torch.Tensor, valid_mask: torch.Tensor,
                concept_ids: torch.Tensor, *,
                exemplar_labels: torch.Tensor | None = None) -> dict[str, torch.Tensor]:
        if residue_embeddings.ndim != 3 or residue_embeddings.shape[-1] != self.embedding_dim:
            raise ValueError("Expected residue_embeddings [batch,length,embedding_dim]")
        batch, length, _ = residue_embeddings.shape
        _validate_mask(valid_mask, batch, length)
        if concept_ids.shape != (batch,) or concept_ids.dtype != torch.long:
            raise ValueError("concept_ids must be int64 [batch]")
        if ((concept_ids < 0) | (concept_ids >= len(CONCEPTS))).any():
            raise ValueError("Unknown linker concept ID")
        if not torch.isfinite(residue_embeddings).all():
            raise ValueError("Residue embeddings contain nonfinite values")

        hidden = self.input_projection(residue_embeddings)
        hidden = hidden + _positional_encoding(length, hidden.shape[-1], hidden.device,
                                                hidden.dtype).unsqueeze(0)
        hidden = self.encoder(hidden, src_key_padding_mask=~valid_mask)
        hidden = hidden.masked_fill(~valid_mask.unsqueeze(-1), 0)
        prompt = self.concept_embedding(concept_ids)
        if exemplar_labels is not None:
            if exemplar_labels.shape != (batch, length) or not torch.isin(
                    exemplar_labels, torch.tensor([-1, 0, 1], device=exemplar_labels.device)).all():
                raise ValueError("exemplar_labels must be -1/0/+1 [batch,length]")
            if (exemplar_labels[~valid_mask] != 0).any():
                raise ValueError("Exemplars cannot be placed on padding")
            means = []
            for value in (1, -1):
                selected = (exemplar_labels == value) & valid_mask
                total = (hidden * selected.unsqueeze(-1)).sum(dim=1)
                means.append(total / selected.sum(dim=1).clamp_min(1).unsqueeze(-1))
            prompt = prompt + self.exemplar_projection(torch.cat(means, dim=-1))

        pooled = hidden.sum(dim=1) / valid_mask.sum(dim=1).unsqueeze(-1)
        presence_logits = self.presence(torch.cat((pooled, prompt), dim=-1)).squeeze(-1)
        semantic_logits = self.semantic(torch.cat((hidden, prompt[:, None, :].expand(-1, length, -1)),
                                        dim=-1)).squeeze(-1)
        query_input = self.query_embedding[None, :, :] + prompt[:, None, :]
        attended, _ = self.query_attention(query_input, hidden, hidden,
                                            key_padding_mask=~valid_mask,
                                            need_weights=False)
        query_state = self.query_norm(query_input + attended)
        query_match_logits = self.query_match(query_state).squeeze(-1)
        keys = self.residue_key(hidden)
        scale = hidden.shape[-1] ** -0.5
        start_logits = torch.matmul(self.start_query(query_state), keys.transpose(1, 2)) * scale
        end_logits = torch.matmul(self.end_query(query_state), keys.transpose(1, 2)) * scale
        instance_mask_logits = torch.matmul(self.mask_query(query_state), keys.transpose(1, 2)) * scale
        padding = ~valid_mask
        return {"presence_logits": presence_logits,
                "semantic_logits": semantic_logits.masked_fill(padding, -1e4),
                "query_match_logits": query_match_logits,
                "start_logits": start_logits.masked_fill(padding[:, None, :], -1e4),
                "end_logits": end_logits.masked_fill(padding[:, None, :], -1e4),
                "instance_mask_logits": instance_mask_logits.masked_fill(
                    padding[:, None, :], -1e4)}


def _match_queries(start: torch.Tensor, end: torch.Tensor,
                   spans: Sequence[tuple[int, int]]) -> tuple[int, ...]:
    """Small exact assignment (<=8 queries) on detached boundary likelihoods."""
    q_count = start.shape[0]
    if len(spans) > q_count:
        raise ValueError("More annotated spans than query slots")
    start_logp = start.detach().log_softmax(-1)
    end_logp = end.detach().log_softmax(-1)
    best: tuple[int, ...] | None = None
    best_cost = math.inf
    for assignment in permutations(range(q_count), len(spans)):
        cost = -sum(float(start_logp[q, s] + end_logp[q, e - 1])
                    for q, (s, e) in zip(assignment, spans))
        if cost < best_cost:
            best_cost, best = cost, assignment
    return best or ()


def segmenter_loss(outputs: dict[str, torch.Tensor], valid_mask: torch.Tensor,
                   residue_targets: torch.Tensor, presence_targets: torch.Tensor,
                   gold_spans: Sequence[Sequence[tuple[int, int]]],
                   exhaustive: torch.Tensor) -> dict[str, torch.Tensor]:
    """Masked supervision: -1 means unknown, never a negative label.

    gold_spans use zero-based half-open coordinates. `exhaustive=True` is
    reserved for adjudicated proteins where unmatched queries may be trained
    as no-object. Ordinary DisProt positive-only records must set it False.
    """
    batch, length = valid_mask.shape
    _validate_mask(valid_mask, batch, length)
    if (residue_targets.shape != (batch, length) or presence_targets.shape != (batch,)
            or exhaustive.shape != (batch,) or exhaustive.dtype != torch.bool
            or len(gold_spans) != batch):
        raise ValueError("Target shapes do not match batch")
    if not torch.isin(residue_targets, torch.tensor([-1, 0, 1], device=residue_targets.device)).all():
        raise ValueError("Residue targets must be -1, 0, or 1")
    if not torch.isin(presence_targets, torch.tensor([-1, 0, 1], device=presence_targets.device)).all():
        raise ValueError("Presence targets must be -1, 0, or 1")
    if (residue_targets[~valid_mask] != -1).any():
        raise ValueError("Padding targets must be unknown")
    if ((presence_targets == 0) & ~exhaustive).any():
        raise ValueError("Absence may be supervised only when annotation is exhaustive")

    zero = outputs["semantic_logits"].sum() * 0
    known = (residue_targets != -1) & valid_mask
    semantic = (F.binary_cross_entropy_with_logits(outputs["semantic_logits"][known],
                residue_targets[known].float()) if known.any() else zero)
    known_presence = presence_targets != -1
    presence = (F.binary_cross_entropy_with_logits(
        outputs["presence_logits"][known_presence], presence_targets[known_presence].float())
        if known_presence.any() else zero)
    query_terms, boundary_terms, mask_terms = [], [], []
    for b, spans in enumerate(gold_spans):
        n = int(valid_mask[b].sum())
        if len(spans) > outputs["query_match_logits"].shape[1]:
            raise ValueError("More spans than query slots")
        ordered = sorted(spans)
        for index, (start, end) in enumerate(ordered):
            if not 0 <= start < end <= n or (index and start < ordered[index - 1][1]):
                raise ValueError("Gold spans must be disjoint and inside the sequence")
            if not (residue_targets[b, start:end] == 1).all():
                raise ValueError("Gold span residues must be labeled positive")
        if ordered and presence_targets[b] != 1:
            raise ValueError("Gold spans require positive presence target")
        if not ordered and presence_targets[b] == 1:
            raise ValueError("Positive presence requires a complete gold span")
        if exhaustive[b] and (residue_targets[b, :n] == -1).any():
            raise ValueError("Exhaustive examples cannot contain unknown residues")
        matched = _match_queries(outputs["start_logits"][b, :, :n],
                                 outputs["end_logits"][b, :, :n], ordered)
        if matched or exhaustive[b]:
            indices = (list(range(outputs["query_match_logits"].shape[1]))
                       if exhaustive[b] else list(matched))
            target = torch.tensor([q in matched for q in indices], device=valid_mask.device,
                                  dtype=outputs["query_match_logits"].dtype)
            query_terms.append(F.binary_cross_entropy_with_logits(
                outputs["query_match_logits"][b, indices], target))
        for q, (start, end) in zip(matched, ordered):
            boundary_terms.append(F.cross_entropy(outputs["start_logits"][b, q, :n][None, :],
                                                   torch.tensor([start], device=valid_mask.device)))
            boundary_terms.append(F.cross_entropy(outputs["end_logits"][b, q, :n][None, :],
                                                   torch.tensor([end - 1], device=valid_mask.device)))
            # Other annotated linker instances and verified non-linker residues
            # are known zero for this particular instance. Unknowns stay masked.
            target = torch.zeros(n, device=valid_mask.device)
            target[start:end] = 1
            mask_terms.append(F.binary_cross_entropy_with_logits(
                outputs["instance_mask_logits"][b, q, :n][known[b, :n]],
                target[known[b, :n]]))
    query = torch.stack(query_terms).mean() if query_terms else zero
    boundary = torch.stack(boundary_terms).mean() if boundary_terms else zero
    instance = torch.stack(mask_terms).mean() if mask_terms else zero
    total = semantic + 0.5 * presence + 0.5 * query + 0.5 * boundary + 0.5 * instance
    return {"total": total, "semantic": semantic, "presence": presence,
            "query_match": query, "boundary": boundary, "instance_mask": instance}


@torch.no_grad()
def decode_spans(outputs: dict[str, torch.Tensor], sequences: Sequence[str],
                 valid_mask: torch.Tensor, concept_ids: torch.Tensor, *,
                 presence_threshold: float = 0.5, query_threshold: float = 0.5,
                 min_length: int = 4, max_length: int = 200,
                 overlap_iou: float = 0.5) -> list[dict]:
    """Return explicit spans or abstention; thresholds must be frozen on dev."""
    batch, length = valid_mask.shape
    _validate_mask(valid_mask, batch, length)
    if len(sequences) != batch or concept_ids.shape != (batch,):
        raise ValueError("Sequence, concept, and batch sizes differ")
    if not (0 <= presence_threshold <= 1 and 0 <= query_threshold <= 1
            and 0 < overlap_iou <= 1 and 1 <= min_length <= max_length):
        raise ValueError("Invalid decoding thresholds")
    results = []
    for b, sequence in enumerate(sequences):
        n = int(valid_mask[b].sum())
        if len(sequence) != n:
            raise ValueError("Sequence length does not match valid mask")
        if not sequence or set(sequence) - set("ACDEFGHIKLMNPQRSTVWY"):
            raise ValueError("Only canonical uppercase amino acids are supported")
        concept = int(concept_ids[b])
        if not 0 <= concept < len(CONCEPTS):
            raise ValueError("Unknown linker concept ID")
        presence = float(outputs["presence_logits"][b].sigmoid())
        candidates = []
        if presence >= presence_threshold:
            for q in range(outputs["query_match_logits"].shape[1]):
                match = float(outputs["query_match_logits"][b, q].sigmoid())
                if match < query_threshold:
                    continue
                start = outputs["start_logits"][b, q, :n].log_softmax(-1)
                end = outputs["end_logits"][b, q, :n].log_softmax(-1)
                joint = start[:, None] + end[None, :]
                start_indices = torch.arange(n, device=joint.device)[:, None]
                end_indices = torch.arange(n, device=joint.device)[None, :]
                span_lengths = end_indices - start_indices + 1
                valid = (span_lengths >= min_length) & (span_lengths <= max_length)
                if not valid.any():
                    continue
                choice = int(joint.masked_fill(~valid, -torch.inf).flatten().argmax())
                left, right = divmod(choice, n)
                # Combine global presence and local query confidence. Boundary
                # logits choose coordinates, not a calibrated biology score.
                candidates.append((presence * match, left, right + 1, q))
        candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
        spans = []
        for score, start, end, query in candidates:
            def overlaps(prior: dict) -> bool:
                prior_start, prior_end = prior["start_1based"] - 1, prior["end_1based"]
                intersection = max(0, min(end, prior_end) - max(start, prior_start))
                union = max(end, prior_end) - min(start, prior_start)
                return intersection / union >= overlap_iou

            if any(overlaps(prior) for prior in spans):
                continue
            peptide = sequence[start:end]
            spans.append({"start_1based": start + 1, "end_1based": end,
                          "sequence": peptide, "length": len(peptide),
                          "composition_counts": dict(sorted(Counter(peptide).items())),
                          "query_index": query, "proposal_score": score})
        results.append({"concept": CONCEPTS[concept], "presence_score": presence,
                        "status": "proposed_spans" if spans else "abstained",
                        "spans": spans,
                        "residue_scores": outputs["semantic_logits"][b, :n].sigmoid().tolist()})
    return results
