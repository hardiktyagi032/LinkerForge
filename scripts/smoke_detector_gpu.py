"""One synthetic CUDA optimizer step and atomic checkpoint/resume smoke test.

Synthetic inputs test software only; they are never scientific training data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from linkerforge.models.linker_detector_gpu import LinkerDetector, detector_loss
from train_linker_detector_gpu import save_checkpoint


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("CUDA unavailable")
    device = torch.device("cuda")
    model = LinkerDetector().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.0003)
    amino = torch.randint(1, 21, (2, 64), device=device)
    domains = torch.zeros((2, 64), dtype=torch.long, device=device)
    domains[:, :24] = 1
    domains[:, 35:] = 2
    valid = torch.ones((2, 64), dtype=torch.bool, device=device)
    labels = torch.zeros((2, 64), dtype=torch.long, device=device)
    labels[0, 24:35] = 1
    starts = torch.zeros((2, 64), device=device)
    ends = torch.zeros((2, 64), device=device)
    starts[0, 24] = 1
    ends[0, 34] = 1
    optimizer.zero_grad(set_to_none=True)
    output = model(amino, domains, valid)
    loss = detector_loss(output, labels, starts, ends, valid)
    loss.backward()
    optimizer.step()
    checkpoint = save_checkpoint({"model": model.state_dict(),
                                  "optimizer": optimizer.state_dict(),
                                  "kind": "synthetic_cuda_smoke"},
                                 args.checkpoint_dir, None)
    restored = torch.load(checkpoint, map_location=device, weights_only=False)
    model.load_state_dict(restored["model"])
    optimizer.load_state_dict(restored["optimizer"])
    print(json.dumps({"status": "synthetic_cuda_smoke_pass", "torch": torch.__version__,
                      "cuda_runtime": torch.version.cuda,
                      "device": torch.cuda.get_device_name(0),
                      "loss_finite": bool(torch.isfinite(loss).item()),
                      "checkpoint": str(checkpoint),
                      "restored_kind": restored["kind"]}), flush=True)


if __name__ == "__main__":
    main()
