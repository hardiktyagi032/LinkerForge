"""Preregistered minimum-length decoder on frozen DLD fold-4 scores."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import torch
from sklearn.metrics import average_precision_score
from transformers import AutoModel, AutoTokenizer

from train_esm2_linker_detector import (
    ResidueHead, batch_embedding, file_hash, high_precision_operating_point,
    make_windows, read_records,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from linkerforge.detector.evaluation import region_metrics  # noqa: E402

VALIDATION_SHA = "290992af4a93c14ba007197c282367734af8ec878783d5e668ee4960128a3461"
CHECKPOINT_SHA = "1dac5c4097eb96acdc6de237bae28af7e1f067cfd72857898fc208a551331ec0"
MINIMUM_LENGTH = 4


def exact_operating_point(scores: np.ndarray, truth: np.ndarray,
                          lengths: list[int], minimum_length: int) -> dict:
    """Activate residues by descending exact score, maintaining surviving runs.

    Every threshold tie is processed as a group. The disjoint-set summary
    yields the same decoded mask as threshold-then-remove-short-runs.
    """
    count = len(scores)
    parent = np.arange(count, dtype=np.int32)
    size = np.zeros(count, dtype=np.int32)
    positive = np.zeros(count, dtype=np.int32)
    active = np.zeros(count, dtype=np.bool_)
    left_edge = np.zeros(count, dtype=np.bool_)
    right_edge = np.zeros(count, dtype=np.bool_)
    offset = 0
    for length in lengths:
        left_edge[offset] = True
        right_edge[offset + length - 1] = True
        offset += length
    if offset != count:
        raise ValueError("Protein lengths do not match flattened scores")

    def root(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = int(parent[index])
        return index

    tp = fp = 0
    best = None
    order = np.argsort(-scores, kind="stable")
    cursor = 0
    while cursor < count:
        threshold = scores[order[cursor]]
        end = cursor + 1
        while end < count and scores[order[end]] == threshold:
            end += 1
        for index in order[cursor:end]:
            index = int(index)
            neighbors = []
            if not left_edge[index] and active[index - 1]:
                neighbors.append(root(index - 1))
            if not right_edge[index] and active[index + 1]:
                neighbor = root(index + 1)
                if neighbor not in neighbors:
                    neighbors.append(neighbor)
            for neighbor in neighbors:
                if size[neighbor] >= minimum_length:
                    tp -= int(positive[neighbor])
                    fp -= int(size[neighbor] - positive[neighbor])
            active[index] = True
            parent[index] = index
            size[index] = 1
            positive[index] = int(truth[index])
            for neighbor in neighbors:
                parent[neighbor] = index
                size[index] += size[neighbor]
                positive[index] += positive[neighbor]
            if size[index] >= minimum_length:
                tp += int(positive[index])
                fp += int(size[index] - positive[index])
        if tp >= 50 and tp / (tp + fp) >= 0.90 and (best is None or tp > best["true_positives"]):
            best = {"target_precision": 0.90, "minimum_true_positives": 50,
                    "threshold": float(threshold), "precision": tp / (tp + fp),
                    "recall": tp / int(truth.sum()), "true_positives": tp,
                    "false_positives": fp}
        cursor = end
    return best or {"target_precision": 0.90, "minimum_true_positives": 50,
                    "threshold": None, "precision": None, "recall": 0.0,
                    "true_positives": 0, "false_positives": 0}


def decoded_mask(scores: np.ndarray, threshold: float, minimum_length: int) -> np.ndarray:
    selected = scores >= threshold
    result = np.zeros(len(scores), dtype=np.bool_)
    start = None
    for index, value in enumerate(np.r_[selected, False]):
        if value and start is None:
            start = index
        elif not value and start is not None:
            if index - start >= minimum_length:
                result[start:index] = True
            start = None
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=Path("artifacts/esm2-35m-linker-run-001/best.pt"))
    parser.add_argument("--expected-checkpoint-sha256", default=CHECKPOINT_SHA)
    parser.add_argument("--validation", type=Path, default=Path("data/processed/dld_reference/dld_validation.jsonl.gz"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/frozen-reference-min4-span-decoder-001"))
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError("Trial output directory is not empty")
    if file_hash(args.validation) != VALIDATION_SHA or file_hash(args.checkpoint) != args.expected_checkpoint_sha256:
        raise ValueError("Frozen input hash mismatch")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; refusing CPU model inference")
    start = time.monotonic()
    peak_start = torch.cuda.max_memory_allocated()
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    model_id, revision = checkpoint["model_id"], checkpoint["revision"]
    device = torch.device("cuda")
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
    backbone = AutoModel.from_pretrained(model_id, revision=revision).to(device).eval()
    head = ResidueHead(backbone.config.hidden_size).to(device).eval()
    head.load_state_dict(checkpoint["head"])
    records = read_records(args.validation)
    windows = make_windows(records, 510)
    score_by_id = {record["source_id"]: [] for record in records}
    with torch.no_grad():
        for offset in range(0, len(windows), 4):
            group = windows[offset:offset + 4]
            embeddings, _, mask = batch_embedding(backbone, tokenizer, group, device)
            scores = head(embeddings).sigmoid()
            for index, (_, _, source_id) in enumerate(group):
                score_by_id[source_id].extend(scores[index, mask[index]].cpu().tolist())
    lengths = [len(row["sequence"]) for row in records]
    truth = np.asarray([int(v > 0) for row in records for v in row["labels"]], dtype=np.uint8)
    scores = np.asarray([v for row in records for v in score_by_id[row["source_id"]]], dtype=np.float32)
    if len(truth) != len(scores):
        raise ValueError("Prediction/label length mismatch")
    baseline = high_precision_operating_point(truth, scores)
    if args.expected_checkpoint_sha256 == CHECKPOINT_SHA and (baseline["true_positives"] != 475 or baseline["false_positives"] != 52):
        raise ValueError("Matched reference operating point changed")
    decoded = exact_operating_point(scores, truth, lengths, MINIMUM_LENGTH)
    region = None
    no_linker_specificity = None
    if decoded["threshold"] is not None:
        predicted_by_id = {row["source_id"]: decoded_mask(np.asarray(score_by_id[row["source_id"]]),
                                                       decoded["threshold"], MINIMUM_LENGTH)
                           for row in records}
        predicted = np.concatenate([predicted_by_id[row["source_id"]] for row in records])
        observed_tp = int(np.count_nonzero(predicted & (truth == 1)))
        observed_fp = int(np.count_nonzero(predicted & (truth == 0)))
        if (observed_tp, observed_fp) != (decoded["true_positives"], decoded["false_positives"]):
            raise ValueError("Incremental decoder does not match full mask")
        negatives = [row for row in records if not any(int(v > 0) for v in row["labels"])]
        no_linker_specificity = sum(not predicted_by_id[row["source_id"]].any() for row in negatives) / len(negatives)
        region = region_metrics(
            {row["source_id"]: [bool(v) for v in row["labels"]] for row in records},
            {row["source_id"]: predicted_by_id[row["source_id"]].astype(float).tolist() for row in records},
            0.5,
        )
    elapsed = time.monotonic() - start
    args.output_dir.mkdir(parents=True, exist_ok=True)
    config = {"checkpoint": str(args.checkpoint), "checkpoint_sha256": args.expected_checkpoint_sha256,
              "validation": str(args.validation),
              "minimum_length": MINIMUM_LENGTH, "threshold_selection": "all exact unique scores with ties intact"}
    result = {"schema_version": "0.1.0", "status": "completed",
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "hypothesis": "Training-supported minimum-length decoding removes short false positives without losing more true positives",
              "expected_failure": "Thresholded true linkers fragment into short runs",
              "checkpoint_sha256": args.expected_checkpoint_sha256, "validation_sha256": VALIDATION_SHA,
              "source_sha256": file_hash(Path(__file__)),
              "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
              "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "model_id": model_id, "revision": revision, "config": config,
              "python": sys.version.split()[0], "torch": torch.__version__,
              "transformers": __import__("transformers").__version__,
              "gpu": torch.cuda.get_device_name(0), "elapsed_seconds": elapsed,
              "peak_pytorch_vram_bytes": max(0, torch.cuda.max_memory_allocated() - peak_start),
              "positive_residues": int(truth.sum()), "baseline": baseline, "decoder": decoded,
              "decoder_no_linker_specificity": no_linker_specificity,
              "decoder_region_iou_0_5": region,
              "residue_auprc_original_scores": float(average_precision_score(truth, scores)),
              "limitations": "Development fold only; postprocessing hypothesis motivated by fold-4 audit; no independent generalization claim"}
    (args.output_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"baseline": baseline, "decoder": decoded,
                      "no_linker_specificity": no_linker_specificity}))


if __name__ == "__main__":
    main()
