"""Bounded frozen-ESM2 plus dedicated BiLSTM DLD linker-residue trial."""

from __future__ import annotations

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
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence
from sklearn.metrics import average_precision_score, roc_auc_score
from transformers import AutoModel, AutoTokenizer

from preflight_detector_data import preflight
from train_esm2_linker_detector import (
    atomic_checkpoint, batch_embedding, file_hash, high_precision_operating_point,
    make_windows, read_records,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from linkerforge.detector.evaluation import region_metrics  # noqa: E402

TRAIN_SHA = "c43952c4f943f458ba61905c34a59e04fadca5607b95d6afc9bd9d1475252c41"
VALIDATION_SHA = "290992af4a93c14ba007197c282367734af8ec878783d5e668ee4960128a3461"


class BiLSTMHead(nn.Module):
    def __init__(self, embedding_dim: int, hidden_size: int = 128) -> None:
        super().__init__()
        self.lstm = nn.LSTM(embedding_dim, hidden_size, batch_first=True, bidirectional=True)
        self.output = nn.Linear(hidden_size * 2, 1)

    def forward(self, embeddings: torch.Tensor, lengths: list[int]) -> torch.Tensor:
        if len(lengths) != embeddings.shape[0] or min(lengths) < 1:
            raise ValueError("Invalid sequence lengths")
        packed = pack_padded_sequence(embeddings, lengths, batch_first=True, enforce_sorted=False)
        encoded, _ = self.lstm(packed)
        padded, _ = pad_packed_sequence(encoded, batch_first=True, total_length=embeddings.shape[1])
        return self.output(padded).squeeze(-1)


@torch.no_grad()
def evaluate(backbone, tokenizer, head, windows, batch_size, device) -> dict:
    backbone.eval()
    head.eval()
    truth_by_protein: dict[str, list[bool]] = {}
    score_by_protein: dict[str, list[float]] = {}
    for offset in range(0, len(windows), batch_size):
        group = windows[offset:offset + batch_size]
        embeddings, targets, mask = batch_embedding(backbone, tokenizer, group, device)
        scores = head(embeddings, [len(row[0]) for row in group]).sigmoid()
        for index, (_, _, source_id) in enumerate(group):
            truth_by_protein.setdefault(source_id, []).extend(
                bool(value) for value in targets[index, mask[index]].cpu().tolist())
            score_by_protein.setdefault(source_id, []).extend(scores[index, mask[index]].cpu().tolist())
    truth = np.asarray([value for sequence in truth_by_protein.values() for value in sequence], dtype=np.uint8)
    score = np.asarray([value for sequence in score_by_protein.values() for value in sequence], dtype=np.float32)
    point = high_precision_operating_point(truth, score)
    threshold = point["threshold"]
    negatives = [key for key, flags in truth_by_protein.items() if not any(flags)]
    specificity = (sum(max(score_by_protein[key]) < threshold for key in negatives) / len(negatives)
                   if threshold is not None and negatives else None)
    return {
        "residue_auprc": float(average_precision_score(truth, score)),
        "residue_auroc": float(roc_auc_score(truth, score)),
        "positive_residues": int(truth.sum()), "residues": len(truth),
        "proteins": len(truth_by_protein),
        "validation_precision_90_operating_point": point,
        "no_linker_protein_specificity": specificity,
        "region_metrics_iou_0_5": (region_metrics(truth_by_protein, score_by_protein, threshold)
                                     if threshold is not None else None),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-id", default="facebook/esm2_t12_35M_UR50D")
    parser.add_argument("--revision", default="6fbf070e65b0b7291e7bbcd451118c216cff79d8")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-residues", type=int, default=510)
    parser.add_argument("--hidden-size", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--positive-weight", type=float, default=6.0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--maximum-hours", type=float, default=2.0)
    parser.add_argument("--maximum-steps", type=int, default=0, help="Smoke-test limit; 0 means full training")
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; refusing CPU training")
    if args.epochs < 1 or args.batch_size < 1 or args.hidden_size < 1 or not 1 <= args.max_residues <= 510:
        raise ValueError("Invalid training dimensions")
    if args.maximum_hours <= 0 or args.maximum_hours > 2 or args.positive_weight <= 0:
        raise ValueError("Job budget or positive weight invalid")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError("Run output must be isolated and empty")
    train_sha, validation_sha = file_hash(args.train), file_hash(args.validation)
    if (train_sha, validation_sha) != (TRAIN_SHA, VALIDATION_SHA):
        raise ValueError("Frozen data hash mismatch")
    preflight_report = preflight(str(args.train), str(args.validation))
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    random.seed(args.seed)
    device = torch.device("cuda")
    tokenizer = AutoTokenizer.from_pretrained(args.model_id, revision=args.revision)
    backbone = AutoModel.from_pretrained(args.model_id, revision=args.revision).to(device).eval()
    backbone.requires_grad_(False)
    head = BiLSTMHead(backbone.config.hidden_size, args.hidden_size).to(device)
    optimizer = torch.optim.AdamW(head.parameters(), lr=args.learning_rate)
    train_windows = make_windows(read_records(args.train), args.max_residues)
    validation_windows = make_windows(read_records(args.validation), args.max_residues)
    args_record = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()}
    manifest = {
        "schema_version": "0.1.0", "status": "running", "created_utc": datetime.now(timezone.utc).isoformat(),
        "architecture": "frozen_esm2_35m_dedicated_bilstm_head",
        "hypothesis": "Bidirectional sequence context improves high-precision DLD linker recall over the frozen-embedding CNN",
        "expected_failure": "Overfit or no qualifying high-precision operating point",
        "literature_basis": "https://doi.org/10.1093/bib/bbag126",
        "adaptation_note": "ESM-2 rather than ProtT5; binary DLD label task rather than the paper's multitask setting",
        "model_id": args.model_id, "revision": args.revision,
        "resolved_model_commit": getattr(backbone.config, "_commit_hash", None),
        "train_sha256": train_sha, "validation_sha256": validation_sha,
        "source_sha256": file_hash(Path(__file__)),
        "config_sha256": hashlib.sha256(json.dumps(args_record, sort_keys=True).encode()).hexdigest(),
        "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "seed": args.seed, "gpu": torch.cuda.get_device_name(0),
        "versions": {"python": sys.version.split()[0], "torch": torch.__version__,
                     "cuda": torch.version.cuda, "transformers": __import__("transformers").__version__},
        "args": args_record, "preflight": preflight_report,
        "train_windows": len(train_windows), "validation_windows": len(validation_windows),
        "selection": "best fold-4 recall at empirical precision >=0.90 with >=50 TP; specificity guardrail",
        "limitations": "DLD binary labels only; fold 5 viewed; no independent test",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    began = time.monotonic()
    best_recall = -1.0
    steps = 0
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
                if args.maximum_steps and steps >= args.maximum_steps:
                    manifest["status"] = "step_limit"
                    break
                group = [train_windows[index] for index in order[offset:offset + args.batch_size]]
                embeddings, targets, mask = batch_embedding(backbone, tokenizer, group, device)
                logits = head(embeddings, [len(row[0]) for row in group])
                loss = F.binary_cross_entropy_with_logits(
                    logits[mask], targets[mask], pos_weight=torch.tensor(args.positive_weight, device=device))
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
                optimizer.step()
                losses.append(float(loss.item()))
                steps += 1
            if manifest["status"] in ("time_limit", "step_limit"):
                break
            metrics = evaluate(backbone, tokenizer, head, validation_windows, args.batch_size, device)
            recall = metrics["validation_precision_90_operating_point"]["recall"]
            checkpoint = {"head": head.state_dict(), "optimizer": optimizer.state_dict(),
                          "epoch": epoch + 1, "model_id": args.model_id, "revision": args.revision,
                          "architecture": manifest["architecture"], "validation": metrics,
                          "training_args": args_record}
            atomic_checkpoint(checkpoint, args.output_dir / "latest.pt")
            if recall > best_recall:
                best_recall = recall
                atomic_checkpoint(checkpoint, args.output_dir / "best.pt")
            with (args.output_dir / "epochs.jsonl").open("a", encoding="utf-8") as stream:
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
        manifest["completed_steps"] = steps
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
