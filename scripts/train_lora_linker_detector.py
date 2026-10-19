"""ESM-2 35M LoRA detector trial on frozen DLD train/development folds.

This is a separate PEFT architecture experiment; it does not modify the
frozen-embedding baseline or treat DLD fold 5 as blind model-selection data.
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

import torch
from torch.nn import functional as F
from peft import LoraConfig
from transformers import AutoModel, AutoTokenizer

from preflight_detector_data import preflight
from train_esm2_linker_detector import atomic_checkpoint, file_hash, make_windows, read_records
from train_span_linker_detector import SpanHead, evaluate


TRAIN_SHA = "c43952c4f943f458ba61905c34a59e04fadca5607b95d6afc9bd9d1475252c41"
VALIDATION_SHA = "290992af4a93c14ba007197c282367734af8ec878783d5e668ee4960128a3461"


def embeddings_and_targets(backbone, tokenizer, group, device):
    sequences = [item[0] for item in group]
    encoded = tokenizer(sequences, return_tensors="pt", padding=True,
                        add_special_tokens=True, truncation=False)
    encoded = {key: value.to(device) for key, value in encoded.items()}
    hidden = backbone(**encoded).last_hidden_state
    embeddings = hidden[:, 1:1 + max(map(len, sequences))]
    targets = torch.zeros(embeddings.shape[:2], device=device)
    mask = torch.zeros_like(targets, dtype=torch.bool)
    for index, (_, labels, _) in enumerate(group):
        targets[index, :len(labels)] = torch.tensor(
            [int(value > 0) for value in labels], dtype=torch.float32, device=device)
        mask[index, :len(labels)] = True
    return embeddings, targets, mask


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-id", default="facebook/esm2_t12_35M_UR50D")
    parser.add_argument("--revision", default="6fbf070e65b0b7291e7bbcd451118c216cff79d8")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation", type=int, default=4)
    parser.add_argument("--max-residues", type=int, default=510)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--positive-weight", type=float, default=6.0)
    parser.add_argument("--lora-rank", type=int, default=8)
    parser.add_argument("--maximum-hours", type=float, default=2.0)
    parser.add_argument("--maximum-steps", type=int, default=0,
                        help="Optional smoke limit; 0 means all training windows")
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("CUDA unavailable; refusing CPU training")
    if args.epochs < 1 or args.batch_size < 1 or args.gradient_accumulation < 1:
        raise ValueError("Invalid epoch or batch configuration")
    if not 1 <= args.max_residues <= 510 or args.lora_rank < 1 or args.maximum_hours <= 0:
        raise ValueError("Invalid ESM window, LoRA rank, or time limit")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError("Isolated run output must be empty")
    if file_hash(args.train) != TRAIN_SHA or file_hash(args.validation) != VALIDATION_SHA:
        raise ValueError("Frozen DLD data hash mismatch")
    preflight_report = preflight(str(args.train), str(args.validation))
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    random.seed(args.seed)
    device = torch.device("cuda")
    tokenizer = AutoTokenizer.from_pretrained(args.model_id, revision=args.revision)
    backbone = AutoModel.from_pretrained(args.model_id, revision=args.revision).to(device)
    backbone.add_adapter(LoraConfig(r=args.lora_rank, lora_alpha=2 * args.lora_rank,
                                    lora_dropout=0.05, target_modules=["query", "value"]))
    head = SpanHead(backbone.config.hidden_size).to(device)
    optimizer = torch.optim.AdamW(
        [parameter for parameter in [*backbone.parameters(), *head.parameters()]
         if parameter.requires_grad], lr=args.learning_rate)
    train_windows = make_windows(read_records(args.train), args.max_residues)
    validation_windows = make_windows(read_records(args.validation), args.max_residues)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args_record = {key: str(value) if isinstance(value, Path) else value
                   for key, value in vars(args).items()}
    manifest = {
        "schema_version": "0.1.0", "status": "running", "created_utc": datetime.now(timezone.utc).isoformat(),
        "architecture": "esm2_35m_query_value_lora_plus_residue_cnn",
        "hypothesis": "Task-adapting ESM-2 increases high-precision linker recall over frozen embeddings",
        "expected_failure": "DLD label sparsity or 6GB VRAM may prevent a valid gain",
        "source_paper": "https://doi.org/10.1038/s41467-024-51844-2",
        "model_id": args.model_id, "revision": args.revision,
        "resolved_model_commit": getattr(backbone.config, "_commit_hash", None),
        "train_sha256": TRAIN_SHA, "validation_sha256": VALIDATION_SHA,
        "source_sha256": file_hash(Path(__file__)),
        "config_sha256": hashlib.sha256(json.dumps(args_record, sort_keys=True).encode()).hexdigest(),
        "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "seed": args.seed, "gpu": torch.cuda.get_device_name(0),
        "versions": {"python": sys.version.split()[0], "torch": torch.__version__,
                     "cuda": torch.version.cuda, "transformers": __import__("transformers").__version__,
                     "peft": __import__("peft").__version__},
        "args": args_record, "preflight": preflight_report,
        "train_windows": len(train_windows), "validation_windows": len(validation_windows),
        "selection": "best fold-4 recall at empirical precision >=0.90 with >=50 TP; specificity guardrail",
        "limitations": "DLD binary labels only; fold 5 previously viewed; no independent test",
    }
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
            backbone.train()
            head.train()
            order = list(range(len(train_windows)))
            random.Random(args.seed + epoch).shuffle(order)
            losses = []
            optimizer.zero_grad(set_to_none=True)
            pending = 0
            for offset in range(0, len(order), args.batch_size):
                if (time.monotonic() - began) / 3600 >= args.maximum_hours:
                    manifest["status"] = "time_limit"
                    break
                if args.maximum_steps and steps >= args.maximum_steps:
                    manifest["status"] = "step_limit"
                    break
                group = [train_windows[index] for index in order[offset:offset + args.batch_size]]
                embeddings, targets, mask = embeddings_and_targets(backbone, tokenizer, group, device)
                residue_logits, _ = head(embeddings)
                loss = F.binary_cross_entropy_with_logits(
                    residue_logits[mask], targets[mask],
                    pos_weight=torch.tensor(args.positive_weight, device=device))
                (loss / args.gradient_accumulation).backward()
                losses.append(float(loss.item()))
                pending += 1
                steps += 1
                if pending == args.gradient_accumulation or offset + args.batch_size >= len(order):
                    torch.nn.utils.clip_grad_norm_(
                        [p for p in [*backbone.parameters(), *head.parameters()] if p.requires_grad], 1.0)
                    optimizer.step()
                    optimizer.zero_grad(set_to_none=True)
                    pending = 0
            if manifest.get("status") in ("time_limit", "step_limit"):
                break
            backbone.eval()
            metrics = evaluate(backbone, tokenizer, head, validation_windows, args.batch_size, device)
            recall = metrics["validation_precision_90_operating_point"]["recall"]
            checkpoint = {
                "backbone": backbone.state_dict(), "head": head.state_dict(),
                "optimizer": optimizer.state_dict(), "epoch": epoch + 1,
                "model_id": args.model_id, "revision": args.revision,
                "architecture": manifest["architecture"], "validation": metrics,
                "training_args": args_record,
            }
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
