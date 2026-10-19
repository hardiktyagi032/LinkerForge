"""Read-only fold-4 error audit of the frozen ESM-2 weighted-BCE detector."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

from train_esm2_linker_detector import (
    ResidueHead, batch_embedding, file_hash, high_precision_operating_point,
    make_windows, read_records,
)

VALIDATION_SHA = "290992af4a93c14ba007197c282367734af8ec878783d5e668ee4960128a3461"


def spans(flags):
    start = None
    for index, active in enumerate([*flags, False]):
        if active and start is None:
            start = index
        elif not active and start is not None:
            yield start, index
            start = None


def bins(lengths):
    labels = ["1-2", "3-4", "5-9", "10-19", "20-39", "40+"]
    counts = Counter()
    for length in lengths:
        counts[next((label for label, limit in zip(labels, [2, 4, 9, 19, 39, float("inf")])
                     if length <= limit))] += 1
    return {label: counts[label] for label in labels}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path,
                        default=Path("artifacts/esm2-35m-linker-run-001/best.pt"))
    parser.add_argument("--validation", type=Path,
                        default=Path("data/processed/dld_reference/dld_validation.jsonl.gz"))
    parser.add_argument("--output", type=Path,
                        default=Path("reports/dld_false_positive_audit_2026-10-11.json"))
    args = parser.parse_args()
    if file_hash(args.validation) != VALIDATION_SHA:
        raise ValueError("Frozen validation hash mismatch")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this reference inference audit")
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    device = torch.device("cuda")
    model_id, revision = checkpoint["model_id"], checkpoint["revision"]
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
    backbone = AutoModel.from_pretrained(model_id, revision=revision).to(device).eval()
    head = ResidueHead(backbone.config.hidden_size).to(device).eval()
    head.load_state_dict(checkpoint["head"])
    records = read_records(args.validation)
    windows = make_windows(records, 510)
    scores_by_id = {record["source_id"]: [] for record in records}
    with torch.no_grad():
        for offset in range(0, len(windows), 4):
            group = windows[offset:offset + 4]
            embeddings, _, mask = batch_embedding(backbone, tokenizer, group, device)
            probabilities = head(embeddings).sigmoid()
            for index, (_, _, source_id) in enumerate(group):
                scores_by_id[source_id].extend(probabilities[index, mask[index]].cpu().tolist())
    truth = np.asarray([int(v > 0) for row in records for v in row["labels"]], dtype=np.uint8)
    scores = np.asarray([v for row in records for v in scores_by_id[row["source_id"]]], dtype=np.float32)
    if len(truth) != len(scores):
        raise ValueError("Score/label coordinate mismatch")
    point = high_precision_operating_point(truth, scores)
    if point["threshold"] is None:
        raise ValueError("Reference checkpoint has no frozen high-precision operating point")
    threshold = point["threshold"]
    predicted_lengths, false_only_lengths, candidates = [], [], []
    no_linker_total = no_linker_with_prediction = 0
    for row in records:
        observed = np.asarray(row["labels"], dtype=np.uint8) > 0
        score = np.asarray(scores_by_id[row["source_id"]], dtype=np.float32)
        predicted = score >= threshold
        if not observed.any():
            no_linker_total += 1
            no_linker_with_prediction += bool(predicted.any())
        for start, end in spans(predicted.tolist()):
            predicted_lengths.append(end - start)
            if not observed[start:end].any():
                false_only_lengths.append(end - start)
                candidates.append({"source_id": row["source_id"], "start_1_based": start + 1,
                                   "end_1_based_inclusive": end, "length": end - start,
                                   "maximum_score": float(score[start:end].max())})
    candidates.sort(key=lambda row: -row["maximum_score"])
    output = {
        "schema_version": "0.1.0", "created_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "development_error_audit_not_independent_test",
        "checkpoint": str(args.checkpoint), "checkpoint_sha256": file_hash(args.checkpoint),
        "validation_sha256": VALIDATION_SHA, "source_sha256": file_hash(Path(__file__)),
        "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "model_id": model_id, "revision": revision, "point": point,
        "predicted_span_count": len(predicted_lengths),
        "predicted_span_length_bins": bins(predicted_lengths),
        "false_only_span_count": len(false_only_lengths),
        "false_only_span_length_bins": bins(false_only_lengths),
        "no_linker_proteins": no_linker_total,
        "no_linker_proteins_with_any_prediction": no_linker_with_prediction,
        "highest_scoring_false_only_spans": candidates[:30],
        "limitation": "A label-negative interval may contain an unannotated true linker; this audit does not adjudicate biology.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: output[key] for key in ["point", "predicted_span_count",
                                                "false_only_span_count", "no_linker_proteins_with_any_prediction"]}))


if __name__ == "__main__":
    main()
