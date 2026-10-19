"""One-time retrospective common-target CAID3 comparison; no model selection."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import torch
from sklearn.metrics import average_precision_score, roc_auc_score, precision_recall_curve
from transformers import AutoModel, AutoTokenizer

from audit_caid3_dld_overlap import caid_records
from train_dfl_masked_cnn import MODEL_ID, ResidueHead
from train_dfl_masked_span import SpanHead


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "artifacts/caid3-common-coverage-001/linker-common.fasta"
COMPETITORS = ROOT / "artifacts/caid3-common-coverage-001/predictions"
OUTPUT = ROOT / "reports/dfl_caid3_common_retrospective_2026-10-12.json"
CHECKPOINTS = {
    "LinkerForge_CNN": (ROOT / "artifacts/dfl-cnn-seed7-001/best.pt", ResidueHead),
    "LinkerForge_span": (ROOT / "artifacts/dfl-span-seed7-001/best.pt", SpanHead),
    "LinkerForge_precision": (ROOT / "artifacts/dfl-precision-seed7-001/best.pt", ResidueHead),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def competitor_scores(path, reference):
    blocks = {}
    current = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(">"):
            current = line[1:].strip()
            if current in blocks:
                raise ValueError(f"Duplicate {current}")
            blocks[current] = []
        elif current is not None and line.strip():
            blocks[current].append(line.split())
    result = {}
    for name, sequence, _ in reference:
        rows = blocks.get(name)
        if rows is None or len(rows) != len(sequence):
            raise ValueError(f"Incomplete competitor coverage: {path.name}, {name}")
        if any(int(parts[0]) != i or parts[1] != aa for i, (parts, aa) in enumerate(zip(rows, sequence), 1)):
            raise ValueError(f"Competitor sequence/position mismatch: {path.name}, {name}")
        result[name] = [float(parts[2]) for parts in rows]
    return result


@torch.no_grad()
def model_scores(backbone, tokenizer, head, sequence, device, span):
    output = []
    for start in range(0, len(sequence), 510):
        fragment = sequence[start:start + 510]
        tokens = tokenizer(fragment, return_tensors="pt", add_special_tokens=True, truncation=False)
        tokens = {key: value.to(device) for key, value in tokens.items()}
        hidden = backbone(**tokens).last_hidden_state[:, 1:1 + len(fragment)]
        logits = head(hidden)
        if span:
            logits = logits[:, :, 0]
        scores = logits.sigmoid()[0].cpu().tolist()
        if len(scores) != len(fragment):
            raise ValueError("Model score/fragment mismatch")
        output.extend(scores)
    return output


def metrics(reference, by_id):
    truth = np.asarray([x == "1" for name, _, labels in reference for x in labels], dtype=np.uint8)
    values = np.asarray([score for name, _, _ in reference for score in by_id[name]], dtype=np.float64)
    if not np.isfinite(values).all() or len(values) != len(truth):
        raise ValueError("Invalid score vector")
    precision, recall, _ = precision_recall_curve(truth, values)
    f1 = np.divide(2 * precision * recall, precision + recall,
                   out=np.zeros_like(precision), where=precision + recall > 0)
    return {"proteins": len(reference), "residues": len(truth), "positive_residues": int(truth.sum()),
            "aps": float(average_precision_score(truth, values)),
            "auroc": float(roc_auc_score(truth, values)), "fmax": float(f1.max())}


def main():
    if OUTPUT.exists():
        raise FileExistsError("One-time comparison output already exists")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA inference required")
    reference = caid_records(REFERENCE)
    if len(reference) != 27 or sum(labels.count("1") for _, _, labels in reference) != 1214:
        raise ValueError("Unexpected common CAID3 reference")
    baseline_paths = sorted(COMPETITORS.glob("*.caid"))
    if len(baseline_paths) != 7:
        raise ValueError("Expected seven released predictors")
    results = {path.stem: metrics(reference, competitor_scores(path, reference)) for path in baseline_paths}
    device = torch.device("cuda")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    backbone = AutoModel.from_pretrained(MODEL_ID).to(device).eval()
    backbone.requires_grad_(False)
    checkpoint_hashes = {}
    for name, (path, head_class) in CHECKPOINTS.items():
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
        if checkpoint["model_id"] != MODEL_ID:
            raise ValueError("Checkpoint model mismatch")
        head = head_class(backbone.config.hidden_size).to(device).eval()
        head.load_state_dict(checkpoint["head"])
        by_id = {id_: model_scores(backbone, tokenizer, head, sequence, device, head_class is SpanHead)
                 for id_, sequence, _ in reference}
        results[name] = metrics(reference, by_id)
        checkpoint_hashes[name] = sha(path)
    report = {"schema_version": "0.1.0", "status": "retrospective_public_benchmark_not_independent_test",
              "reference": "CAID3_Linker_27_protein_full_coverage_intersection",
              "results": results,
              "provenance": {"reference_sha256": sha(REFERENCE), "baseline_sha256": {p.name: sha(p) for p in baseline_paths},
                             "checkpoint_sha256": checkpoint_hashes, "script_sha256": sha(Path(__file__)),
                             "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                             "python": sys.version.split()[0], "torch": torch.__version__},
              "limitations": ["Public CAID3 labels are not a fresh independent test.",
                              "Original competitor weights are not retrained here; these are released historical score submissions.",
                              "Our three checkpoints were selected on TE82, not CAID3; prior DLD CAID3 review exists in the project.",
                              "TR166-to-CAID3 remote homology is not certified absent.",
                              "CAID3 reference is linker-positive proteins only; no-linker specificity is unavailable.",
                              "This scikit-learn common-score summary must be checked against official CAID evaluation."]}
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
