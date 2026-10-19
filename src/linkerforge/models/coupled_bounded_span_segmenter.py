"""Second segmental variant: candidate interval evidence enters residue logits."""

import torch
from torch.nn import functional as F

from .bounded_span_linker_segmenter import BoundedSpanLinkerSegmenter


class CoupledBoundedSpanSegmenter(BoundedSpanLinkerSegmenter):
    def forward(self, residue_embeddings: torch.Tensor, valid_mask: torch.Tensor) -> dict:
        output = super().forward(residue_embeddings, valid_mask)
        length = valid_mask.shape[1]
        support = []
        for span_len, logits in enumerate(output["span_logits"], start=1):
            # A residue can be supported by any candidate interval containing it.
            # Preserve score ties and mask invalid/padded intervals.
            padded = F.pad(logits.unsqueeze(1), (span_len - 1, span_len - 1), value=-1e4)
            pooled = F.max_pool1d(padded, kernel_size=span_len, stride=1).squeeze(1)
            if pooled.shape[1] != length:
                raise RuntimeError("Span-to-residue aggregation length mismatch")
            support.append(pooled)
        span_support = torch.stack(support).amax(0)
        output["semantic_logits"] = (output["semantic_logits"] + 0.5 * span_support).masked_fill(~valid_mask, -1e4)
        output["span_support_logits"] = span_support.masked_fill(~valid_mask, -1e4)
        return output
