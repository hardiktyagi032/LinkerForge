"""Explore whether a frozen detector can reach a precision target on validation.

This script never opens a blind/test shard. Results cannot be called held-out.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import precision_recall_curve
from transformers import AutoModel, AutoTokenizer

from evaluate_esm2_linker_blind import scores_for, threshold_metrics
from train_esm2_linker_detector import ResidueHead, file_hash, read_records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--target-precision", type=float, default=0.90)
    parser.add_argument("--minimum-true-positives", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()
    if not 0 < args.target_precision <= 1 or args.minimum_true_positives < 1:
        raise ValueError("Invalid precision/support target")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU unavailable")
    state = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    tokenizer = AutoTokenizer.from_pretrained(state["model_id"], revision=state["revision"], local_files_only=True)
    backbone = AutoModel.from_pretrained(state["model_id"], revision=state["revision"], local_files_only=True).to("cuda").eval()
    backbone.requires_grad_(False)
    head = ResidueHead(backbone.config.hidden_size).to("cuda").eval()
    head.load_state_dict(state["head"])
    truth, scores, protein_truth, protein_max = scores_for(
        backbone, tokenizer, head, read_records(args.validation), args.batch_size, "cuda")
    precision, recall, thresholds = precision_recall_curve(truth, scores)
    candidates = np.flatnonzero((precision[:-1] >= args.target_precision) &
                                (recall[:-1] * int(truth.sum()) >= args.minimum_true_positives))
    chosen = None
    if len(candidates):
        index = int(candidates[np.argmax(recall[candidates])])
        chosen = threshold_metrics(truth, scores, protein_truth, protein_max, float(thresholds[index]))
    root = Path(__file__).resolve().parents[1]
    config = {"target_precision": args.target_precision,
              "minimum_true_positives": args.minimum_true_positives,
              "batch_size": args.batch_size}
    report = {
        "schema_version": "0.1.0", "status": "validation_only_exploratory",
        "target_precision": args.target_precision,
        "minimum_true_positives": args.minimum_true_positives,
        "candidate": chosen,
        "checkpoint_sha256": file_hash(args.checkpoint),
        "validation_sha256": file_hash(args.validation),
        "limitations": ["Validation-only threshold search; no held-out 90-percent precision claim.",
                        "A candidate threshold can fail on unseen proteins or new domain families.",
                        "Changing a threshold after a blind result is exploratory, not a confirmatory test."],
        "provenance": {
            "source_ids": ["DLD:validation"],
            "pipeline_commit": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
            "script_sha256": file_hash(Path(__file__).resolve()),
            "config_hash": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
            "software": {"torch": torch.__version__},
            "evidence_quality": "curated_validation_exploratory"
        }
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"candidate": chosen, "output": str(args.output)}))


if __name__ == "__main__":
    main()
