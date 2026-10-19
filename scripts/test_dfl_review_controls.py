"""Score frozen CNN on review controls; TE82 is development, not blind test."""

import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import torch
from sklearn.metrics import average_precision_score, roc_auc_score
from transformers import AutoModel, AutoTokenizer

from train_dfl_masked_cnn import MODEL_ID, ResidueHead, load


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "reports/dfl_te82_blinded_review_packet_2026-10-12.json"
CROSSWALK = ROOT / "artifacts/dfl_te82_disprot_annotation_crosswalk_2026-10-12.json"
SOURCE = ROOT / "data/processed/published_dfl_splits/te82.jsonl"
CHECKPOINT = ROOT / "artifacts/dfl-cnn-seed7-001/best.pt"
OUTPUT = ROOT / "artifacts/dfl_te82_review_control_test_2026-10-12.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score_sequence(backbone, tokenizer, head, sequence, device):
    scores = []
    for start in range(0, len(sequence), 510):
        frag = sequence[start:start + 510]
        tokens = tokenizer(frag, return_tensors="pt", add_special_tokens=True, truncation=False)
        hidden = backbone(**{k: v.to(device) for k, v in tokens.items()}).last_hidden_state[:, 1:1 + len(frag)]
        scores.extend(head(hidden).sigmoid()[0].cpu().tolist())
    if len(scores) != len(sequence):
        raise ValueError("Incomplete scoring")
    return scores


def main():
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required")
    device = torch.device("cuda")
    packet = json.loads(PACKET.read_text(encoding="utf-8"))["records"]
    crosswalk = {r["case_id"]: r for r in json.loads(CROSSWALK.read_text(encoding="utf-8"))["records"]}
    source = {r["protein_id"]: r for r in load(SOURCE)}
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    backbone = AutoModel.from_pretrained(MODEL_ID).to(device).eval()
    backbone.requires_grad_(False)
    state = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    if state["model_id"] != MODEL_ID:
        raise ValueError("Checkpoint/backbone mismatch")
    head = ResidueHead(backbone.config.hidden_size).to(device).eval()
    head.load_state_dict(state["head"])
    scored = []
    with torch.no_grad():
        for case in packet:
            row = source[case["protein_id"]]
            scores = score_sequence(backbone, tokenizer, head, row["sequence"], device)
            begin, end = case["start_1based"], case["end_1based"]
            values = scores[begin - 1:end]
            anno = crosswalk[case["case_id"]]
            scored.append({"case_id": case["case_id"], "selection_category": anno["selection_category"],
                           "mean_score": float(np.mean(values)), "max_score": float(np.max(values)),
                           "curated_overlap": anno["same_sequence_curated_overlap"],
                           "source_label": anno["published_label"]})
    controls = [r for r in scored if r["selection_category"] in
                {"published_positive_control", "published_negative_control"}]
    truth = np.array([r["selection_category"] == "published_positive_control" for r in controls], dtype=int)
    values = np.array([r["mean_score"] for r in controls])
    result = {"cases": len(controls), "published_positive_controls": int(truth.sum()),
              "published_negative_controls": int(len(truth) - truth.sum()),
              "average_precision": float(average_precision_score(truth, values)),
              "auroc": float(roc_auc_score(truth, values)),
              "positive_mean_score": float(values[truth == 1].mean()),
              "negative_mean_score": float(values[truth == 0].mean())}
    report = {"schema_version": "0.1.0", "status": "retrospective_development_control_test_not_independent",
              "control_result": result, "case_scores": scored,
              "provenance": {"packet_sha256": sha(PACKET), "crosswalk_sha256": sha(CROSSWALK),
                             "source_sha256": sha(SOURCE), "checkpoint_sha256": sha(CHECKPOINT),
                             "script_sha256": sha(Path(__file__)),
                             "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()},
              "limitations": ["TE82 was used for development/model selection, so these control metrics are not generalization estimates.",
                              "Published 0/1 labels are operational controls, not new independent human adjudication.",
                              "The one curated-overlapping unknown was model-selected; do not count it as an unbiased test positive.",
                              "Unannotated unknowns remain unknown and are excluded from control metrics."]}
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
