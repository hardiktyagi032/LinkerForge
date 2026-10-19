"""Bounded DLD trial: frozen ESM-2, residue CNN, auxiliary span boundaries.

Folds 1-3 train and fold 4 develops; never opens fold 5. This is a binary
span-supervision adaptation, not a claim to reproduce a semi-Markov CRF.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import random
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from sklearn.metrics import average_precision_score, roc_auc_score
from transformers import AutoModel, AutoTokenizer

from preflight_detector_data import preflight
from train_esm2_linker_detector import (
    atomic_checkpoint, batch_embedding, file_hash, high_precision_operating_point,
    make_windows, read_records,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from linkerforge.detector.evaluation import region_metrics  # noqa: E402


class SpanHead(nn.Module):
    def __init__(self, embedding_dim: int, width: int = 128) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv1d(embedding_dim, width, 5, padding=2), nn.GELU(),
            nn.Conv1d(width, width, 5, padding=2), nn.GELU(),
        )
        self.residue = nn.Conv1d(width, 1, 1)
        self.boundary = nn.Conv1d(width, 2, 1)

    def forward(self, embeddings: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        features = self.features(embeddings.transpose(1, 2))
        return self.residue(features).squeeze(1), self.boundary(features).transpose(1, 2)


def boundary_targets(targets: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """Mark starts and ends separately; padding can never create an end."""
    positive = (targets > 0) & mask
    prior = F.pad(positive[:, :-1], (1, 0), value=False)
    following = F.pad(positive[:, 1:], (0, 1), value=False)
    return torch.stack((positive & ~prior, positive & ~following), dim=-1).float()


def span_loss(residue_logits: torch.Tensor, boundary_logits: torch.Tensor,
              targets: torch.Tensor, mask: torch.Tensor,
              positive_weight: float, boundary_weight: float) -> torch.Tensor:
    residue_loss = F.binary_cross_entropy_with_logits(
        residue_logits[mask], targets[mask],
        pos_weight=torch.tensor(positive_weight, device=targets.device))
    boundaries = boundary_targets(targets, mask)
    selected = boundary_logits[mask]
    boundary_loss = F.binary_cross_entropy_with_logits(
        selected, boundaries[mask],
        pos_weight=torch.tensor(positive_weight, device=targets.device))
    return residue_loss + boundary_weight * boundary_loss


@torch.no_grad()
def evaluate(backbone, tokenizer, head, windows, batch_size, device) -> dict:
    head.eval()
    truths: list[int] = []
    scores: list[float] = []
    truth_by_protein: dict[str, list[bool]] = {}
    score_by_protein: dict[str, list[float]] = {}
    for offset in range(0, len(windows), batch_size):
        group = windows[offset:offset + batch_size]
        embeddings, targets, mask = batch_embedding(backbone, tokenizer, group, device)
        logits, _ = head(embeddings)
        probabilities = logits.sigmoid()
        for index, (_, _, source_id) in enumerate(group):
            observed = targets[index, mask[index]].to("cpu").int().tolist()
            predicted = probabilities[index, mask[index]].to("cpu").tolist()
            truths.extend(observed)
            scores.extend(predicted)
            truth_by_protein.setdefault(source_id, []).extend(bool(x) for x in observed)
            score_by_protein.setdefault(source_id, []).extend(predicted)
    truth = np.asarray(truths, dtype=np.uint8)
    score = np.asarray(scores, dtype=np.float32)
    if not truth.any() or truth.all():
        raise ValueError("Validation requires positive and negative residues")
    point = high_precision_operating_point(truth, score)
    threshold = point["threshold"]
    negatives = [key for key, flags in truth_by_protein.items() if not any(flags)]
    specificity = (sum(max(score_by_protein[key]) < threshold for key in negatives) / len(negatives)
                   if threshold is not None and negatives else None)
    regions = (region_metrics(truth_by_protein, score_by_protein, threshold)
               if threshold is not None else None)
    return {
        "residue_auprc": float(average_precision_score(truth, score)),
        "residue_auroc": float(roc_auc_score(truth, score)),
        "positive_residues": int(truth.sum()), "residues": len(truth),
        "proteins": len(truth_by_protein),
        "validation_precision_90_operating_point": point,
        "no_linker_protein_specificity": specificity,
        "region_metrics_iou_0_5": regions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--model-id", default="facebook/esm2_t12_35M_UR50D")
    parser.add_argument("--revision", default="6fbf070e65b0b7291e7bbcd451118c216cff79d8")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-residues", type=int, default=510)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--positive-weight", type=float, default=6.0)
    parser.add_argument("--boundary-weight", type=float, default=0.25)
    parser.add_argument("--maximum-hours", type=float, default=6.0)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("CUDA unavailable; refusing CPU training")
    if args.epochs < 1 or args.batch_size < 1 or not 1 <= args.max_residues <= 510:
        raise ValueError("Invalid training dimensions")
    if args.positive_weight <= 0 or args.boundary_weight < 0 or args.maximum_hours <= 0:
        raise ValueError("Invalid loss or time budget")
    output = args.output_dir
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Run output must be isolated and empty: {output}")
    train_hash, validation_hash = file_hash(args.train), file_hash(args.validation)
    expected = {
        "train": "c43952c4f943f458ba61905c34a59e04fadca5607b95d6afc9bd9d1475252c41",
        "validation": "290992af4a93c14ba007197c282367734af8ec878783d5e668ee4960128a3461",
    }
    if train_hash != expected["train"] or validation_hash != expected["validation"]:
        raise ValueError("Frozen DLD train/validation hash mismatch")
    preflight_report = preflight(str(args.train), str(args.validation))
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    random.seed(args.seed)
    device = torch.device("cuda")
    tokenizer = AutoTokenizer.from_pretrained(args.model_id, revision=args.revision)
    backbone = AutoModel.from_pretrained(args.model_id, revision=args.revision).to(device).eval()
    backbone.requires_grad_(False)
    if getattr(backbone.config, "_commit_hash", None) not in (None, args.revision):
        raise ValueError("Resolved backbone revision differs from requested revision")
    head = SpanHead(backbone.config.hidden_size).to(device)
    optimizer = torch.optim.AdamW(head.parameters(), lr=args.learning_rate)
    train_windows = make_windows(read_records(args.train), args.max_residues)
    validation_windows = make_windows(read_records(args.validation), args.max_residues)
    output.mkdir(parents=True, exist_ok=True)
    source_hash = file_hash(Path(__file__))
    config_hash = hashlib.sha256(json.dumps(vars(args), default=str, sort_keys=True).encode()).hexdigest()
    manifest = {
        "schema_version": "0.1.0", "status": "running", "created_utc": datetime.now(timezone.utc).isoformat(),
        "architecture": "frozen_esm2_residue_cnn_with_auxiliary_start_end_heads",
        "hypothesis": "Boundary supervision increases fold-4 high-precision residue recall without no-linker specificity loss >0.02",
        "expected_failure": "Boundary targets are sparse and may overfit or reduce precision",
        "model_id": args.model_id, "revision": args.revision,
        "resolved_model_commit": getattr(backbone.config, "_commit_hash", None),
        "train_sha256": train_hash, "validation_sha256": validation_hash,
        "source_sha256": source_hash, "config_sha256": config_hash,
        "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "seed": args.seed, "gpu": torch.cuda.get_device_name(0),
        "versions": {"python": sys.version.split()[0], "torch": torch.__version__,
                     "cuda": torch.version.cuda, "transformers": __import__("transformers").__version__},
        "args": {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
        "preflight": preflight_report,
        "train_windows": len(train_windows), "validation_windows": len(validation_windows),
        "selection": "best fold-4 recall at empirical precision >=0.90 with >=50 true positives; specificity guardrail checked after run",
        "limitations": "DLD binary labels only; fold 5 previously viewed; no rigid/flexible/cleavage head",
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    began = time.monotonic()
    best_recall = -1.0
    try:
        for epoch in range(args.epochs):
            if (time.monotonic() - began) / 3600 >= args.maximum_hours:
                manifest["status"] = "time_limit"
                break
            head.train()
            order = list(range(len(train_windows)))
            random.Random(args.seed + epoch).shuffle(order)
            losses = []
            for offset in range(0, len(order), args.batch_size):
                if (time.monotonic() - began) / 3600 >= args.maximum_hours:
                    manifest["status"] = "time_limit"
                    break
                group = [train_windows[index] for index in order[offset:offset + args.batch_size]]
                embeddings, targets, mask = batch_embedding(backbone, tokenizer, group, device)
                residue_logits, boundary_logits = head(embeddings)
                loss = span_loss(residue_logits, boundary_logits, targets, mask,
                                 args.positive_weight, args.boundary_weight)
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
                optimizer.step()
                losses.append(float(loss.item()))
            if manifest.get("status") == "time_limit":
                break
            metrics = evaluate(backbone, tokenizer, head, validation_windows, args.batch_size, device)
            recall = metrics["validation_precision_90_operating_point"]["recall"]
            state = {"head": head.state_dict(), "optimizer": optimizer.state_dict(),
                     "epoch": epoch + 1, "model_id": args.model_id, "revision": args.revision,
                     "architecture": manifest["architecture"], "validation": metrics,
                     "training_args": manifest["args"]}
            atomic_checkpoint(state, output / "latest.pt")
            if recall > best_recall:
                best_recall = recall
                atomic_checkpoint(state, output / "best.pt")
            with (output / "epochs.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"epoch": epoch + 1, "train_loss": sum(losses) / len(losses),
                                         "validation": metrics}) + "\n")
            print(json.dumps({"epoch": epoch + 1, "recall_at_precision_90": recall,
                              "residue_auprc": metrics["residue_auprc"]}), flush=True)
        if manifest["status"] == "running":
            manifest["status"] = "completed"
        manifest["best_validation_recall_at_precision_90"] = best_recall
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
        manifest["gpu_hours_wall_clock"] = (time.monotonic() - began) / 3600
        manifest["peak_vram_bytes"] = torch.cuda.max_memory_allocated()
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
