"""Matched direct-vs-IDR-transfer pilot for SAM-like and YOLO-1D DFL heads.

One process/trial and one GPU at a time. The suite launcher runs 12 isolated
trials sequentially, not concurrently. TE82 is development; TE64/CAID3 are
not read. This adapts TransDFL's transfer *idea*, not its exact weights/data.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

import numpy as np
import torch
from sklearn.metrics import average_precision_score, roc_auc_score
from transformers import AutoModel, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from train_dfl_masked_cnn import DATA_MANIFEST, DEV, MODEL_ID, TRAIN, embed_group, preflight, sha, windows
from train_dfl_promptable_segmenter import targets as sam_targets
from train_dfl_masked_span import clean_spans
from train_esm2_linker_detector import atomic_checkpoint, high_precision_operating_point
from linkerforge.models.promptable_linker_segmenter import PromptableLinkerSegmenter, segmenter_loss
from linkerforge.models.yolo1d_linker_segmenter import Yolo1DLinkerSegmenter, yolo1d_loss

CONFIG_PATH = ROOT / "configs/dfl_disorder_transfer_autoresearch_2026-10-13.json"
AUX = ROOT / "data/processed/disorder_transfer_pilot_v1/pretrain.jsonl"
AUX_MANIFEST = AUX.parent / "manifest.json"
SUITE_ROOT = ROOT / "artifacts/dfl-disorder-transfer-2026-10-13"


def configure_head(arch: str, dimension: int, device: torch.device):
    if arch == "samlike":
        return PromptableLinkerSegmenter(dimension).to(device)
    if arch == "yolo1d":
        return Yolo1DLinkerSegmenter(dimension).to(device)
    raise ValueError(arch)


def target_batch(group, device):
    valid, residue, presence, spans, exhaustive, concept = sam_targets(group, device)
    return valid, residue, presence, spans, exhaustive, concept


def forward_loss(arch, head, embeddings, group, device, *, auxiliary=False):
    valid, residue, presence, spans, exhaustive, concept = target_batch(group, device)
    if arch == "samlike":
        output = head(embeddings, valid, concept)
        if auxiliary:
            known = valid & (residue >= 0)
            loss = torch.nn.functional.binary_cross_entropy_with_logits(
                output["semantic_logits"][known], residue[known].float())
        else:
            loss = segmenter_loss(output, valid, residue, presence, spans, exhaustive)["total"]
    else:
        output = head(embeddings, valid)
        if auxiliary:
            known = valid & (residue >= 0)
            loss = torch.nn.functional.binary_cross_entropy_with_logits(
                output["semantic_logits"][:, :, 0][known], residue[known].float())
        else:
            loss = yolo1d_loss(output, valid, residue, spans)["total"]
    return loss


@torch.no_grad()
def evaluate(arch, backbone, tokenizer, head, examples, batch_size, device):
    head.eval()
    all_truth, all_scores = [], []
    by_protein = {}
    for offset in range(0, len(examples), batch_size):
        group = examples[offset:offset + batch_size]
        embeddings, _, _ = embed_group(backbone, tokenizer, group, device)
        valid, residue, _, _, _, concept = target_batch(group, device)
        output = head(embeddings, valid, concept) if arch == "samlike" else head(embeddings, valid)
        scores = (output["semantic_logits"] if arch == "samlike" else output["semantic_logits"][:, :, 0]).sigmoid()
        for index, (_, labels, protein_id) in enumerate(group):
            n = len(labels)
            values = scores[index, :n].cpu().numpy().tolist()
            known = [c != "x" for c in labels]
            all_truth.extend(int(c == "1") for c in labels if c != "x")
            all_scores.extend(score for score, yes in zip(values, known) if yes)
            saved = by_protein.setdefault(protein_id, {"labels": "", "scores": []})
            saved["labels"] += labels
            saved["scores"].extend(values)
    truth = np.asarray(all_truth, dtype=np.uint8)
    prediction = np.asarray(all_scores, dtype=np.float32)
    point = high_precision_operating_point(truth, prediction)
    threshold = point["threshold"]
    negative = [row for row in by_protein.values() if "1" not in row["labels"]]
    specificity = None
    if threshold is not None and negative:
        specificity = sum(max((score for score, c in zip(row["scores"], row["labels"]) if c != "x"), default=0) < threshold
                          for row in negative) / len(negative)
    gold_count = recovered = 0
    for row in by_protein.values():
        gold = clean_spans(row["labels"], "1")
        predicted = clean_spans("".join("1" if score >= 0.5 else "0" for score in row["scores"]), "1")
        for a, b in gold:
            gold_count += 1
            if any(max(0, min(b, d) - max(a, c) + 1) / (max(b, d) - min(a, c) + 1) >= 0.5
                   for c, d in predicted):
                recovered += 1
    return {"masked_residue_aps": float(average_precision_score(truth, prediction)),
            "masked_residue_auroc": float(roc_auc_score(truth, prediction)),
            "positive_residues": int(truth.sum()), "negative_residues": int(len(truth) - truth.sum()),
            "precision_90_operating_point": point,
            "no_positive_protein_proxy_specificity": specificity,
            "region_recall_iou_0.5_at_threshold_0.5": recovered / gold_count if gold_count else None,
            "region_recovered": recovered, "region_gold": gold_count}


def run_trial(args):
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if args.arch not in config["architecture"] or args.condition not in config["conditions"] or args.seed not in config["seeds"]:
        raise ValueError("Trial not in frozen config")
    if args.output_dir.exists():
        raise FileExistsError(f"Refusing existing output: {args.output_dir}")
    train, dev = preflight()
    aux_manifest = json.loads(AUX_MANIFEST.read_text(encoding="utf-8"))
    if aux_manifest["files"]["pretrain"]["sha256"] != sha(AUX):
        raise ValueError("Auxiliary data hash mismatch")
    aux = [json.loads(line) for line in AUX.read_text(encoding="utf-8").splitlines()]
    if not aux or any(row["status"] != "eligible_for_development_pilot" or set(row["labels"]) - {"0", "1"} for row in aux):
        raise ValueError("Auxiliary data invalid or empty")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; CPU training refused")
    args.output_dir.mkdir(parents=True)
    device = torch.device("cuda")
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    np.random.seed(args.seed)
    random.seed(args.seed)
    start = time.monotonic()
    manifest = {"schema_version": "1.0.0", "status": "initializing", "arch": args.arch,
                "condition": args.condition, "seed": args.seed, "config_sha256": sha(CONFIG_PATH),
                "train_sha256": sha(TRAIN), "dev_sha256": sha(DEV), "aux_sha256": sha(AUX),
                "aux_manifest_sha256": sha(AUX_MANIFEST), "data_manifest_sha256": sha(DATA_MANIFEST),
                "source_sha256": sha(Path(__file__)), "pipeline_commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "model_id": MODEL_ID, "gpu": torch.cuda.get_device_name(0),
                "started_utc": datetime.now(timezone.utc).isoformat(),
                "max_seconds": args.max_seconds,
                "versions": {"python": sys.version.split()[0], "torch": torch.__version__,
                             "transformers": __import__("transformers").__version__},
                "claim_status": "development_pilot_not_independent"}
    target = args.output_dir / "manifest.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        backbone = AutoModel.from_pretrained(MODEL_ID).to(device).eval()
        backbone.requires_grad_(False)
        head = configure_head(args.arch, backbone.config.hidden_size, device)
        optimizer = torch.optim.AdamW(head.parameters(), lr=config["learning_rate"])
        batch_size = config["batch_size"][args.arch]
        aux_windows = windows(aux, config["max_residues_per_window"])
        train_windows = windows(train, config["max_residues_per_window"])
        dev_windows = windows(dev, config["max_residues_per_window"])
        manifest["status"] = "running"
        target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        best = -1.0
        stages = []
        if args.condition == "disorder_transfer":
            stages.append(("auxiliary_IDR", aux_windows, config["auxiliary_semantic_epochs"]))
        stages.append(("DFL", train_windows, config["dfl_finetune_epochs"]))
        for stage, examples, epochs in stages:
            for epoch in range(epochs):
                if time.monotonic() - start > args.max_seconds:
                    manifest["status"] = "time_limit"
                    break
                head.train()
                order = list(range(len(examples)))
                random.Random(args.seed + epoch + (1000 if stage == "DFL" else 0)).shuffle(order)
                losses = []
                for offset in range(0, len(order), batch_size):
                    if time.monotonic() - start > args.max_seconds:
                        manifest["status"] = "time_limit"
                        break
                    group = [examples[i] for i in order[offset:offset + batch_size]]
                    embeddings, _, _ = embed_group(backbone, tokenizer, group, device)
                    loss = forward_loss(args.arch, head, embeddings, group, device,
                                        auxiliary=stage == "auxiliary_IDR")
                    optimizer.zero_grad(set_to_none=True)
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
                    optimizer.step()
                    losses.append(float(loss.item()))
                if manifest["status"] == "time_limit":
                    break
                record = {"stage": stage, "epoch": epoch + 1, "train_loss": sum(losses) / len(losses)}
                if stage == "DFL":
                    metrics = evaluate(args.arch, backbone, tokenizer, head, dev_windows, batch_size, device)
                    record["development"] = metrics
                    if metrics["masked_residue_aps"] > best:
                        best = metrics["masked_residue_aps"]
                        atomic_checkpoint({"head": head.state_dict(), "epoch": epoch + 1,
                                           "arch": args.arch, "condition": args.condition,
                                           "development": metrics}, args.output_dir / "best.pt")
                        manifest["best_development"] = metrics
                        manifest["best_epoch"] = epoch + 1
                with (args.output_dir / "epochs.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record) + "\n")
                manifest["completed_stage"] = stage
                manifest["completed_epoch"] = epoch + 1
                target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
                print(json.dumps({"stage": stage, "epoch": epoch + 1,
                                  "development_aps": record.get("development", {}).get("masked_residue_aps")}), flush=True)
            if manifest["status"] == "time_limit":
                break
        if manifest["status"] == "running":
            manifest["status"] = "completed"
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        manifest["elapsed_seconds"] = round(time.monotonic() - start, 3)
        manifest["peak_pytorch_vram_bytes"] = torch.cuda.max_memory_allocated()
        target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def run_suite(args):
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if args.output_dir.exists():
        raise FileExistsError("Suite output exists; refusing duplicate launch")
    args.output_dir.mkdir(parents=True)
    start = time.monotonic()
    ledger = {"status": "running", "config_sha256": sha(CONFIG_PATH), "runs": [],
              "started_utc": datetime.now(timezone.utc).isoformat()}
    ledger_path = args.output_dir / "ledger.json"
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    for seed in config["seeds"]:
        for arch in config["architecture"]:
            for condition in config["conditions"]:
                remaining = config["max_gpu_hours_total"] * 3600 - (time.monotonic() - start)
                if remaining <= 0:
                    ledger["status"] = "time_budget_exhausted"
                    break
                name = f"{arch}-{condition}-seed{seed}"
                trial_dir = args.output_dir / name
                cmd = [sys.executable, str(Path(__file__).resolve()), "trial", "--arch", arch,
                       "--condition", condition, "--seed", str(seed), "--output-dir", str(trial_dir),
                       "--max-seconds", str(min(remaining, 1800))]
                with (args.output_dir / f"{name}.log").open("w", encoding="utf-8") as log:
                    completed = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=min(remaining, 1800) + 60)
                result = {"name": name, "exit_code": completed.returncode,
                          "manifest": str(trial_dir / "manifest.json")}
                ledger["runs"].append(result)
                ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
                if completed.returncode:
                    ledger["status"] = "stopped_on_trial_failure"
                    break
            if ledger["status"] != "running":
                break
        if ledger["status"] != "running":
            break
    if ledger["status"] == "running":
        ledger["status"] = "completed"
    ledger["elapsed_seconds"] = round(time.monotonic() - start, 3)
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    trial = sub.add_parser("trial")
    trial.add_argument("--arch", required=True, choices=("samlike", "yolo1d"))
    trial.add_argument("--condition", required=True, choices=("direct", "disorder_transfer"))
    trial.add_argument("--seed", required=True, type=int)
    trial.add_argument("--output-dir", required=True, type=Path)
    trial.add_argument("--max-seconds", type=float, default=1800)
    suite = sub.add_parser("suite")
    suite.add_argument("--output-dir", type=Path, default=SUITE_ROOT)
    args = parser.parse_args()
    if args.mode == "trial":
        run_trial(args)
    else:
        run_suite(args)


if __name__ == "__main__":
    main()
