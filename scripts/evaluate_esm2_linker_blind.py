"""One-time DLD fold-5 evaluation with thresholds frozen on fold 4."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score
from transformers import AutoModel, AutoTokenizer

from preflight_detector_data import scan
from train_esm2_linker_detector import (ResidueHead, batch_embedding, file_hash,
                                        make_windows, read_records)


@torch.no_grad()
def scores_for(backbone, tokenizer, head, records, batch_size, device,
               return_per_protein=False):
    windows = make_windows(records, 510)
    truth, scores = [], []
    protein_truth: dict[str, bool] = {}
    protein_max: dict[str, float] = {}
    protein_observed: dict[str, list[bool]] = {}
    protein_predicted: dict[str, list[float]] = {}
    for offset in range(0, len(windows), batch_size):
        group = windows[offset:offset + batch_size]
        hidden, targets, mask = batch_embedding(backbone, tokenizer, group, device)
        probabilities = head(hidden).sigmoid()
        for index, (_, _, source_id) in enumerate(group):
            observed = targets[index, mask[index]].cpu().numpy()
            predicted = probabilities[index, mask[index]].cpu().numpy()
            truth.extend(observed.tolist())
            scores.extend(predicted.tolist())
            protein_truth[source_id] = protein_truth.get(source_id, False) or bool(observed.any())
            protein_max[source_id] = max(protein_max.get(source_id, 0.0), float(predicted.max()))
            if return_per_protein:
                protein_observed.setdefault(source_id, []).extend(bool(value) for value in observed)
                protein_predicted.setdefault(source_id, []).extend(float(value) for value in predicted)
    if return_per_protein:
        return (np.asarray(truth, dtype=np.uint8), np.asarray(scores, dtype=np.float32),
                protein_truth, protein_max, protein_observed, protein_predicted)
    return np.asarray(truth, dtype=np.uint8), np.asarray(scores, dtype=np.float32), protein_truth, protein_max


def threshold_metrics(truth, scores, protein_truth, protein_max, threshold):
    predicted = scores >= threshold
    tp = int(np.count_nonzero(predicted & (truth == 1)))
    fp = int(np.count_nonzero(predicted & (truth == 0)))
    fn = int(np.count_nonzero(~predicted & (truth == 1)))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    negatives = [key for key, is_positive in protein_truth.items() if not is_positive]
    specificity = sum(protein_max[key] < threshold for key in negatives) / len(negatives)
    return {"threshold": float(threshold), "precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "true_positive_residues": tp, "false_positive_residues": fp,
            "no_linker_protein_specificity": specificity}


def select_thresholds(truth, scores, protein_truth, protein_max, target_precision):
    precision, recall, thresholds = precision_recall_curve(truth, scores)
    f1 = np.divide(2 * precision[:-1] * recall[:-1], precision[:-1] + recall[:-1],
                   out=np.zeros_like(thresholds), where=(precision[:-1] + recall[:-1]) > 0)
    best_index = int(np.argmax(f1))
    f1_threshold = float(thresholds[best_index])
    # Require at least 50 true positives to avoid a vacuous high-precision threshold.
    possible = np.flatnonzero((precision[:-1] >= target_precision) &
                               (recall[:-1] * int(truth.sum()) >= 50))
    high_precision = None
    if len(possible):
        index = possible[np.argmax(recall[possible])]
        high_precision = threshold_metrics(truth, scores, protein_truth,
                                           protein_max, float(thresholds[index]))
    return {"f1_selected": threshold_metrics(truth, scores, protein_truth,
                                               protein_max, f1_threshold),
            "target_precision": target_precision, "high_precision": high_precision,
            "high_precision_status": "available" if high_precision else "not_attained_on_validation"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    parser.add_argument("--blind", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--target-precision", type=float, default=0.70)
    parser.add_argument("--frozen-report", type=Path,
                        help="Prior full-fold report whose validation-selected thresholds must be reused")
    parser.add_argument("--overlap-screen", type=Path,
                        help="Sequence-only split screen; exclude every flagged blind source ID")
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("CUDA GPU unavailable")
    if not 0 < args.target_precision <= 1:
        raise ValueError("Target precision must be in (0, 1]")
    _, train_clusters, train_sequences = scan(str(args.train), "train")
    _, validation_clusters, validation_sequences = scan(str(args.validation), "validation")
    _, blind_clusters, blind_sequences = scan(str(args.blind), "blind")
    if (train_clusters & blind_clusters or validation_clusters & blind_clusters or
            train_sequences & blind_sequences or validation_sequences & blind_sequences):
        raise ValueError("Blind split overlaps training or validation")
    device = torch.device("cuda")
    state = torch.load(args.checkpoint, map_location=device, weights_only=False)
    model_id, revision = state["model_id"], state["revision"]
    exclusion = None
    excluded_ids: set[str] = set()
    if args.overlap_screen:
        if not args.frozen_report:
            raise ValueError("A sequence-overlap exclusion requires --frozen-report")
        audit = json.loads(args.overlap_screen.read_text(encoding="utf-8"))
        if audit["status"] != "candidate_screen_not_homology_certification":
            raise ValueError("Unexpected overlap-screen status")
        if sorted(audit["provenance"]["sha256"].values()) != sorted(
                [file_hash(args.train), file_hash(args.validation), file_hash(args.blind)]):
            raise ValueError("Overlap screen was computed for different input shards")
        excluded_ids = {hit["query_id"] for hit in audit["hits"]}
        exclusion = {"rule": "all_query_ids_flagged_by_sequence_only_overlap_screen",
                     "source_ids": sorted(excluded_ids),
                     "screen_sha256": file_hash(args.overlap_screen),
                     "screen_status": audit["status"]}
    if args.frozen_report:
        frozen = json.loads(args.frozen_report.read_text(encoding="utf-8"))
        if (frozen["checkpoint_sha256"] != file_hash(args.checkpoint) or
                frozen["validation_sha256"] != file_hash(args.validation) or
                frozen["blind_sha256"] != file_hash(args.blind) or
                frozen["model_id"] != model_id or frozen["revision"] != revision):
            raise ValueError("Frozen report does not match checkpoint and data")
        chosen = frozen["calibration"]
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
    backbone = AutoModel.from_pretrained(model_id, revision=revision).to(device).eval()
    backbone.requires_grad_(False)
    head = ResidueHead(backbone.config.hidden_size).to(device).eval()
    head.load_state_dict(state["head"])
    if not args.frozen_report:
        validation = scores_for(backbone, tokenizer, head, read_records(args.validation),
                                args.batch_size, device)
        chosen = select_thresholds(*validation, args.target_precision)
    blind_records = read_records(args.blind)
    if excluded_ids - {row["source_id"] for row in blind_records}:
        raise ValueError("Overlap screen names blind IDs absent from this shard")
    blind_records = [row for row in blind_records if row["source_id"] not in excluded_ids]
    blind = scores_for(backbone, tokenizer, head, blind_records,
                       args.batch_size, device)
    blind_truth, blind_scores, blind_protein_truth, blind_protein_max = blind
    blind_metrics = {"residue_auprc": float(average_precision_score(blind_truth, blind_scores)),
                     "residue_auroc": float(roc_auc_score(blind_truth, blind_scores)),
                     "positive_residues": int(blind_truth.sum()),
                     "residues": int(len(blind_truth)), "proteins": len(blind_protein_truth),
                     "f1_selected": threshold_metrics(*blind, chosen["f1_selected"]["threshold"])}
    if chosen["high_precision"]:
        blind_metrics["high_precision"] = threshold_metrics(
            *blind, chosen["high_precision"]["threshold"])
    root = Path(__file__).resolve().parents[1]
    config = {"batch_size": args.batch_size, "frozen_report_sha256": file_hash(args.frozen_report) if args.frozen_report else None,
              "overlap_screen_sha256": file_hash(args.overlap_screen) if args.overlap_screen else None}
    report = {"schema_version": "0.1.0", "status": "evaluated_screened_blind" if exclusion else "evaluated_frozen_blind",
              "model_id": model_id, "revision": revision,
              "checkpoint_sha256": file_hash(args.checkpoint),
              "validation_sha256": file_hash(args.validation), "blind_sha256": file_hash(args.blind),
              "calibration": chosen, "blind_metrics": blind_metrics,
              "exclusion": exclusion,
              "provenance": {"source_ids": ["DLD:train", "DLD:validation", "DLD:blind"],
                             "pipeline_commit": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
                             "script_sha256": file_hash(Path(__file__).resolve()),
                             "config_hash": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
                             "evidence_quality": "curated_reference_sequence_screened" if exclusion else "curated_reference"},
              "limitations": ["DLD source fold 5 is not CAID3 and metrics are not directly comparable.",
                              "The top-k sequence-only overlap screen is not a complete homology audit.",
                              "Published LINKER-Pred models trained on DLD/DisProt; this is not an independent head-to-head set.",
                              "Natural linker detection does not establish fusion-linker design quality."]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
