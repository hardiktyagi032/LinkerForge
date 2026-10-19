"""Fail-closed first bounded-span DFL trial on CAID3-sequence-screened data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score

import run_caid3_protected_dfl_trial as protected
import run_dfl_disorder_transfer as trial
from train_dfl_masked_span import clean_spans
from train_esm2_linker_detector import high_precision_operating_point
from linkerforge.models.bounded_span_linker_segmenter import (
    BoundedSpanLinkerSegmenter, bounded_span_loss,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/dfl_bounded_span_protected_round_2026-10-16.json"
MODEL_SOURCE = ROOT / "src/linkerforge/models/bounded_span_linker_segmenter.py"


def configure_head(arch, dimension, device):
    if arch != "bounded_span":
        raise ValueError(arch)
    return BoundedSpanLinkerSegmenter(dimension).to(device)


def forward_loss(arch, head, embeddings, group, device, *, auxiliary=False):
    if arch != "bounded_span":
        raise ValueError(arch)
    valid, residue, _, spans, _, _ = trial.target_batch(group, device)
    output = head(embeddings, valid)
    known = valid & (residue >= 0)
    if auxiliary:
        return torch.nn.functional.binary_cross_entropy_with_logits(
            output["semantic_logits"][known], residue[known].float())
    return bounded_span_loss(output, valid, residue, spans)


@torch.no_grad()
def evaluate(arch, backbone, tokenizer, head, examples, batch_size, device):
    if arch != "bounded_span":
        raise ValueError(arch)
    head.eval()
    all_truth, all_scores = [], []
    by_protein = {}
    for offset in range(0, len(examples), batch_size):
        group = examples[offset:offset + batch_size]
        embeddings, _, _ = trial.embed_group(backbone, tokenizer, group, device)
        valid, _, _, _, _, _ = trial.target_batch(group, device)
        scores = head(embeddings, valid)["semantic_logits"].sigmoid()
        for index, (_, labels, protein_id) in enumerate(group):
            values = scores[index, :len(labels)].cpu().numpy().tolist()
            all_truth.extend(int(c == "1") for c in labels if c != "x")
            all_scores.extend(score for score, label in zip(values, labels) if label != "x")
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
        specificity = sum(max((score for score, c in zip(row["scores"], row["labels"])
                               if c != "x"), default=0) < threshold for row in negative) / len(negative)
    gold_count = recovered = 0
    for row in by_protein.values():
        gold = clean_spans(row["labels"], "1")
        predicted = clean_spans("".join("1" if score >= 0.5 else "0" for score in row["scores"]), "1")
        for a, b in gold:
            gold_count += 1
            if any(max(0, min(b, d) - max(a, c) + 1) / (max(b, d) - min(a, c) + 1) >= 0.5
                   for c, d in predicted):
                recovered += 1
    precision, recall, _ = precision_recall_curve(truth, prediction)
    f1 = np.divide(2 * precision * recall, precision + recall,
                   out=np.zeros_like(precision), where=(precision + recall) > 0)
    return {"masked_residue_aps": float(average_precision_score(truth, prediction)),
            "masked_residue_auroc": float(roc_auc_score(truth, prediction)),
            "masked_residue_fmax": float(f1.max()),
            "positive_residues": int(truth.sum()), "negative_residues": int(len(truth) - truth.sum()),
            "precision_90_operating_point": point,
            "no_positive_protein_proxy_specificity": specificity,
            "region_recall_iou_0.5_at_threshold_0.5": recovered / gold_count if gold_count else None,
            "region_recovered": recovered, "region_gold": gold_count}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-seconds", type=float, default=1800)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if not 0 < args.max_seconds <= 1800:
        raise ValueError("Trial exceeds per-job bound")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if config["data_manifest"] != str((protected.DATA / "manifest.json").relative_to(ROOT)).replace("\\", "/"):
        raise ValueError("Wrong data manifest")
    protected.preflight()
    if args.preflight_only:
        print(json.dumps({"status": "preflight_passed", "data_manifest_sha256": trial.sha(protected.DATA / "manifest.json")}))
        return
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    trial.CONFIG_PATH = CONFIG
    trial.TRAIN = protected.DATA / "train.jsonl"
    trial.DEV = protected.DATA / "development.jsonl"
    trial.AUX = protected.DATA / "auxiliary.jsonl"
    trial.AUX_MANIFEST = protected.ALIAS
    trial.DATA_MANIFEST = protected.DATA / "manifest.json"
    trial.preflight = protected.preflight
    trial.configure_head = configure_head
    trial.forward_loss = forward_loss
    trial.evaluate = evaluate
    args.arch = "bounded_span"
    args.condition = "direct"
    args.seed = 7
    try:
        trial.run_trial(args)
    finally:
        manifest_path = args.output_dir / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest.update({"launcher_sha256": trial.sha(Path(__file__)),
                             "model_source_sha256": trial.sha(MODEL_SOURCE),
                             "blacklist_manifest_sha256": trial.sha(protected.DATA / "manifest.json"),
                             "blacklist_status": "passed_before_training",
                             "claim_status": "CAID3_public_retrospective_not_fresh_blind"})
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
