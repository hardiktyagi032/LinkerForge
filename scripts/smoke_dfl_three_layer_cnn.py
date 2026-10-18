"""CPU-only synthetic forward/backward check of the first-stage DFL CNN.

This command uses no proteins, benchmark labels, pretrained encoder or GPU.
It cannot create a mining-qualified checkpoint.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.linkerforge.detector.cnn import ThreeLayerDFLCNN, labels_to_tensor, masked_bce_with_logits


def main() -> None:
    torch.manual_seed(20261018)
    model = ThreeLayerDFLCNN(8)
    features = torch.randn(2, 16, 8)
    labels = labels_to_tensor(["xx111000xxxxxxxx", "x0011xxxxxxxxxxx"], 16)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    before = float(masked_bce_with_logits(model(features), labels).detach())
    for _ in range(12):
        optimizer.zero_grad(set_to_none=True)
        loss = masked_bce_with_logits(model(features), labels)
        loss.backward()
        optimizer.step()
    after = float(masked_bce_with_logits(model(features), labels).detach())
    if not after < before:
        raise RuntimeError("Synthetic loss did not decrease")
    print(json.dumps({"status": "synthetic_cpu_smoke_pass", "architecture": "three_layer_1d_cnn_1_5_1",
                      "scores_per_sequence": list(model(features).shape),
                      "observed_positives": int((labels == 1).sum()),
                      "observed_negatives": int((labels == 0).sum()),
                      "ignored_unknown_or_padding": int((labels == -1).sum()),
                      "loss_before": before, "loss_after": after,
                      "scientific_status": "untrained_on_proteins_no_precision_claim"}))


if __name__ == "__main__":
    main()
