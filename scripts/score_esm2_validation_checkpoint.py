"""Score one frozen ESM-2 detector checkpoint on validation only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import torch
from sklearn.metrics import average_precision_score
from transformers import AutoModel, AutoTokenizer

from evaluate_esm2_linker_blind import scores_for, threshold_metrics
from train_esm2_linker_detector import ResidueHead, file_hash, high_precision_operating_point, read_records

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from linkerforge.detector.evaluation import region_metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("CUDA GPU unavailable")
    manifest_path = args.checkpoint.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if file_hash(args.validation) != manifest["validation_sha256"]:
        raise ValueError("Validation file differs from training manifest")
    device = torch.device("cuda")
    state = torch.load(args.checkpoint, map_location=device, weights_only=False)
    if (state["model_id"] != manifest["model_id"] or
            state["revision"] != manifest["revision"]):
        raise ValueError("Checkpoint and manifest disagree on backbone")
    tokenizer = AutoTokenizer.from_pretrained(state["model_id"], revision=state["revision"])
    backbone = AutoModel.from_pretrained(state["model_id"], revision=state["revision"]).to(device).eval()
    head = ResidueHead(backbone.config.hidden_size).to(device).eval()
    head.load_state_dict(state["head"])
    truth, scores, protein_truth, protein_max, protein_observed, protein_predicted = scores_for(
        backbone, tokenizer, head, read_records(args.validation), args.batch_size,
        device, return_per_protein=True)
    point = high_precision_operating_point(truth, scores, 0.90)
    if point["threshold"] is not None:
        point["no_linker_protein_specificity"] = threshold_metrics(
            truth, scores, protein_truth, protein_max,
            point["threshold"])["no_linker_protein_specificity"]
    regions = (region_metrics(protein_observed, protein_predicted, point["threshold"])
               if point["threshold"] is not None else None)
    print(json.dumps({"split": "validation_only", "checkpoint_sha256": file_hash(args.checkpoint),
                      "validation_sha256": manifest["validation_sha256"],
                      "selected_epoch": state["epoch"],
                      "residue_auprc": float(average_precision_score(truth, scores)),
                      "precision_90_operating_point": point,
                      "region_metrics_at_precision_90": regions}, indent=2))


if __name__ == "__main__":
    main()
