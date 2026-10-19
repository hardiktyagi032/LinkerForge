"""Select development-set unknown spans for blinded annotation review.

Predictions nominate records for review; they never change source labels.
"""

import hashlib
import json
from pathlib import Path
import subprocess

import torch
from transformers import AutoModel, AutoTokenizer

from train_dfl_masked_cnn import MODEL_ID, ResidueHead, load


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/processed/published_dfl_splits/te82.jsonl"
CHECKPOINT = ROOT / "artifacts/dfl-cnn-seed7-001/best.pt"
OUTPUT = ROOT / "reports/dfl_te82_unknown_review_queue_2026-10-12.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runs(labels):
    start = None
    for i, label in enumerate(labels + "!", 1):
        if label == "x" and start is None:
            start = i
        elif label != "x" and start is not None:
            yield start, i - 1
            start = None


def main():
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required for frozen-model review queue")
    device = torch.device("cuda")
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    backbone = AutoModel.from_pretrained(MODEL_ID).to(device).eval()
    backbone.requires_grad_(False)
    state = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    if state["model_id"] != MODEL_ID:
        raise ValueError("Checkpoint backbone mismatch")
    head = ResidueHead(backbone.config.hidden_size).to(device).eval()
    head.load_state_dict(state["head"])
    candidates = []
    with torch.no_grad():
        for row in load(SOURCE):
            sequence, labels = row["sequence"], row["labels"]
            scores = []
            for start in range(0, len(sequence), 510):
                frag = sequence[start:start + 510]
                tokens = tok(frag, return_tensors="pt", add_special_tokens=True, truncation=False)
                hidden = backbone(**{k: v.to(device) for k, v in tokens.items()}).last_hidden_state[:, 1:1 + len(frag)]
                scores.extend(head(hidden).sigmoid()[0].cpu().tolist())
            if len(scores) != len(labels):
                raise ValueError("Score/label length mismatch")
            for begin, end in runs(labels):
                if end - begin + 1 < 10:
                    continue
                # Score a fixed 20-residue window to avoid selecting an entire
                # long unknown block on the basis of an unrelated local peak.
                for left in range(begin, end - 8, 10):
                    right = min(left + 19, end)
                    values = scores[left - 1:right]
                    candidates.append({"protein_id": row["protein_id"],
                                       "start_1based": left, "end_1based": right,
                                       "sequence": sequence[left - 1:right],
                                       "mean_model_score": sum(values) / len(values),
                                       "source_label": "x_masked_unknown",
                                       "evidence_quality": "unadjudicated_model_nominated"})
    candidates.sort(key=lambda item: (-item["mean_model_score"], item["protein_id"], item["start_1based"]))
    selected, used = [], set()
    for item in candidates:
        if item["protein_id"] not in used:
            selected.append(item)
            used.add(item["protein_id"])
        if len(selected) == 20:
            break
    report = {"schema_version": "0.1.0", "status": "annotation_review_queue_not_ground_truth",
              "selection": "top mean-score 10-20-residue unknown window; at most one per protein",
              "records": selected,
              "provenance": {"source_sha256": sha(SOURCE), "checkpoint_sha256": sha(CHECKPOINT),
                             "script_sha256": sha(Path(__file__)),
                             "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()},
              "warning": "Selection is model-informed; do not train/evaluate on these as negatives or claim a random annotation audit."}
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"candidates": len(candidates), "review_records": len(selected),
                      "top_mean_score": selected[0]["mean_model_score"] if selected else None}))


if __name__ == "__main__":
    main()
