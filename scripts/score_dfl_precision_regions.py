"""TE82-only interval audit for precision-constrained CNN trial."""

import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

from score_dfl_baseline_regions import f1_threshold, region_metrics
from train_dfl_masked_cnn import DEV, MODEL_ID, ResidueHead, embed_group, load, windows
from train_esm2_linker_detector import high_precision_operating_point


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "artifacts/dfl-precision-seed7-001/best.pt"
OUTPUT = ROOT / "reports/dfl_precision_te82_region_audit_2026-10-12.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required for matched audit")
    rows = load(DEV)
    checkpoint = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    if checkpoint["model_id"] != MODEL_ID:
        raise ValueError("Checkpoint model mismatch")
    device = torch.device("cuda")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    backbone = AutoModel.from_pretrained(MODEL_ID).to(device).eval()
    backbone.requires_grad_(False)
    head = ResidueHead(backbone.config.hidden_size).to(device).eval()
    head.load_state_dict(checkpoint["head"])
    scores_by_id = {r["protein_id"]: [] for r in rows}
    examples = windows(rows, 510)
    with torch.no_grad():
        for offset in range(0, len(examples), 4):
            group = examples[offset:offset + 4]
            embeddings, _, _ = embed_group(backbone, tokenizer, group, device)
            probabilities = head(embeddings).sigmoid().cpu().numpy()
            for i, (sequence, _, protein_id) in enumerate(group):
                scores_by_id[protein_id].extend(probabilities[i, :len(sequence)].tolist())
    truth = np.asarray([int(x) for r in rows for x in r["labels"] if x != "x"], dtype=np.uint8)
    scores = np.asarray([s for r in rows for x, s in zip(r["labels"], scores_by_id[r["protein_id"]])
                         if x != "x"], dtype=np.float32)
    f1 = f1_threshold(truth, scores)
    hp = high_precision_operating_point(truth, scores)
    result = {"schema_version": "0.1.0", "record_type": "dfl_precision_trial_region_audit",
              "split": "TE82_development_only", "threshold_selection": "TE82_exact_score_ties",
              "f1_operating_point": f1, "f1_regions": region_metrics(rows, scores_by_id, f1["threshold"]),
              "high_precision_operating_point": hp,
              "high_precision_regions": region_metrics(rows, scores_by_id, hp["threshold"]) if hp["threshold"] is not None else None,
              "provenance": {"checkpoint_sha256": sha(CHECKPOINT), "dev_sha256": sha(DEV),
                             "script_sha256": sha(Path(__file__)),
                             "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()},
              "limitations": ["Development threshold, not independent test", "Masked positions break reported intervals",
                              "No-positive specificity only on scored residues"]}
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"f1_regions": result["f1_regions"], "high_precision_regions": result["high_precision_regions"]}))


if __name__ == "__main__":
    main()
