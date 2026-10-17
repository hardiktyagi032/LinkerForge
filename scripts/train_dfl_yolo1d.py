"""Bounded YOLO-style 1D DFL trial on frozen published TR166/TE82 masks.

Only the DFL class is trained. CAID3 and TE64 are not opened. This is a
development comparison, not an independent frontier benchmark.
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
from sklearn.metrics import average_precision_score, roc_auc_score
from transformers import AutoModel, AutoTokenizer

from train_dfl_masked_cnn import (DATA_MANIFEST, DEV, MODEL_ID, TRAIN,
                                  embed_group, preflight, sha, windows)
from train_dfl_promptable_segmenter import targets
from train_esm2_linker_detector import atomic_checkpoint, high_precision_operating_point
from linkerforge.models.yolo1d_linker_segmenter import Yolo1DLinkerSegmenter, yolo1d_loss


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/yolo1d_dfl_round_2026-10-13.json"


@torch.no_grad()
def evaluate(backbone, tokenizer, head, examples, batch_size, device):
    head.eval()
    truth, scores = [], []
    protein_positive, protein_max = {}, {}
    for offset in range(0, len(examples), batch_size):
        group = examples[offset:offset + batch_size]
        embeddings, _, _ = embed_group(backbone, tokenizer, group, device)
        valid, residue, _, _, _, _ = targets(group, device)
        predicted = head(embeddings, valid)["semantic_logits"][:, :, 0].sigmoid()
        for i, (_, _, protein_id) in enumerate(group):
            known = residue[i] >= 0
            observed = residue[i][known].cpu().numpy()
            values = predicted[i][known].cpu().numpy()
            truth.extend(observed.tolist())
            scores.extend(values.tolist())
            protein_positive[protein_id] = protein_positive.get(protein_id, False) or bool(observed.any())
            if len(values):
                protein_max[protein_id] = max(protein_max.get(protein_id, 0.0), float(values.max()))
    truth = np.asarray(truth, dtype=np.uint8)
    scores = np.asarray(scores, dtype=np.float32)
    point = high_precision_operating_point(truth, scores)
    threshold = point["threshold"]
    negative_ids = [key for key, positive in protein_positive.items() if not positive]
    specificity = (sum(protein_max.get(key, 0.0) < threshold for key in negative_ids) / len(negative_ids)
                   if threshold is not None and negative_ids else None)
    return {"masked_residue_aps": float(average_precision_score(truth, scores)),
            "masked_residue_auroc": float(roc_auc_score(truth, scores)),
            "scored_residues": int(len(truth)), "positive_residues": int(truth.sum()),
            "negative_residues": int(len(truth) - truth.sum()),
            "no_positive_proteins": len(negative_ids),
            "precision_90_operating_point": point,
            "no_positive_protein_specificity_at_precision_90": specificity}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--max-hours", type=float, default=2)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--width", type=int, default=128)
    parser.add_argument("--prototypes", type=int, default=16)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    train, dev = preflight()
    configuration = json.loads(args.config.read_text(encoding="utf-8"))
    if (configuration.get("width", args.width) != args.width
            or configuration.get("prototypes", args.prototypes) != args.prototypes
            or args.seed not in configuration["seeds"]):
        raise ValueError("CLI architecture/seed differs from frozen config")
    if args.preflight_only:
        print(json.dumps({"status": "preflight_pass", "train_proteins": len(train),
                          "dev_proteins": len(dev), "train_sha256": sha(TRAIN),
                          "dev_sha256": sha(DEV)}))
        return
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; CPU training refused")
    if (args.epochs < 1 or not 0 < args.max_hours <= 2 or not 1 <= args.batch_size <= 4
            or not 16 <= args.width <= 384 or not 1 <= args.prototypes <= 64):
        raise ValueError("Trial bounds invalid")
    if args.output_dir.exists():
        raise FileExistsError("Trial output exists; refusing duplicate/overwrite")
    args.output_dir.mkdir(parents=True)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    random.seed(args.seed)
    device = torch.device("cuda")
    start = time.monotonic()
    manifest = {"schema_version": "0.1.0", "status": "initializing",
                "experiment": "yolo1d_dfl_original_split_exploratory",
                "claim_status": "development_only_not_independent",
                "seed": args.seed, "model_id": MODEL_ID,
                "width": args.width, "prototypes": args.prototypes,
                "train_sha256": sha(TRAIN), "dev_sha256": sha(DEV),
                "config_sha256": sha(args.config), "data_manifest_sha256": sha(DATA_MANIFEST),
                "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "head_source_sha256": hashlib.sha256(Path(sys.modules[Yolo1DLinkerSegmenter.__module__].__file__).read_bytes()).hexdigest(),
                "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "max_hours": args.max_hours, "batch_size": args.batch_size,
                "gpu": torch.cuda.get_device_name(0),
                "versions": {"python": sys.version.split()[0], "torch": torch.__version__,
                             "transformers": __import__("transformers").__version__}}
    target = args.output_dir / "manifest.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        backbone = AutoModel.from_pretrained(MODEL_ID).to(device).eval()
        backbone.requires_grad_(False)
        manifest["resolved_model_commit"] = getattr(backbone.config, "_commit_hash", None)
        head = Yolo1DLinkerSegmenter(backbone.config.hidden_size, width=args.width,
                                     prototypes=args.prototypes).to(device)
        optimizer = torch.optim.AdamW(head.parameters(), lr=3e-4)
        train_windows, dev_windows = windows(train, 510), windows(dev, 510)
        manifest["status"] = "running"
        target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        best = -1.0
        for epoch in range(args.epochs):
            if time.monotonic() - start > args.max_hours * 3600:
                manifest["status"] = "time_limit"
                break
            head.train()
            order = list(range(len(train_windows)))
            random.Random(args.seed + epoch).shuffle(order)
            losses = []
            for offset in range(0, len(order), args.batch_size):
                if time.monotonic() - start > args.max_hours * 3600:
                    manifest["status"] = "time_limit"
                    break
                group = [train_windows[i] for i in order[offset:offset + args.batch_size]]
                embeddings, _, _ = embed_group(backbone, tokenizer, group, device)
                valid, residue, _, spans, _, _ = targets(group, device)
                outputs = head(embeddings, valid)
                loss = yolo1d_loss(outputs, valid, residue, spans)["total"]
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
                optimizer.step()
                losses.append(float(loss.item()))
            if manifest["status"] == "time_limit":
                break
            metrics = evaluate(backbone, tokenizer, head, dev_windows, args.batch_size, device)
            record = {"epoch": epoch + 1, "train_loss": sum(losses) / len(losses),
                      "development": metrics}
            with (args.output_dir / "epochs.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record) + "\n")
            if metrics["masked_residue_aps"] > best:
                best = metrics["masked_residue_aps"]
                atomic_checkpoint({"head": head.state_dict(), "epoch": epoch + 1,
                                   "model_id": MODEL_ID, "development": metrics,
                                   "width": args.width, "prototypes": args.prototypes},
                                  args.output_dir / "best.pt")
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
        manifest["elapsed_seconds"] = round(time.monotonic() - start, 3)
        manifest["peak_pytorch_vram_bytes"] = torch.cuda.max_memory_allocated()
        target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
