"""Check whether batched development scoring and single-protein deployment agree."""

import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import torch
from sklearn.metrics import average_precision_score
from transformers import AutoModel, AutoTokenizer

from compare_dfl_caid3_common import model_scores
from train_dfl_masked_cnn import DEV, MODEL_ID, ResidueHead, embed_group, load, windows


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "artifacts/dfl-cnn-seed7-001/best.pt"
OUTPUT = ROOT / "reports/dfl_inference_consistency_2026-10-12.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUTPUT.exists():
        raise FileExistsError("Diagnostic output exists")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required")
    rows = load(DEV)
    state = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    device = torch.device("cuda")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    backbone = AutoModel.from_pretrained(MODEL_ID).to(device).eval()
    backbone.requires_grad_(False)
    head = ResidueHead(backbone.config.hidden_size).to(device).eval()
    head.load_state_dict(state["head"])
    batch_scores = {r["protein_id"]: [] for r in rows}
    examples = windows(rows, 510)
    with torch.no_grad():
        for offset in range(0, len(examples), 4):
            group = examples[offset:offset + 4]
            embeddings, _, _ = embed_group(backbone, tokenizer, group, device)
            scores = head(embeddings).sigmoid().cpu().numpy()
            for i, (sequence, _, protein_id) in enumerate(group):
                batch_scores[protein_id].extend(scores[i, :len(sequence)].tolist())
    single_scores = {r["protein_id"]: model_scores(backbone, tokenizer, head, r["sequence"], device, False)
                     for r in rows}
    truth = np.asarray([int(x) for r in rows for x in r["labels"] if x != "x"], dtype=np.uint8)
    batched = np.asarray([s for r in rows for x, s in zip(r["labels"], batch_scores[r["protein_id"]]) if x != "x"])
    individual = np.asarray([s for r in rows for x, s in zip(r["labels"], single_scores[r["protein_id"]]) if x != "x"])
    differences = np.abs(batched - individual)
    report = {"schema_version": "0.1.0", "status": "diagnostic_only_no_model_selection",
              "scored_residues": int(len(truth)),
              "batched_aps": float(average_precision_score(truth, batched)),
              "single_protein_aps": float(average_precision_score(truth, individual)),
              "max_absolute_score_difference": float(differences.max()),
              "mean_absolute_score_difference": float(differences.mean()),
              "residues_difference_gt_0_01": int((differences > 0.01).sum()),
              "provenance": {"dev_sha256": sha(DEV), "checkpoint_sha256": sha(CHECKPOINT),
                             "script_sha256": sha(Path(__file__)),
                             "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()},
              "limitations": ["TE82 development diagnostic only; no thresholds or weights changed."]}
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in {"provenance", "limitations"}}))


if __name__ == "__main__":
    main()
