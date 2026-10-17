"""Bounded exploratory masked-DFL precision-constraint loss adaptation.

The smooth batchwise penalty is inspired by Rath & Hughes (AISTATS 2022),
not a reproduction of their tight count bounds or clinical experiments.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import subprocess
import sys
import time

import torch
from torch.nn import functional as F
from transformers import AutoModel, AutoTokenizer

from train_dfl_masked_cnn import (TRAIN, DEV, CONFIG, DATA_MANIFEST, MODEL_ID,
                                  ResidueHead, atomic_checkpoint, embed_group,
                                  evaluate, preflight, sha, windows)


def precision_constrained_loss(logits, labels, mask):
    if not mask.any():
        return logits.sum() * 0
    scored_logits, targets = logits[mask], labels[mask]
    anchor = F.binary_cross_entropy_with_logits(scored_logits, targets)
    # Differentiable batch counts. The 0.9 target implies FP <= TP / 9.
    # This is a simple adaptation, not the paper's certified tight bounds.
    probabilities = torch.sigmoid(scored_logits)
    soft_tp = (probabilities * targets).sum()
    soft_fp = (probabilities * (1 - targets)).sum()
    positive_count = targets.sum()
    if positive_count == 0:
        return anchor + 0.5 * soft_fp / targets.numel()
    soft_recall = soft_tp / positive_count
    violation = F.relu(soft_fp - soft_tp / 9) / targets.numel()
    return anchor + 0.5 * (1 - soft_recall) + violation


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--max-hours", type=float, default=2)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    train, dev = preflight()
    if args.preflight_only:
        test = precision_constrained_loss(torch.tensor([0., 0.], requires_grad=True),
                                          torch.tensor([1., 0.]), torch.tensor([True, True]))
        test.backward()
        if not torch.isfinite(test):
            raise ValueError("Nonfinite loss")
        print(json.dumps({"status": "preflight_pass", "train_sha256": sha(TRAIN), "dev_sha256": sha(DEV),
                          "train_proteins": len(train), "dev_proteins": len(dev)}))
        return
    if not torch.cuda.is_available() or args.epochs < 1 or not 0 < args.max_hours <= 2:
        raise RuntimeError("CUDA unavailable or trial bounds invalid")
    if args.output_dir.exists():
        raise FileExistsError("Trial directory already exists")
    args.output_dir.mkdir(parents=True)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    random.seed(args.seed)
    device = torch.device("cuda")
    began = time.monotonic()
    manifest = {"schema_version": "0.1.0", "status": "initializing", "seed": args.seed,
                "architecture": "frozen_esm2_35m_CNN_BCE_plus_smooth_precision_constraint",
                "model_id": MODEL_ID, "train_sha256": sha(TRAIN), "dev_sha256": sha(DEV),
                "config_sha256": sha(CONFIG), "data_manifest_sha256": sha(DATA_MANIFEST),
                "source_sha256": sha(Path(__file__)),
                "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "created_utc": datetime.now(timezone.utc).isoformat(), "max_hours": args.max_hours,
                "gpu": torch.cuda.get_device_name(0),
                "versions": {"python": sys.version.split()[0], "torch": torch.__version__,
                             "transformers": __import__("transformers").__version__}}
    path = args.output_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        backbone = AutoModel.from_pretrained(MODEL_ID).to(device).eval()
        backbone.requires_grad_(False)
        manifest["resolved_model_commit"] = getattr(backbone.config, "_commit_hash", None)
        head = ResidueHead(backbone.config.hidden_size).to(device)
        optimizer = torch.optim.AdamW(head.parameters(), lr=3e-4)
        train_windows, dev_windows = windows(train, 510), windows(dev, 510)
        manifest["status"] = "running"
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        best = -1.
        for epoch in range(args.epochs):
            if time.monotonic() - began > args.max_hours * 3600:
                manifest["status"] = "time_limit"
                break
            head.train()
            order = list(range(len(train_windows)))
            random.Random(args.seed + epoch).shuffle(order)
            losses = []
            for offset in range(0, len(order), 4):
                group = [train_windows[i] for i in order[offset:offset + 4]]
                embeddings, labels, mask = embed_group(backbone, tokenizer, group, device)
                logits = head(embeddings)
                loss = precision_constrained_loss(logits, labels, mask)
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(head.parameters(), 1.)
                optimizer.step()
                losses.append(float(loss.item()))
            metrics = evaluate(backbone, tokenizer, head, dev_windows, 4, device)
            record = {"epoch": epoch + 1, "train_loss": sum(losses) / len(losses), "development": metrics}
            with (args.output_dir / "epochs.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record) + "\n")
            if metrics["masked_residue_aps"] > best:
                best = metrics["masked_residue_aps"]
                atomic_checkpoint({"head": head.state_dict(), "epoch": epoch + 1,
                                   "model_id": MODEL_ID, "development": metrics}, args.output_dir / "best.pt")
            manifest["completed_epochs"] = epoch + 1
            manifest["best_development_aps"] = best
            path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(record), flush=True)
        if manifest["status"] == "running":
            manifest["status"] = "completed"
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        manifest["elapsed_seconds"] = round(time.monotonic() - began, 3)
        manifest["peak_pytorch_vram_bytes"] = torch.cuda.max_memory_allocated()
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
