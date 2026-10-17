"""One-time TE64 retrospective test of frozen TE82-selected DFL heads."""

import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import torch
from sklearn.metrics import average_precision_score, roc_auc_score
from transformers import AutoModel, AutoTokenizer

from train_dfl_masked_cnn import MODEL_ID, ResidueHead, embed_group, load, windows
from train_dfl_masked_span import SpanHead


ROOT = Path(__file__).resolve().parents[1]
TE64 = ROOT / "data/processed/published_dfl_splits/te64.jsonl"
OUT = ROOT / "reports/dfl_te64_frozen_retrospective_2026-10-12.json"
CHECKPOINTS = {
    "LinkerForge_CNN": (ROOT / "artifacts/dfl-cnn-seed7-001/best.pt", ResidueHead),
    "LinkerForge_span": (ROOT / "artifacts/dfl-span-seed7-001/best.pt", SpanHead),
    "LinkerForge_precision": (ROOT / "artifacts/dfl-precision-seed7-001/best.pt", ResidueHead),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUT.exists():
        raise FileExistsError("One-time TE64 output already exists")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required")
    rows = load(TE64)
    if len(rows) != 64 or sum(r["labels"].count("1") for r in rows) != 949:
        raise ValueError("Unexpected TE64 content")
    examples = windows(rows, 510)
    device = torch.device("cuda")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    backbone = AutoModel.from_pretrained(MODEL_ID).to(device).eval()
    backbone.requires_grad_(False)
    results = {}
    for name, (path, head_type) in CHECKPOINTS.items():
        state = torch.load(path, map_location="cpu", weights_only=False)
        if state["model_id"] != MODEL_ID:
            raise ValueError("Model ID mismatch")
        head = head_type(backbone.config.hidden_size).to(device).eval()
        head.load_state_dict(state["head"])
        truth, scores = [], []
        with torch.no_grad():
            for offset in range(0, len(examples), 4):
                group = examples[offset:offset + 4]
                embeddings, labels, mask = embed_group(backbone, tokenizer, group, device)
                logits = head(embeddings)
                if head_type is SpanHead:
                    logits = logits[:, :, 0]
                truth.extend(labels[mask].cpu().numpy().astype(int).tolist())
                scores.extend(logits.sigmoid()[mask].cpu().numpy().tolist())
        truth, scores = np.asarray(truth), np.asarray(scores)
        results[name] = {"scored_residues": int(len(truth)), "positive_residues": int(truth.sum()),
                         "aps": float(average_precision_score(truth, scores)),
                         "auroc": float(roc_auc_score(truth, scores)),
                         "checkpoint_sha256": sha(path)}
    result = {"schema_version": "0.1.0", "status": "retrospective_test_frozen_checkpoints_no_selection",
              "test": "TransDFL_TE64", "results": results,
              "provenance": {"te64_sha256": sha(TE64), "script_sha256": sha(Path(__file__)),
                             "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()},
              "limitations": ["TE64 is a published historical test, not a fresh blind test.",
                              "The prior TE82-selected checkpoints are unchanged; do not tune or select on TE64.",
                              "This does not reproduce original TransDFL inference."]}
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
