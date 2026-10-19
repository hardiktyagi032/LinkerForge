"""Bounded span-aware DFL trial on the frozen TR166/TE82 masked contract.

Adds start/end heads and an explicit complete-interval objective to the
matched frozen-ESM2 CNN baseline. It does not open TE64 or CAID3.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import time

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from sklearn.metrics import average_precision_score, roc_auc_score
from transformers import AutoModel, AutoTokenizer

from train_dfl_masked_cnn import TRAIN, DEV, MODEL_ID, embed_group, load, preflight, windows
from train_esm2_linker_detector import atomic_checkpoint, high_precision_operating_point


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/dfl_autoresearch_round_2026-10-12.json"
DATA_MANIFEST = ROOT / "data/processed/published_dfl_splits/manifest.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SpanHead(nn.Module):
    def __init__(self, embedding_dim: int):
        super().__init__()
        self.network = nn.Sequential(nn.Conv1d(embedding_dim, 128, 5, padding=2), nn.GELU(),
                                     nn.Conv1d(128, 128, 5, padding=2), nn.GELU(),
                                     nn.Conv1d(128, 3, 1))

    def forward(self, embeddings):
        return self.network(embeddings.transpose(1, 2)).transpose(1, 2)


def clean_spans(encoded: str, symbol: str, minimum: int = 4, maximum: int = 200):
    spans = []
    start = None
    for i, value in enumerate(encoded + "!"):
        if value == symbol and start is None:
            start = i
        if start is not None and value != symbol:
            end = i - 1
            if symbol == "0":
                # Sample bounded all-negative subsegments even in long runs.
                for a in range(start, end + 1, 50):
                    b = min(a + 49, end)
                    if b - a + 1 >= minimum:
                        spans.append((a, b))
                start = None
                continue
            if minimum <= end - start + 1 <= maximum and start > 0 and end + 1 < len(encoded):
                # Positive span boundaries are the ends of the published
                # annotation, even when adjacent residues are masked x.
                spans.append((start, end))
            start = None
    return spans


def boundary_targets(encoded: str, device):
    start = torch.zeros(len(encoded), device=device)
    end = torch.zeros(len(encoded), device=device)
    valid = torch.zeros(len(encoded), device=device, dtype=torch.bool)
    for i, value in enumerate(encoded):
        if value == "x" or i == 0 or i == len(encoded) - 1:
            continue
        if value == "0" and (encoded[i - 1] == "x" or encoded[i + 1] == "x"):
            continue
        valid[i] = True
        start[i] = value == "1" and encoded[i - 1] != "1"
        end[i] = value == "1" and encoded[i + 1] != "1"
    return start, end, valid


def interval_logit(logits, start: int, end: int):
    return (logits[start:end + 1, 0].mean() + logits[start, 1] + logits[end, 2]) / 3


def training_loss(logits, labels, mask, group):
    residue = (F.binary_cross_entropy_with_logits(logits[:, :, 0][mask], labels[mask])
               if mask.any() else logits.sum() * 0)
    boundary_terms = []
    span_positive = []
    span_negative = []
    for i, (_, encoded, _) in enumerate(group):
        start, end, valid = boundary_targets(encoded, logits.device)
        if valid.any():
            boundary_terms.append(F.binary_cross_entropy_with_logits(logits[i, :len(encoded), 1][valid], start[valid]))
            boundary_terms.append(F.binary_cross_entropy_with_logits(logits[i, :len(encoded), 2][valid], end[valid]))
        positives = clean_spans(encoded, "1")
        negatives = clean_spans(encoded, "0")
        for a, b in positives:
            span_positive.append(interval_logit(logits[i], a, b))
        for a, b in negatives[:max(1, 2 * len(positives))]:
            span_negative.append(interval_logit(logits[i], a, b))
    loss = residue
    if boundary_terms:
        loss = loss + 0.2 * torch.stack(boundary_terms).mean()
    if span_positive and span_negative:
        positive = torch.stack(span_positive)
        negative = torch.stack(span_negative)
        loss = loss + 0.3 * (F.softplus(-positive).mean() + F.softplus(negative).mean()) / 2
    return loss


@torch.no_grad()
def evaluate(backbone, tokenizer, head, examples, device):
    head.eval()
    truth, scores = [], []
    for offset in range(0, len(examples), 4):
        group = examples[offset:offset + 4]
        embeddings, labels, mask = embed_group(backbone, tokenizer, group, device)
        probabilities = head(embeddings)[:, :, 0].sigmoid()
        truth.extend(labels[mask].cpu().numpy().tolist())
        scores.extend(probabilities[mask].cpu().numpy().tolist())
    truth = np.asarray(truth, dtype=np.uint8)
    scores = np.asarray(scores, dtype=np.float32)
    return {"masked_residue_aps": float(average_precision_score(truth, scores)),
            "masked_residue_auroc": float(roc_auc_score(truth, scores)),
            "scored_residues": int(len(truth)), "positive_residues": int(truth.sum()),
            "precision_90_operating_point": high_precision_operating_point(truth, scores)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--max-hours", type=float, default=2)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    train, dev = preflight()
    train_windows = windows(train, 510)
    clean_positive = sum(len(clean_spans(encoded, "1")) for _, encoded, _ in train_windows)
    clean_negative = sum(len(clean_spans(encoded, "0")) for _, encoded, _ in train_windows)
    if not clean_positive or not clean_negative:
        raise ValueError("No eligible complete positive/negative spans")
    if args.preflight_only:
        print(json.dumps({"status": "preflight_pass", "train_windows": len(train_windows),
                          "clean_positive_spans": clean_positive, "clean_negative_spans": clean_negative,
                          "train_sha256": sha(TRAIN), "dev_sha256": sha(DEV)}))
        return
    if not torch.cuda.is_available() or args.epochs < 1 or not 0 < args.max_hours <= 2:
        raise RuntimeError("CUDA unavailable or trial bounds invalid")
    if args.output_dir.exists():
        raise FileExistsError("Trial output exists; refusing duplicate")
    args.output_dir.mkdir(parents=True)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    random.seed(args.seed)
    device = torch.device("cuda")
    started = time.monotonic()
    manifest = {"schema_version": "0.1.0", "status": "initializing", "seed": args.seed,
                "architecture": "frozen_esm2_35m_CNN_residue_boundary_interval",
                "model_id": MODEL_ID, "train_sha256": sha(TRAIN), "dev_sha256": sha(DEV),
                "config_sha256": sha(CONFIG), "data_manifest_sha256": sha(DATA_MANIFEST),
                "source_sha256": sha(Path(__file__)),
                "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "created_utc": datetime.now(timezone.utc).isoformat(), "max_hours": args.max_hours,
                "gpu": torch.cuda.get_device_name(0),
                "span_objective_eligible_positive_train_windows": clean_positive,
                "span_objective_eligible_negative_train_windows": clean_negative,
                "versions": {"python": sys.version.split()[0], "torch": torch.__version__,
                             "transformers": __import__("transformers").__version__}}
    target = args.output_dir / "manifest.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        backbone = AutoModel.from_pretrained(MODEL_ID).to(device).eval()
        backbone.requires_grad_(False)
        manifest["resolved_model_commit"] = getattr(backbone.config, "_commit_hash", None)
        head = SpanHead(backbone.config.hidden_size).to(device)
        optimizer = torch.optim.AdamW(head.parameters(), lr=3e-4)
        dev_windows = windows(dev, 510)
        manifest["status"] = "running"
        target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        best = -1.0
        for epoch in range(args.epochs):
            if time.monotonic() - started > args.max_hours * 3600:
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
                loss = training_loss(logits, labels, mask, group)
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
                optimizer.step()
                losses.append(float(loss.item()))
            metrics = evaluate(backbone, tokenizer, head, dev_windows, device)
            record = {"epoch": epoch + 1, "train_loss": sum(losses) / len(losses), "development": metrics}
            with (args.output_dir / "epochs.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record) + "\n")
            if metrics["masked_residue_aps"] > best:
                best = metrics["masked_residue_aps"]
                atomic_checkpoint({"head": head.state_dict(), "epoch": epoch + 1,
                                   "model_id": MODEL_ID, "development": metrics}, args.output_dir / "best.pt")
            manifest["completed_epochs"] = epoch + 1
            manifest["best_development_aps"] = best
            target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(record), flush=True)
        if manifest["status"] == "running":
            manifest["status"] = "completed"
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        manifest["elapsed_seconds"] = round(time.monotonic() - started, 3)
        manifest["peak_pytorch_vram_bytes"] = torch.cuda.max_memory_allocated()
        target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
