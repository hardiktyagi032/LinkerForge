"""Matched TE82 development-region audit of the frozen span-head checkpoint."""

import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

from score_dfl_baseline_regions import f1_threshold, region_metrics
from train_dfl_masked_cnn import DEV, MODEL_ID, embed_group, load, windows
from train_dfl_masked_span import SpanHead
from train_esm2_linker_detector import high_precision_operating_point


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "artifacts/dfl-span-seed7-001/best.pt"
OUTPUT = ROOT / "reports/dfl_span_te82_region_audit_2026-10-12.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    head = SpanHead(backbone.config.hidden_size).to(device).eval()
    head.load_state_dict(checkpoint["head"])
    scores_by_id = {row["protein_id"]: [] for row in rows}
    examples = windows(rows, 510)
    with torch.no_grad():
        for offset in range(0, len(examples), 4):
            group = examples[offset:offset + 4]
            embeddings, _, _ = embed_group(backbone, tokenizer, group, device)
            scores = head(embeddings)[:, :, 0].sigmoid().cpu().numpy()
            for i, (sequence, _, protein_id) in enumerate(group):
                scores_by_id[protein_id].extend(scores[i, :len(sequence)].tolist())
    truth = np.asarray([int(value) for row in rows for value in row["labels"] if value != "x"], dtype=np.uint8)
    score_vector = np.asarray([score for row in rows for value, score in zip(row["labels"], scores_by_id[row["protein_id"]])
                               if value != "x"], dtype=np.float32)
    selected = f1_threshold(truth, score_vector)
    metrics = region_metrics(rows, scores_by_id, selected["threshold"])
    high_precision = high_precision_operating_point(truth, score_vector)
    high_precision_regions = (region_metrics(rows, scores_by_id, high_precision["threshold"])
                              if high_precision["threshold"] is not None else None)
    high_precision_per_protein = []
    if high_precision["threshold"] is not None:
        for row in rows:
            labels = row["labels"]
            scores = scores_by_id[row["protein_id"]]
            tp = sum(label == "1" and score >= high_precision["threshold"]
                     for label, score in zip(labels, scores))
            fp = sum(label == "0" and score >= high_precision["threshold"]
                     for label, score in zip(labels, scores))
            if tp or fp:
                high_precision_per_protein.append({"protein_id": row["protein_id"],
                                                   "true_positives": tp, "false_positives": fp})
        high_precision_per_protein.sort(key=lambda x: (-x["true_positives"], x["protein_id"]))
    output = {"schema_version": "0.1.0", "record_type": "dfl_span_region_audit",
              "split": "TE82_development_only", "threshold_selection": "maximum_masked_residue_F1_on_TE82_exact_score_ties",
              "provenance": {"checkpoint_sha256": sha(CHECKPOINT), "dev_sha256": sha(DEV),
                             "script_sha256": sha(Path(__file__)),
                             "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()},
              "scored_residues": int(len(truth)), "positive_residues": int(truth.sum()),
              "selected_operating_point": selected, "intervals": metrics,
              "high_precision_operating_point": high_precision,
              "high_precision_intervals": high_precision_regions,
              "high_precision_per_protein": high_precision_per_protein,
              "high_precision_proteins_with_true_positives": sum(x["true_positives"] > 0 for x in high_precision_per_protein),
              "limitations": ["Development threshold, not independent test", "Masked positions break reported prediction intervals",
                              "No-positive specificity is measured only on scored 0/1 positions"]}
    OUTPUT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"selected_operating_point": selected, "intervals": metrics,
                      "high_precision_operating_point": high_precision,
                      "high_precision_intervals": high_precision_regions}, indent=2))


if __name__ == "__main__":
    main()
