"""Score author-bundled DP04257 outputs against CAID3; never call this blind."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
from Bio import SeqIO
from sklearn.metrics import average_precision_score, roc_auc_score


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--bundled-fasta", required=True, type=Path)
    parser.add_argument("--lite", required=True, type=Path)
    parser.add_argument("--pred2", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    fasta = list(SeqIO.parse(args.bundled_fasta, "fasta"))
    if len(fasta) != 1 or fasta[0].id != "DP04257":
        raise ValueError("Only the authors' bundled DP04257 example is supported")
    lines = args.reference.read_text(encoding="utf-8").splitlines()
    pos = lines.index(">DP04257")
    reference_sequence, label_line = lines[pos + 1:pos + 3]
    if reference_sequence != str(fasta[0].seq) or len(label_line) != len(reference_sequence):
        raise ValueError("Bundled FASTA and CAID3 reference disagree")
    if set(label_line) - {"0", "1"}:
        raise ValueError("Reference has unhandled masked labels")
    truth = np.fromiter((int(char) for char in label_line), dtype=np.uint8)
    scores = {}
    for path, expected_name in ((args.lite, "LINKER-Pred-Lite"), (args.pred2, "LINKER-Pred2")):
        prediction = json.loads(path.read_text(encoding="utf-8"))
        if prediction["sequence_id"] != "DP04257" or prediction["predictor"] != expected_name:
            raise ValueError(f"Wrong predictor or sequence in {path}")
        if prediction["provenance"]["input_hashes"]["fasta"] != sha256(args.bundled_fasta):
            raise ValueError(f"Input FASTA hash mismatch in {path}")
        probabilities = np.asarray(prediction["scores"], dtype=float)
        labels = np.asarray(prediction["labels"], dtype=np.uint8)
        if probabilities.shape != truth.shape or labels.shape != truth.shape:
            raise ValueError(f"Residue count mismatch in {path}")
        if not np.array_equal(labels, probabilities > prediction["threshold"]):
            raise ValueError(f"Stored labels do not match frozen threshold in {path}")
        tp = int(np.count_nonzero((labels == 1) & (truth == 1)))
        fp = int(np.count_nonzero((labels == 1) & (truth == 0)))
        fn = int(np.count_nonzero((labels == 0) & (truth == 1)))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores[expected_name] = {
            "residue_auprc": float(average_precision_score(truth, probabilities)),
            "residue_auroc": float(roc_auc_score(truth, probabilities)),
            "precision_at_authors_threshold": precision,
            "recall_at_authors_threshold": recall,
            "f1_at_authors_threshold": (2 * precision * recall / (precision + recall)) if precision + recall else 0.0,
            "tp": tp, "fp": fp, "fn": fn,
            "prediction_sha256": sha256(path),
        }
    root = Path(__file__).resolve().parents[1]
    result = {
        "schema_version": "0.1.0",
        "status": "single_bundled_example_scored",
        "evaluation_scope": "not_independent_benchmark",
        "sequence_id": "DP04257",
        "positive_residues": int(truth.sum()),
        "residues": len(truth),
        "predictors": scores,
        "limitations": [
            "The sequence and both feature arrays are bundled with the published predictor repository.",
            "One labelled CAID3 protein does not estimate generalisation or reproduce CAID3-wide scores.",
            "Upstream model training-set overlap with this example is not ruled out.",
        ],
        "provenance": {
            "source_ids": ["CAID3:DP04257", "punch_linker2:DP04257"],
            "reference_sha256": sha256(args.reference),
            "bundled_fasta_sha256": sha256(args.bundled_fasta),
            "pipeline_commit": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
            "script_sha256": sha256(Path(__file__).resolve()),
            "config_hash": hashlib.sha256(b"DP04257|authors_thresholds|CAID3_reference").hexdigest(),
            "evidence_quality": "published_reference_label_bundled_example",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "results": scores}))


if __name__ == "__main__":
    main()
