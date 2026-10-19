"""Check single-sequence inference against stored TE82 development metrics."""

from pathlib import Path

import torch
from transformers import AutoModel, AutoTokenizer

from compare_dfl_yolo_sam_public import (ROOT, checkpoints, embed_records,
                                         head_from_checkpoint, metrics, scores_for)
from train_dfl_masked_cnn import DEV, MODEL_ID, load


def main():
    rows = load(DEV)
    records = [(row["protein_id"], row["sequence"], row["labels"]) for row in rows]
    device = torch.device("cuda")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    backbone = AutoModel.from_pretrained(MODEL_ID).to(device).eval()
    backbone.requires_grad_(False)
    embeddings = embed_records(backbone, tokenizer, records, device)
    for name, dirname, kind in checkpoints():
        if name.startswith("LinkerForge"):
            continue
        path = ROOT / "artifacts" / dirname / "best.pt"
        state = torch.load(path, map_location="cpu", weights_only=False)
        head = head_from_checkpoint(kind, state, backbone.config.hidden_size, device)
        truth, scores = [], []
        for protein, _, labels in records:
            predicted = scores_for(head, kind, embeddings[protein], device)
            if len(predicted) != len(labels):
                raise ValueError(f"Length mismatch: {name}, {protein}")
            truth.extend(label == "1" for label in labels if label != "x")
            scores.extend(score for label, score in zip(labels, predicted) if label != "x")
        observed = metrics(truth, scores)["aps"]
        stored = state["development"]["masked_residue_aps"]
        delta = observed - stored
        print(f"{name} stored={stored:.6f} single_sequence={observed:.6f} delta={delta:+.6f}")
        if abs(delta) > 0.02:
            raise ValueError(f"Large inference-path discrepancy: {name}")


if __name__ == "__main__":
    main()
