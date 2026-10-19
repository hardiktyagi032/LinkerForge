"""Exploratory cross-ontology DLD checkpoint scoring on official CAID3 linker reference.

This is neither model selection nor a valid independent superiority test:
known DLD train/validation overlap exists for three CAID3 proteins.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import torch
from sklearn.metrics import average_precision_score, roc_auc_score
from transformers import AutoModel, AutoTokenizer

from audit_caid3_dld_overlap import caid_records
from train_esm2_linker_detector import ResidueHead, file_hash


def score_sequence(backbone, tokenizer, head, sequence: str, device: torch.device) -> list[float]:
    scores: list[float] = []
    for start in range(0, len(sequence), 510):
        fragment = sequence[start:start + 510]
        encoded = tokenizer(fragment, return_tensors="pt", add_special_tokens=True, truncation=False)
        encoded = {key: value.to(device) for key, value in encoded.items()}
        with torch.no_grad():
            hidden = backbone(**encoded).last_hidden_state[:, 1:1 + len(fragment)]
            probabilities = head(hidden).sigmoid()[0].detach().cpu().tolist()
        if len(probabilities) != len(fragment):
            raise ValueError("Model output and sequence fragment differ in length")
        scores.extend(probabilities)
    return scores


def summarize(rows: list[tuple[str, str, str, list[float]]]) -> dict:
    truth, scores = [], []
    for _, _, labels, predicted in rows:
        for label, score in zip(labels, predicted):
            if label != "-":
                truth.append(label == "1")
                scores.append(score)
    if not truth or not any(truth) or all(truth):
        raise ValueError("No evaluable positive and negative labels")
    return {"proteins": len(rows), "evaluated_residues": len(truth),
            "positive_residues": sum(truth),
            "average_precision": float(average_precision_score(truth, scores)),
            "roc_auc": float(roc_auc_score(truth, scores))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--overlap-audit", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("CUDA unavailable; refusing CPU inference")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError("Output directory must be empty and isolated")
    audit = json.loads(args.overlap_audit.read_text(encoding="utf-8"))
    if (audit["status"] != "sequence_overlap_screen_not_full_homology_certification" or
            audit["source_sha256"] != file_hash(args.reference)):
        raise ValueError("CAID3 reference/overlap audit mismatch")
    records = caid_records(args.reference)
    if len(records) != 31 or sum(labels.count("1") for _, _, labels in records) != 1379:
        raise ValueError("Unexpected CAID3 Linker reference content")
    manifest_path = args.checkpoint.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    state = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    if state["model_id"] != manifest["model_id"] or state["revision"] != manifest["revision"]:
        raise ValueError("Checkpoint/backbone manifest mismatch")
    device = torch.device("cuda")
    tokenizer = AutoTokenizer.from_pretrained(state["model_id"], revision=state["revision"])
    backbone = AutoModel.from_pretrained(state["model_id"], revision=state["revision"]).to(device).eval()
    backbone.requires_grad_(False)
    head = ResidueHead(backbone.config.hidden_size).to(device).eval()
    head.load_state_dict(state["head"])
    scored = [(name, sequence, labels, score_sequence(backbone, tokenizer, head, sequence, device))
              for name, sequence, labels in records]
    flagged = {hit["caid_id"] for hit in audit["hits"]}
    if not flagged:
        raise ValueError("Expected overlap flags absent; audit changed")
    clean_screened = [row for row in scored if row[0] not in flagged]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    prediction_path = args.output_dir / "dld_esm2_transfer.caid"
    with prediction_path.open("w", encoding="utf-8") as stream:
        for name, sequence, _, scores in scored:
            stream.write(f">{name}\n")
            for index, (residue, score) in enumerate(zip(sequence, scores), start=1):
                stream.write(f"{index}\t{residue}\t{score:.6f}\t{int(score >= 0.5)}\n")
    root = Path(__file__).resolve().parents[1]
    report = {
        "schema_version": "0.1.0", "status": "exploratory_cross_ontology_contaminated_public_benchmark",
        "target": "CAID3_DisProt_disordered_flexible_linker",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "reference_url": "https://caid.idpcentral.org/assets/sections/challenge/static/references/3/linker.fasta",
        "reference_sha256": file_hash(args.reference),
        "checkpoint_sha256": file_hash(args.checkpoint),
        "overlap_audit_sha256": file_hash(args.overlap_audit),
        "prediction_file": str(prediction_path.resolve().relative_to(root)),
        "prediction_sha256": file_hash(prediction_path),
        "script_sha256": file_hash(Path(__file__)),
        "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "software": {"python": sys.version.split()[0], "torch": torch.__version__,
                     "transformers": __import__("transformers").__version__,
                     "sklearn": __import__("sklearn").__version__},
        "model_id": state["model_id"], "model_revision": state["revision"],
        "gpu": torch.cuda.get_device_name(0),
        "metrics": {"all_public_targets": summarize(scored),
                    "after_known_overlap_screen": summarize(clean_screened)},
        "known_overlap_ids": sorted(flagged),
        "limitations": [
            "DLD IDL/DDL training labels and CAID3 DisProt DFL labels are different ontologies.",
            "Three CAID3 targets have high-identity DLD train/validation matches; the full metric is contaminated.",
            "Top-5 k-mer/local overlap is not a complete homology audit; the screened subset is not certified independent.",
            "Threshold-free APS/AUC are exploratory and not an official CAID scorer reproduction or matched leaderboard comparison.",
            "CAID3 has no no-linker proteins, so protein specificity is unavailable."
        ]
    }
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["metrics"]), flush=True)


if __name__ == "__main__":
    main()
