"""Bounded frozen-ESM2 residue-CNN baseline on published masked DFL labels.

TR166 trains; TE82 is development. TE64 and CAID3 are not opened here.
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

from train_esm2_linker_detector import ResidueHead, atomic_checkpoint, high_precision_operating_point


ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "data/processed/published_dfl_splits/tr166.jsonl"
DEV = ROOT / "data/processed/published_dfl_splits/te82.jsonl"
CONFIG = ROOT / "configs/dfl_autoresearch_round_2026-10-12.json"
DATA_MANIFEST = ROOT / "data/processed/published_dfl_splits/manifest.json"
MODEL_ID = "facebook/esm2_t12_35M_UR50D"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def preflight() -> tuple[list[dict], list[dict]]:
    train, dev = load(TRAIN), load(DEV)
    if sha(TRAIN) != "8fbfa1a503857131b8e485f511f5c84d9fbea24b9d5bbac2aa003508cb4f716c":
        raise ValueError("Training split hash changed")
    if sha(DEV) != "f15ac3eef1edc45b95bc600d661dab348a0cb0bee11e47febeac356ef93db916":
        raise ValueError("Development split hash changed")
    if {row["protein_id"] for row in train} & {row["protein_id"] for row in dev}:
        raise ValueError("Exact protein ID overlap")
    for row in train + dev:
        if len(row["sequence"]) != len(row["labels"]) or set(row["labels"]) - set("01x"):
            raise ValueError(f"Malformed labels: {row['protein_id']}")
        if row["split"] not in {"train_original", "development_original"}:
            raise ValueError("Unexpected split")
    return train, dev


def windows(rows: list[dict], width: int) -> list[tuple[str, str, str]]:
    return [(row["sequence"][start:start + width], row["labels"][start:start + width], row["protein_id"])
            for row in rows for start in range(0, len(row["sequence"]), width)]


def embed_group(backbone, tokenizer, group, device):
    seqs = [row[0] for row in group]
    tokens = tokenizer(seqs, return_tensors="pt", padding=True, add_special_tokens=True, truncation=False)
    tokens = {key: value.to(device) for key, value in tokens.items()}
    with torch.no_grad():
        embeddings = backbone(**tokens).last_hidden_state[:, 1:1 + max(map(len, seqs))]
    labels = torch.zeros(embeddings.shape[:2], device=device)
    mask = torch.zeros_like(labels, dtype=torch.bool)
    for i, (_, encoded, _) in enumerate(group):
        labels[i, :len(encoded)] = torch.tensor([x == "1" for x in encoded], dtype=torch.float32, device=device)
        mask[i, :len(encoded)] = torch.tensor([x != "x" for x in encoded], dtype=torch.bool, device=device)
    return embeddings, labels, mask


@torch.no_grad()
def evaluate(backbone, tokenizer, head, examples, batch_size, device):
    head.eval()
    truth, scores = [], []
    protein_positive, protein_max = {}, {}
    for offset in range(0, len(examples), batch_size):
        group = examples[offset:offset + batch_size]
        embeddings, labels, mask = embed_group(backbone, tokenizer, group, device)
        predictions = head(embeddings).sigmoid()
        for i, (_, _, protein_id) in enumerate(group):
            observed = labels[i][mask[i]].cpu().numpy()
            predicted = predictions[i][mask[i]].cpu().numpy()
            truth.extend(observed.tolist())
            scores.extend(predicted.tolist())
            protein_positive[protein_id] = protein_positive.get(protein_id, False) or bool(observed.any())
            if len(predicted):
                protein_max[protein_id] = max(protein_max.get(protein_id, 0.0), float(predicted.max()))
    truth = np.asarray(truth, dtype=np.uint8)
    scores = np.asarray(scores, dtype=np.float32)
    primary = float(average_precision_score(truth, scores))
    point = high_precision_operating_point(truth, scores)
    threshold = point["threshold"]
    negative_ids = [key for key, positive in protein_positive.items() if not positive]
    specificity = (sum(protein_max.get(key, 0.0) < threshold for key in negative_ids) / len(negative_ids)
                   if threshold is not None and negative_ids else None)
    return {"masked_residue_aps": primary, "masked_residue_auroc": float(roc_auc_score(truth, scores)),
            "scored_residues": int(len(truth)), "positive_residues": int(truth.sum()),
            "negative_residues": int(len(truth) - truth.sum()), "no_positive_proteins": len(negative_ids),
            "precision_90_operating_point": point, "no_positive_protein_specificity_at_precision_90": specificity}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--max-hours", type=float, default=2)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    train, dev = preflight()
    if args.preflight_only:
        print(json.dumps({"status": "preflight_pass", "train_proteins": len(train), "dev_proteins": len(dev),
                          "train_sha256": sha(TRAIN), "dev_sha256": sha(DEV)}))
        return
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; CPU training refused")
    if args.epochs < 1 or not 0 < args.max_hours <= 2:
        raise ValueError("Trial bounds invalid")
    if args.output_dir.exists():
        raise FileExistsError("Trial output exists; refusing duplicate or overwrite")
    args.output_dir.mkdir(parents=True)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    random.seed(args.seed)
    device = torch.device("cuda")
    start = time.monotonic()
    manifest = {"schema_version": "0.1.0", "status": "initializing", "seed": args.seed,
                "model_id": MODEL_ID, "train_sha256": sha(TRAIN), "dev_sha256": sha(DEV),
                "config_sha256": sha(CONFIG), "data_manifest_sha256": sha(DATA_MANIFEST),
                "source_sha256": sha(Path(__file__)),
                "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "created_utc": datetime.now(timezone.utc).isoformat(), "max_hours": args.max_hours,
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
        head = ResidueHead(backbone.config.hidden_size).to(device)
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
            for offset in range(0, len(order), 4):
                group = [train_windows[i] for i in order[offset:offset + 4]]
                embeddings, labels, mask = embed_group(backbone, tokenizer, group, device)
                logits = head(embeddings)
                loss = torch.nn.functional.binary_cross_entropy_with_logits(logits[mask], labels[mask])
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
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
