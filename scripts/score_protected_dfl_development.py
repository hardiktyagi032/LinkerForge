"""Rescore completed, CAID3-screened DFL baselines on filtered development.

This reads no CAID3 labels and does not select a checkpoint. It adds Fmax at
exact score ties to the APS-selected checkpoint recorded by each trial.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import precision_recall_curve
from transformers import AutoModel, AutoTokenizer

import run_caid3_protected_dfl_trial as protected
import run_dfl_disorder_transfer as trial


def fmax_at_exact_ties(truth: np.ndarray, scores: np.ndarray) -> dict:
    if len(truth) != len(scores) or not len(truth) or not np.isfinite(scores).all():
        raise ValueError("Invalid truth/scores")
    if not (np.any(truth == 1) and np.any(truth == 0)):
        raise ValueError("Fmax requires positive and negative labelled residues")
    precision, recall, thresholds = precision_recall_curve(truth, scores)
    f1 = np.divide(2 * precision * recall, precision + recall,
                   out=np.zeros_like(precision), where=(precision + recall) > 0)
    best = int(np.argmax(f1))
    return {"fmax": float(f1[best]),
            "threshold": float(thresholds[best]) if best < len(thresholds) else None,
            "precision": float(precision[best]), "recall": float(recall[best]),
            "positive_residues": int(truth.sum()), "negative_residues": int(len(truth) - truth.sum())}


@torch.no_grad()
def score_one(backbone, tokenizer, device, run: Path, examples: list, expected: dict) -> dict:
    manifest_path = run / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["status"] != "completed" or manifest["blacklist_status"] != "passed_before_training":
        raise ValueError(f"Incomplete or unprotected trial: {run}")
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(f"{run}: {key} mismatch")
    checkpoint_path = run / "best.pt"
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    if checkpoint["arch"] != manifest["arch"] or checkpoint["epoch"] != manifest["best_epoch"]:
        raise ValueError(f"Checkpoint/manifest mismatch: {run}")
    head = trial.configure_head(manifest["arch"], backbone.config.hidden_size, device)
    head.load_state_dict(checkpoint["head"])
    head.eval()
    all_truth, all_scores = [], []
    for offset in range(0, len(examples), 4):
        group = examples[offset:offset + 4]
        embeddings, _, _ = trial.embed_group(backbone, tokenizer, group, device)
        valid, residue, _, _, _, concept = trial.target_batch(group, device)
        output = head(embeddings, valid, concept) if manifest["arch"] == "samlike" else head(embeddings, valid)
        values = (output["semantic_logits"] if manifest["arch"] == "samlike"
                  else output["semantic_logits"][:, :, 0]).sigmoid()
        for index, (_, labels, _) in enumerate(group):
            for label, score in zip(labels, values[index, :len(labels)].cpu().tolist()):
                if label != "x":
                    all_truth.append(int(label == "1"))
                    all_scores.append(score)
    result = fmax_at_exact_ties(np.asarray(all_truth, dtype=np.uint8),
                                np.asarray(all_scores, dtype=np.float32))
    if result["positive_residues"] != manifest["best_development"]["positive_residues"] or result["negative_residues"] != manifest["best_development"]["negative_residues"]:
        raise ValueError(f"Scored residue counts differ from original evaluation: {run}")
    result.update({"trial": run.name, "arch": manifest["arch"], "condition": manifest["condition"],
                   "seed": manifest["seed"], "checkpoint_sha256": hashlib.sha256(checkpoint_path.read_bytes()).hexdigest(),
                   "development_aps_from_trial": manifest["best_development"]["masked_residue_aps"],
                   "development_auroc_from_trial": manifest["best_development"]["masked_residue_auroc"]})
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, default=protected.ROOT / "artifacts/dfl-caid3-protected-baselines-2026-10-16")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verified = protected.preflight()
    ledger = json.loads((args.suite / "ledger.json").read_text(encoding="utf-8"))
    if ledger["status"] != "completed" or len(ledger["runs"]) != 12:
        raise ValueError("Expected completed 12-trial baseline suite")
    if args.output.exists():
        raise FileExistsError(args.output)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required for matched model rescoring")
    device = torch.device("cuda")
    tokenizer = AutoTokenizer.from_pretrained(trial.MODEL_ID)
    backbone = AutoModel.from_pretrained(trial.MODEL_ID).to(device).eval()
    backbone.requires_grad_(False)
    dev = trial.windows(verified[1], json.loads(protected.CONFIG.read_text(encoding="utf-8"))["max_residues_per_window"])
    expected = {"config_sha256": trial.sha(protected.CONFIG),
                "train_sha256": trial.sha(protected.DATA / "train.jsonl"),
                "dev_sha256": trial.sha(protected.DATA / "development.jsonl"),
                "aux_sha256": trial.sha(protected.DATA / "auxiliary.jsonl"),
                "data_manifest_sha256": trial.sha(protected.DATA / "manifest.json")}
    rows = [score_one(backbone, tokenizer, device, args.suite / row["name"], dev, expected)
            for row in ledger["runs"]]
    payload = {"schema_version": "1.0.0", "status": "filtered_development_only",
               "data_manifest_sha256": expected["data_manifest_sha256"],
               "config_sha256": expected["config_sha256"],
               "method": "maximum F1 over exact score ties on labelled development residues",
               "runs": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "completed", "runs": len(rows), "output": str(args.output)}))


if __name__ == "__main__":
    main()
