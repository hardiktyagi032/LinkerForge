"""One-time locked CAID3 common-27 retrospective for a frozen DFL checkpoint.

Selection must have been finalized on filtered development data before this
script reads CAID3 labels. The official CAID evaluator is run after inference.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys

import torch
from transformers import AutoModel, AutoTokenizer

from audit_caid3_dld_overlap import caid_records
from compare_dfl_caid3_common import competitor_scores, metrics
from preflight_caid3_protected_training import verify
from run_dfl_disorder_transfer import configure_head, sha
from linkerforge.models.sam_linker_variants import SAMLinkerVariant, VARIANTS

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/caid3_protected_dfl_v1"
REFERENCE = ROOT / "artifacts/caid3-common-coverage-001/linker-common.fasta"
BASELINES = ROOT / "artifacts/caid3-common-coverage-001/predictions"
EVALUATOR = ROOT / "artifacts/caid-evaluator/caid.py"
MODEL_ID = "facebook/esm2_t12_35M_UR50D"


@torch.no_grad()
def predict(backbone, tokenizer, head, arch: str, sequence: str, device) -> list[float]:
    values = []
    for offset in range(0, len(sequence), 510):
        fragment = sequence[offset:offset + 510]
        tokens = tokenizer(fragment, return_tensors="pt", add_special_tokens=True, truncation=False)
        hidden = backbone(**{key: value.to(device) for key, value in tokens.items()}).last_hidden_state[:, 1:1 + len(fragment)]
        valid = torch.ones((1, len(fragment)), dtype=torch.bool, device=device)
        if arch == "samlike":
            logits = head(hidden, valid, torch.zeros(1, dtype=torch.long, device=device))["semantic_logits"]
        else:
            logits = head(hidden, valid)["semantic_logits"][:, :, 0]
        scores = logits.sigmoid()[0].cpu().tolist()
        if len(scores) != len(fragment):
            raise ValueError("Prediction length mismatch")
        values.extend(scores)
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    # The official evaluator runs from its own directory; relative output paths
    # otherwise make an intact predictions folder appear empty to that process.
    args.selection = args.selection.resolve()
    args.output_dir = args.output_dir.resolve()
    if args.output_dir.exists():
        raise FileExistsError("CAID3 output already exists; refusing repeated overwrite")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable for frozen inference")
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    if selection.get("frozen_before_caid3") is not True or selection.get("selection_basis") != "filtered_development_only":
        raise ValueError("Checkpoint selection was not declared frozen before CAID3")
    data_gate = verify(DATA / "manifest.json")
    checkpoint_path = ROOT / selection["checkpoint"]
    if sha(checkpoint_path) != selection["checkpoint_sha256"]:
        raise ValueError("Frozen checkpoint hash mismatch")
    manifest_path = checkpoint_path.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))["files"]
    if (manifest["status"] != "completed" or
            manifest["train_sha256"] != expected["train"]["sha256"] or
            manifest["dev_sha256"] != expected["development"]["sha256"] or
            manifest["aux_sha256"] != expected["auxiliary"]["sha256"] or
            manifest.get("blacklist_status") != "passed_before_training"):
        raise ValueError("Checkpoint was not trained under the protected-data contract")
    arch = manifest["arch"]
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if checkpoint["arch"] != arch or manifest["model_id"] != MODEL_ID:
        raise ValueError("Model/checkpoint mismatch")
    reference = caid_records(REFERENCE)
    if len(reference) != 27 or sum(labels.count("1") for _, _, labels in reference) != 1214:
        raise ValueError("Unexpected common-coverage CAID3 reference")
    baseline_paths = sorted(BASELINES.glob("*.caid"))
    if len(baseline_paths) != 7:
        raise ValueError("Expected seven original released predictor files")
    device = torch.device("cuda")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    backbone = AutoModel.from_pretrained(MODEL_ID).to(device).eval()
    backbone.requires_grad_(False)
    variant = selection.get("variant")
    if variant is not None and (arch != "samlike" or variant not in VARIANTS or
                                manifest.get("variant") != variant):
        raise ValueError("Frozen variant/manifest mismatch")
    head = (SAMLinkerVariant(backbone.config.hidden_size, variant).to(device).eval()
            if variant else configure_head(arch, backbone.config.hidden_size, device).eval())
    head.load_state_dict(checkpoint["head"])
    by_id = {identifier: predict(backbone, tokenizer, head, arch, sequence, device)
             for identifier, sequence, _ in reference}
    results = {path.stem: metrics(reference, competitor_scores(path, reference)) for path in baseline_paths}
    results["LinkerForge_frozen"] = metrics(reference, by_id)
    args.output_dir.mkdir(parents=True)
    predictions = args.output_dir / "predictions"
    predictions.mkdir()
    for path in baseline_paths:
        shutil.copyfile(path, predictions / path.name)
    ours = predictions / "LinkerForge_frozen.caid"
    with ours.open("w", encoding="utf-8") as stream:
        for identifier, sequence, _ in reference:
            stream.write(f">{identifier}\n")
            for position, (residue, score) in enumerate(zip(sequence, by_id[identifier]), 1):
                stream.write(f"{position}\t{residue}\t{score:.8f}\t{int(score >= 0.5)}\n")
    official = args.output_dir / "official_evaluator"
    subprocess.run([sys.executable, str(EVALUATOR), str(REFERENCE), str(predictions),
                    "-o", str(official)], cwd=EVALUATOR.parent, check=True, timeout=3600)
    report = {"schema_version": "1.0.0", "status": "public_retrospective_not_fresh_independent",
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "reference_sha256": sha(REFERENCE), "selection_sha256": sha(args.selection),
              "checkpoint_sha256": sha(checkpoint_path), "checkpoint_manifest_sha256": sha(manifest_path),
              "protected_manifest_sha256": sha(DATA / "manifest.json"),
              "official_evaluator_sha256": sha(EVALUATOR),
              "prediction_sha256": sha(ours), "baseline_sha256": {p.name: sha(p) for p in baseline_paths},
              "data_gate": data_gate["status"], "results_local_crosscheck": results,
              "official_evaluator_dir": str(official),
              "limitations": ["CAID3 is public and previously inspected; this is not a fresh blind test.",
                              "The sequence blacklist is not a full remote-homology or ESM pretraining audit.",
                              "CAID3 common-27 has no no-linker-protein specificity estimate."]}
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
