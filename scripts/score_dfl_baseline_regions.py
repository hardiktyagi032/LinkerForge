"""Frozen TE82 development interval audit for the masked DFL CNN baseline."""

import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

from train_dfl_masked_cnn import DEV, MODEL_ID, ResidueHead, embed_group, load, windows


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "artifacts/dfl-cnn-seed7-001/best.pt"
OUTPUT = ROOT / "reports/dfl_cnn_te82_region_audit_2026-10-12.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def intervals(values: list[bool]) -> list[tuple[int, int]]:
    result = []
    start = None
    for i, active in enumerate(values):
        if active and start is None:
            start = i
        if start is not None and (not active or i == len(values) - 1):
            end = i if active else i - 1
            result.append((start, end))
            start = None
    return result


def f1_threshold(truth: np.ndarray, scores: np.ndarray) -> dict:
    order = np.argsort(-scores, kind="stable")
    ranked, labels = scores[order], truth[order]
    tp = np.cumsum(labels)
    predicted = np.arange(1, len(scores) + 1)
    precision = tp / predicted
    recall = tp / truth.sum()
    f1 = np.divide(2 * precision * recall, precision + recall,
                   out=np.zeros_like(precision), where=precision + recall > 0)
    ties_end = np.r_[ranked[1:] != ranked[:-1], True]
    eligible = np.flatnonzero(ties_end)
    best = int(eligible[np.argmax(f1[eligible])])
    return {"threshold": float(ranked[best]), "f1": float(f1[best]),
            "precision": float(precision[best]), "recall": float(recall[best]),
            "true_positives": int(tp[best]), "false_positives": int(predicted[best] - tp[best])}


def region_metrics(rows: list[dict], scores_by_id: dict[str, list[float]], threshold: float) -> dict:
    true_regions, predicted_regions, matches = 0, 0, []
    no_positive = 0
    no_positive_clear = 0
    for row in rows:
        labels = row["labels"]
        scores = scores_by_id[row["protein_id"]]
        if len(scores) != len(labels):
            raise ValueError(f"Score/label length mismatch for {row['protein_id']}")
        true = intervals([value == "1" for value in labels])
        predicted = intervals([value != "x" and score >= threshold for value, score in zip(labels, scores)])
        true_regions += len(true)
        predicted_regions += len(predicted)
        if not true:
            no_positive += 1
            no_positive_clear += not bool(predicted)
        candidates = []
        for ti, (ts, te) in enumerate(true):
            for pi, (ps, pe) in enumerate(predicted):
                overlap = max(0, min(te, pe) - max(ts, ps) + 1)
                union = (te - ts + 1) + (pe - ps + 1) - overlap
                iou = overlap / union
                if iou >= 0.5:
                    candidates.append((iou, ti, pi))
        used_true, used_pred = set(), set()
        for iou, ti, pi in sorted(candidates, reverse=True):
            if ti in used_true or pi in used_pred:
                continue
            used_true.add(ti)
            used_pred.add(pi)
            ts, te = true[ti]
            ps, pe = predicted[pi]
            matches.append({"protein_id": row["protein_id"], "iou": iou,
                            "start_error": abs(ps - ts), "end_error": abs(pe - te)})
    return {"true_regions": true_regions, "predicted_regions": predicted_regions,
            "matched_regions_iou_0_5": len(matches),
            "region_precision_iou_0_5": len(matches) / predicted_regions if predicted_regions else None,
            "region_recall_iou_0_5": len(matches) / true_regions if true_regions else None,
            "median_start_error_matched_residues": float(np.median([x["start_error"] for x in matches])) if matches else None,
            "median_end_error_matched_residues": float(np.median([x["end_error"] for x in matches])) if matches else None,
            "no_positive_proteins": no_positive,
            "no_positive_proteins_without_scored_residue_prediction": no_positive_clear,
            "no_positive_scored_residue_specificity": no_positive_clear / no_positive if no_positive else None}


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("GPU inference required for this audit")
    rows = load(DEV)
    checkpoint = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    if checkpoint["model_id"] != MODEL_ID:
        raise ValueError("Wrong checkpoint model")
    device = torch.device("cuda")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    backbone = AutoModel.from_pretrained(MODEL_ID).to(device).eval()
    backbone.requires_grad_(False)
    head = ResidueHead(backbone.config.hidden_size).to(device).eval()
    head.load_state_dict(checkpoint["head"])
    scores_by_id = {row["protein_id"]: [] for row in rows}
    examples = windows(rows, 510)
    with torch.no_grad():
        for offset in range(0, len(examples), 4):
            group = examples[offset:offset + 4]
            embeddings, _, _ = embed_group(backbone, tokenizer, group, device)
            scores = head(embeddings).sigmoid().cpu().numpy()
            for i, (sequence, _, protein_id) in enumerate(group):
                scores_by_id[protein_id].extend(scores[i, :len(sequence)].tolist())
    truth = np.asarray([int(value) for row in rows for value in row["labels"] if value != "x"], dtype=np.uint8)
    score_vector = np.asarray([score for row in rows for value, score in zip(row["labels"], scores_by_id[row["protein_id"]])
                               if value != "x"], dtype=np.float32)
    selected = f1_threshold(truth, score_vector)
    metrics = region_metrics(rows, scores_by_id, selected["threshold"])
    output = {"schema_version": "0.1.0", "record_type": "dfl_baseline_region_audit",
              "split": "TE82_development_only", "threshold_selection": "maximum_masked_residue_F1_on_TE82_exact_score_ties",
              "provenance": {"checkpoint_sha256": sha(CHECKPOINT), "dev_sha256": sha(DEV),
                             "script_sha256": sha(Path(__file__)),
                             "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()},
              "scored_residues": int(len(truth)), "positive_residues": int(truth.sum()),
              "selected_operating_point": selected, "intervals": metrics,
              "limitations": ["Development threshold, not independent test", "Masked positions break reported prediction intervals", "No-positive specificity is measured only on scored 0/1 positions"]}
    OUTPUT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"selected_operating_point": selected, "intervals": metrics}, indent=2))


if __name__ == "__main__":
    main()
