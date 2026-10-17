"""Frozen ESM-2 residue embeddings plus a trainable linker head.

Reference-only experiment: source DLD folds 1-3 train, fold 4 validation.
Fold 5 is never opened here. The model is not LINKER-Pred2 reproduction;
it tests the protein-language-model strategy with a smaller local backbone.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
from uuid import uuid4

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from sklearn.metrics import average_precision_score, roc_auc_score
from transformers import AutoModel, AutoTokenizer

from preflight_detector_data import preflight


class ResidueHead(nn.Module):
    def __init__(self, embedding_dim: int, width: int = 128) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Conv1d(embedding_dim, width, 5, padding=2), nn.GELU(),
            nn.Conv1d(width, width, 5, padding=2), nn.GELU(),
            nn.Conv1d(width, 1, 1),
        )

    def forward(self, embeddings: torch.Tensor) -> torch.Tensor:
        return self.network(embeddings.transpose(1, 2)).squeeze(1)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_records(path: Path) -> list[dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def make_windows(records: list[dict], max_residues: int) -> list[tuple[str, list[int], str]]:
    windows = []
    for row in records:
        sequence = row["sequence"]
        labels = row["labels"]
        for start in range(0, len(sequence), max_residues):
            end = min(start + max_residues, len(sequence))
            windows.append((sequence[start:end], labels[start:end], row["source_id"]))
    return windows


def batch_embedding(backbone, tokenizer, group, device):
    sequences = [item[0] for item in group]
    encoded = tokenizer(sequences, return_tensors="pt", padding=True,
                        add_special_tokens=True, truncation=False)
    encoded = {key: value.to(device) for key, value in encoded.items()}
    with torch.no_grad():
        hidden = backbone(**encoded).last_hidden_state
    # ESM tokenizers put a BOS token before the first amino acid.
    embeddings = hidden[:, 1:1 + max(map(len, sequences))]
    targets = torch.zeros(embeddings.shape[:2], device=device)
    mask = torch.zeros_like(targets, dtype=torch.bool)
    for index, (_, labels, _) in enumerate(group):
        targets[index, :len(labels)] = torch.tensor(
            [int(value > 0) for value in labels], dtype=torch.float32, device=device)
        mask[index, :len(labels)] = True
    return embeddings, targets, mask


def atomic_checkpoint(state: dict, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{target.name}.{uuid4().hex}.tmp")
    torch.save(state, temporary)
    for attempt in range(6):
        try:
            os.replace(temporary, target)
            return
        except OSError as exc:
            if getattr(exc, "winerror", None) not in (5, 32, 33) or attempt == 5:
                raise
            time.sleep(0.25 * 2 ** attempt)


def classification_loss(logits: torch.Tensor, targets: torch.Tensor,
                        positive_weight: float, focal_gamma: float,
                        loss_name: str = "focal") -> torch.Tensor:
    """Controlled imbalance-loss adaptations on the same valid residues."""
    if focal_gamma < 0:
        raise ValueError("focal_gamma must be non-negative")
    if loss_name not in {"focal", "asymmetric", "bce_tversky", "hard_negative"}:
        raise ValueError(f"Unsupported loss: {loss_name}")
    per_residue = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
    weights = torch.where(targets > 0, positive_weight, 1.0)
    probability = logits.sigmoid()
    if loss_name == "focal" and focal_gamma:
        correct_class_probability = torch.where(targets > 0, probability, 1 - probability)
        weights = weights * (1 - correct_class_probability).pow(focal_gamma)
    if loss_name == "asymmetric":
        # Binary adaptation of asymmetric focusing: harder negatives receive
        # larger weight, while the positive term remains ordinary weighted BCE.
        weights = weights * torch.where(targets > 0, 1.0,
                                        probability.pow(focal_gamma))
    if loss_name == "hard_negative":
        # OHEM adaptation: retain all positives and at most 3 hard negatives
        # per positive, with a 64-negative floor for all-negative batches.
        positives = targets > 0
        negative_indices = torch.nonzero(~positives, as_tuple=False).flatten()
        negative_budget = max(64, 3 * int(positives.sum().item()))
        if len(negative_indices) > negative_budget:
            top = torch.topk(per_residue[negative_indices], negative_budget).indices
            selected = positives.clone()
            selected[negative_indices[top]] = True
            per_residue = per_residue[selected]
            weights = weights[selected]
    weighted_bce = (weights * per_residue).mean()
    if loss_name != "bce_tversky":
        return weighted_bce
    # A 1-D segment analogue of medical-image Tversky loss. Keep BCE for
    # calibrated residue scores and add overlap pressure within each batch.
    true_positive = (probability * targets).sum()
    false_positive = (probability * (1 - targets)).sum()
    false_negative = ((1 - probability) * targets).sum()
    tversky = 1 - (true_positive + 1.0) / (
        true_positive + 0.7 * false_positive + 0.3 * false_negative + 1.0)
    return weighted_bce + 0.5 * tversky


def high_precision_operating_point(truth: np.ndarray, scores: np.ndarray,
                                   minimum_precision: float = 0.90,
                                   minimum_true_positives: int = 50) -> dict:
    """Choose maximum validation recall subject to empirical precision."""
    if not 0 < minimum_precision <= 1:
        raise ValueError("minimum_precision must be in (0, 1]")
    if minimum_true_positives < 1:
        raise ValueError("minimum_true_positives must be positive")
    order = np.argsort(-scores, kind="stable")
    ranked_scores = scores[order]
    ranked_truth = truth[order]
    true_positives = np.cumsum(ranked_truth == 1)
    predicted_positives = np.arange(1, len(scores) + 1)
    precision = true_positives / predicted_positives
    distinct_ends = np.r_[ranked_scores[1:] != ranked_scores[:-1], True]
    eligible = np.flatnonzero(distinct_ends & (precision >= minimum_precision) &
                              (true_positives >= minimum_true_positives))
    if len(eligible) == 0:
        return {"target_precision": minimum_precision,
                "minimum_true_positives": minimum_true_positives,
                "threshold": None,
                "precision": None, "recall": 0.0, "true_positives": 0,
                "false_positives": 0}
    index = int(eligible[np.argmax(true_positives[eligible])])
    tp = int(true_positives[index])
    return {"target_precision": minimum_precision,
            "minimum_true_positives": minimum_true_positives,
            "threshold": float(ranked_scores[index]),
            "precision": float(precision[index]),
            "recall": tp / int(np.count_nonzero(truth == 1)),
            "true_positives": tp,
            "false_positives": int(predicted_positives[index] - tp)}


@torch.no_grad()
def evaluate(backbone, tokenizer, head, windows, batch_size, device):
    head.eval()
    truth = []
    scores = []
    protein_truth: dict[str, bool] = {}
    protein_max: dict[str, float] = {}
    for offset in range(0, len(windows), batch_size):
        group = windows[offset:offset + batch_size]
        embeddings, targets, mask = batch_embedding(backbone, tokenizer, group, device)
        probabilities = head(embeddings).sigmoid()
        for index, (_, _, source_id) in enumerate(group):
            valid = mask[index]
            observed = targets[index, valid].cpu().numpy()
            predicted = probabilities[index, valid].cpu().numpy()
            truth.extend(observed.tolist())
            scores.extend(predicted.tolist())
            protein_truth[source_id] = protein_truth.get(source_id, False) or bool(observed.any())
            protein_max[source_id] = max(protein_max.get(source_id, 0.0), float(predicted.max()))
    truth = np.asarray(truth, dtype=np.uint8)
    scores = np.asarray(scores, dtype=np.float32)
    if not np.any(truth) or np.all(truth):
        raise ValueError("Validation needs positive and negative residues")
    metrics = {"residue_auprc": float(average_precision_score(truth, scores)),
               "residue_auroc": float(roc_auc_score(truth, scores)),
               "positive_residues": int(truth.sum()), "residues": int(len(truth)),
               "proteins": int(len(protein_truth))}
    metrics["validation_precision_90_operating_point"] = high_precision_operating_point(truth, scores)
    # Select the operating point on validation only. Never tune against blind.
    best = None
    for threshold in np.linspace(0.01, 0.99, 99):
        predicted = scores >= threshold
        tp = int(np.count_nonzero(predicted & (truth == 1)))
        fp = int(np.count_nonzero(predicted & (truth == 0)))
        fn = int(np.count_nonzero(~predicted & (truth == 1)))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        negatives = [key for key, value in protein_truth.items() if not value]
        specificity = sum(protein_max[key] < threshold for key in negatives) / len(negatives)
        candidate = {"threshold": round(float(threshold), 3), "precision": precision,
                     "recall": recall, "f1": f1,
                     "no_linker_protein_specificity": specificity}
        if best is None or candidate["f1"] > best["f1"]:
            best = candidate
    metrics["validation_selected_operating_point"] = best
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--model-id", default="facebook/esm2_t6_8M_UR50D")
    parser.add_argument("--revision", default="main")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-residues", type=int, default=510)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--seed", type=int, default=7,
                        help="Training seed; default 7 reproduces the original reference")
    parser.add_argument("--positive-weight", type=float, default=6.0)
    parser.add_argument("--focal-gamma", type=float, default=0.0,
                        help="0 preserves weighted BCE; positive values test focal loss")
    parser.add_argument("--loss-name", choices=("focal", "asymmetric", "bce_tversky", "hard_negative"),
                        default="focal")
    parser.add_argument("--resume", type=Path)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("CUDA GPU unavailable; refusing CPU training")
    if args.epochs < 1 or args.batch_size < 1 or not 1 <= args.max_residues <= 510:
        raise ValueError("Invalid epochs, batch size or ESM window length")
    if args.positive_weight <= 0 or args.focal_gamma < 0:
        raise ValueError("positive weight must be positive and focal gamma non-negative")
    preflight_report = preflight(str(args.train), str(args.validation))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda")
    torch.manual_seed(args.seed)
    random.seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    tokenizer = AutoTokenizer.from_pretrained(args.model_id, revision=args.revision)
    backbone = AutoModel.from_pretrained(args.model_id, revision=args.revision).to(device).eval()
    backbone.requires_grad_(False)
    head = ResidueHead(backbone.config.hidden_size).to(device)
    optimizer = torch.optim.AdamW(head.parameters(), lr=args.learning_rate)
    train_windows = make_windows(read_records(args.train), args.max_residues)
    validation_windows = make_windows(read_records(args.validation), args.max_residues)
    start_epoch = 0
    best_ap = -1.0
    if args.resume:
        state = torch.load(args.resume, map_location=device, weights_only=False)
        if state["model_id"] != args.model_id or state["revision"] != args.revision:
            raise ValueError("Resume checkpoint uses a different backbone")
        prior_gamma = float(state.get("training_args", {}).get("focal_gamma", 0.0))
        prior_loss = state.get("training_args", {}).get("loss_name", "focal")
        if prior_gamma != args.focal_gamma or prior_loss != args.loss_name:
            raise ValueError("Resume checkpoint uses a different loss setting")
        head.load_state_dict(state["head"])
        optimizer.load_state_dict(state["optimizer"])
        start_epoch = int(state["epoch"])
        best_ap = float(state["best_validation_auprc"])
    manifest = {"schema_version": "0.1.0", "status": "running", "created_utc": datetime.now(timezone.utc).isoformat(),
                "model_id": args.model_id, "revision": args.revision,
                "resolved_model_commit": getattr(backbone.config, "_commit_hash", None),
                "architecture": "frozen_esm2_with_trainable_residue_cnn",
                "loss": {"name": "weighted_bce" if args.loss_name == "focal" and not args.focal_gamma
                         else args.loss_name,
                         "positive_weight": args.positive_weight, "focal_gamma": args.focal_gamma},
                "train_sha256": file_hash(args.train), "validation_sha256": file_hash(args.validation),
                "preflight": preflight_report,
                "train_windows": len(train_windows), "validation_windows": len(validation_windows),
                "versions": {"python": sys.version.split()[0], "torch": torch.__version__,
                             "cuda": torch.version.cuda,
                             "transformers": __import__("transformers").__version__},
                "gpu": torch.cuda.get_device_name(0), "seed": args.seed,
                "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "note": "DLD reference-label training only; CAID3 performance not yet measured."}
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    history_path = args.output_dir / "epochs.jsonl"
    try:
        for epoch in range(start_epoch, args.epochs):
            head.train()
            order = list(range(len(train_windows)))
            random.Random(args.seed + epoch).shuffle(order)
            losses = []
            for offset in range(0, len(order), args.batch_size):
                group = [train_windows[index] for index in order[offset:offset + args.batch_size]]
                embeddings, targets, mask = batch_embedding(backbone, tokenizer, group, device)
                logits = head(embeddings)
                loss = classification_loss(logits[mask], targets[mask],
                                           args.positive_weight, args.focal_gamma,
                                           args.loss_name)
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
                optimizer.step()
                losses.append(float(loss.item()))
            metrics = evaluate(backbone, tokenizer, head, validation_windows,
                               args.batch_size, device)
            score = metrics["residue_auprc"]
            best_ap = max(best_ap, score)
            state = {"head": head.state_dict(), "optimizer": optimizer.state_dict(),
                     "epoch": epoch + 1, "model_id": args.model_id, "revision": args.revision,
                     "best_validation_auprc": best_ap, "validation": metrics,
                     "training_args": vars(args)}
            atomic_checkpoint(state, args.output_dir / "latest.pt")
            if score >= best_ap:
                atomic_checkpoint(state, args.output_dir / "best.pt")
            report = {"schema_version": "0.1.0", "epoch": epoch + 1, "train_loss": sum(losses) / len(losses),
                      "validation": metrics}
            with history_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(report) + "\n")
            print(json.dumps(report), flush=True)
        manifest["status"] = "completed"
        manifest["best_validation_auprc"] = best_ap
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
