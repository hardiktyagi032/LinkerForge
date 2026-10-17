"""Validation-only equal-weight ensemble of two compatible ESM-2 residue heads.

This is an exploratory ablation. It never opens the DLD blind shard and does
not alter either checkpoint or choose ensemble weights on validation data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import average_precision_score
from transformers import AutoModel, AutoTokenizer

from evaluate_esm2_linker_blind import threshold_metrics
from train_esm2_linker_detector import (ResidueHead, batch_embedding, file_hash,
                                        high_precision_operating_point,
                                        make_windows, read_records)


def summarize(truth: np.ndarray, scores: np.ndarray,
              protein_truth: dict[str, bool], protein_max: dict[str, float]) -> dict:
    point = high_precision_operating_point(truth, scores, 0.90)
    if point["threshold"] is not None:
        point["no_linker_protein_specificity"] = threshold_metrics(
            truth, scores, protein_truth, protein_max,
            point["threshold"])["no_linker_protein_specificity"]
    return {"residue_auprc": float(average_precision_score(truth, scores)),
            "precision_90_operating_point": point}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-a", required=True, type=Path)
    parser.add_argument("--checkpoint-b", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("CUDA GPU unavailable")
    manifests = [json.loads((path.parent / "manifest.json").read_text(encoding="utf-8"))
                 for path in (args.checkpoint_a, args.checkpoint_b)]
    for key in ("model_id", "revision", "train_sha256", "validation_sha256"):
        if manifests[0][key] != manifests[1][key]:
            raise ValueError(f"Incompatible checkpoints: {key}")
    if file_hash(args.validation) != manifests[0]["validation_sha256"]:
        raise ValueError("Validation file differs from checkpoint manifests")
    device = torch.device("cuda")
    states = [torch.load(path, map_location=device, weights_only=False)
              for path in (args.checkpoint_a, args.checkpoint_b)]
    for state in states:
        if (state["model_id"] != manifests[0]["model_id"] or
                state["revision"] != manifests[0]["revision"]):
            raise ValueError("Checkpoint and manifest disagree on backbone")
    tokenizer = AutoTokenizer.from_pretrained(manifests[0]["model_id"],
                                               revision=manifests[0]["revision"])
    backbone = AutoModel.from_pretrained(manifests[0]["model_id"],
                                         revision=manifests[0]["revision"]).to(device).eval()
    heads = []
    for state in states:
        head = ResidueHead(backbone.config.hidden_size).to(device).eval()
        head.load_state_dict(state["head"])
        heads.append(head)
    windows = make_windows(read_records(args.validation), 510)
    truth: list[int] = []
    predictions: list[list[float]] = [[], [], []]
    protein_truth: dict[str, bool] = {}
    protein_max: list[dict[str, float]] = [{}, {}, {}]
    with torch.no_grad():
        for offset in range(0, len(windows), args.batch_size):
            group = windows[offset:offset + args.batch_size]
            embeddings, targets, mask = batch_embedding(backbone, tokenizer, group, device)
            first, second = [head(embeddings).sigmoid() for head in heads]
            combined = (first + second) / 2
            for index, (_, _, source_id) in enumerate(group):
                valid = mask[index]
                observed = targets[index, valid].cpu().numpy()
                truth.extend(observed.astype(np.uint8).tolist())
                protein_truth[source_id] = (protein_truth.get(source_id, False) or
                                            bool(observed.any()))
                for slot, probabilities in enumerate((first, second, combined)):
                    values = probabilities[index, valid].cpu().numpy()
                    predictions[slot].extend(values.tolist())
                    protein_max[slot][source_id] = max(
                        protein_max[slot].get(source_id, 0.0), float(values.max()))
    truth_array = np.asarray(truth, dtype=np.uint8)
    result = {
        "split": "validation_only", "ensemble_rule": "equal_arithmetic_mean_probabilities",
        "model_id": manifests[0]["model_id"], "revision": manifests[0]["revision"],
        "validation_sha256": manifests[0]["validation_sha256"],
        "checkpoints": [
            {"path": str(path), "sha256": file_hash(path), "selected_epoch": state["epoch"]}
            for path, state in zip((args.checkpoint_a, args.checkpoint_b), states)],
        "scores": {name: summarize(truth_array, np.asarray(values, dtype=np.float32),
                                   protein_truth, maxima)
                   for name, values, maxima in zip(("a", "b", "equal_mean"),
                                                   predictions, protein_max)},
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
