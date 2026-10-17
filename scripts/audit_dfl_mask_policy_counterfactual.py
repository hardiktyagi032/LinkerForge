"""Re-score frozen DFL heads if source x residues were counted as negatives.

This is a label-policy sensitivity experiment, not a biological relabeling.
"""

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
SPLITS = {"TE82": ROOT / "data/processed/published_dfl_splits/te82.jsonl",
          "TE64": ROOT / "data/processed/published_dfl_splits/te64.jsonl"}
HEADS = {"CNN": (ROOT / "artifacts/dfl-cnn-seed7-001/best.pt", ResidueHead),
         "span": (ROOT / "artifacts/dfl-span-seed7-001/best.pt", SpanHead),
         "precision": (ROOT / "artifacts/dfl-precision-seed7-001/best.pt", ResidueHead)}
OUT = ROOT / "reports/dfl_mask_policy_counterfactual_v2_2026-10-12.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(labels, scores, scored_only):
    selected = [(label, score) for label, score in zip(labels, scores) if not scored_only or label != "x"]
    truth = np.asarray([label == "1" for label, _ in selected], dtype=np.uint8)
    values = np.asarray([score for _, score in selected], dtype=np.float32)
    return {"residues": len(values), "positives": int(truth.sum()),
            "aps": float(average_precision_score(truth, values)),
            "auroc": float(roc_auc_score(truth, values)),
            "positive_prevalence": float(truth.mean())}


def main():
    if OUT.exists():
        raise FileExistsError("Diagnostic already exists")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required")
    device = torch.device("cuda")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    backbone = AutoModel.from_pretrained(MODEL_ID).to(device).eval()
    backbone.requires_grad_(False)
    results = {}
    with torch.no_grad():
        for name, split in SPLITS.items():
            rows = load(split)
            examples = windows(rows, 510)
            positive_ids = {row["protein_id"] for row in rows if "1" in row["labels"]}
            results[name] = {}
            for model, (checkpoint, head_type) in HEADS.items():
                state = torch.load(checkpoint, map_location="cpu", weights_only=False)
                head = head_type(backbone.config.hidden_size).to(device).eval()
                head.load_state_dict(state["head"])
                labels, scores = [], []
                positive_only_labels, positive_only_scores = [], []
                for offset in range(0, len(examples), 4):
                    group = examples[offset:offset + 4]
                    embeddings, _, _ = embed_group(backbone, tokenizer, group, device)
                    logits = head(embeddings)
                    if head_type is SpanHead:
                        logits = logits[:, :, 0]
                    probabilities = logits.sigmoid().cpu().numpy()
                    for i, (sequence, encoded, protein_id) in enumerate(group):
                        labels.extend(encoded)
                        scores.extend(probabilities[i, :len(sequence)].tolist())
                        # The public CAID3 linker reference contains positive proteins only.
                        # Preserve record boundaries when matching that sampling policy.
                        if protein_id in positive_ids:
                            positive_only_labels.extend(encoded)
                            positive_only_scores.extend(probabilities[i, :len(sequence)].tolist())
                if len(labels) != sum(len(r["labels"]) for r in rows):
                    raise ValueError("Incomplete scoring")
                x_values = np.asarray([score for label, score in zip(labels, scores) if label == "x"])
                results[name][model] = {
                    "published_masked_protocol": summarize(labels, scores, True),
                    "counterfactual_x_as_negative": summarize(labels, scores, False),
                    "positive_proteins_masked": summarize(positive_only_labels, positive_only_scores, True),
                    "positive_proteins_x_as_negative": summarize(positive_only_labels, positive_only_scores, False),
                    "masked_x_mean_score": float(x_values.mean()),
                    "masked_x_fraction_score_ge_0_5": float((x_values >= 0.5).mean())}
    report = {"schema_version": "0.1.0", "status": "counterfactual_label_policy_diagnostic_not_training_or_model_selection",
              "results": results,
              "provenance": {"split_sha256": {n: sha(p) for n, p in SPLITS.items()},
                             "checkpoint_sha256": {n: sha(p) for n, (p, _) in HEADS.items()},
                             "script_sha256": sha(Path(__file__)),
                             "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()},
              "limitations": ["The x residues are unknown/masked under the source protocol, not established negatives.",
                              "Treating x as negative is a sensitivity test only and cannot prove CAID3 annotation equivalence.",
                              "No model weights, checkpoints or thresholds were changed."]}
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
