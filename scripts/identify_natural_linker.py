"""Identify provisional interdomain-linker spans in one natural protein FASTA.

This is an inference adapter for the existing DLD-trained ESM-2 detector. It
does not establish domain boundaries or experimental linker function.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import torch
from transformers import AutoModel, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from linkerforge.detector.regions import intervals  # noqa: E402
from train_esm2_linker_detector import ResidueHead, file_hash  # noqa: E402
from train_span_linker_detector import SpanHead  # noqa: E402


KNOWN_CHECKPOINT_SHA256 = "adc41ba95190df0c55a50e75f80f1042386f6e90ae87c1a1620e53eb09afc42c"
KNOWN_THRESHOLD = 0.9753981232643127


def read_one_fasta(path: Path) -> tuple[str, str]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines or not lines[0].startswith(">") or any(line.startswith(">") for line in lines[1:]):
        raise ValueError("Provide exactly one FASTA entry")
    identifier = lines[0][1:].split()[0]
    if not identifier:
        raise ValueError("FASTA identifier is empty")
    return identifier, "".join(lines[1:]).upper()


@torch.inference_mode()
def residue_scores(sequence: str, checkpoint: Path, device: str, allow_download: bool) -> tuple[list[float], dict]:
    state = torch.load(checkpoint, map_location="cpu", weights_only=False)
    manifest = json.loads((checkpoint.parent / "manifest.json").read_text(encoding="utf-8"))
    if state["model_id"] != manifest["model_id"] or state["revision"] != manifest["revision"]:
        raise ValueError("Checkpoint backbone does not match run manifest")
    model_id, revision = state["model_id"], state["revision"]
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision, local_files_only=not allow_download)
    backbone = AutoModel.from_pretrained(model_id, revision=revision, local_files_only=not allow_download).to(device).eval()
    span_architecture = state.get("architecture") == "frozen_esm2_residue_cnn_with_auxiliary_start_end_heads"
    head = (SpanHead(backbone.config.hidden_size) if span_architecture
            else ResidueHead(backbone.config.hidden_size)).to(device).eval()
    head.load_state_dict(state["head"], strict=True)
    scores = []
    for offset in range(0, len(sequence), 510):
        fragment = sequence[offset:offset + 510]
        tokens = tokenizer(fragment, return_tensors="pt", add_special_tokens=True, truncation=False)
        hidden = backbone(**{key: value.to(device) for key, value in tokens.items()}).last_hidden_state[:, 1:1 + len(fragment)]
        logits = head(hidden)
        if span_architecture:
            logits = logits[0]
        values = logits.sigmoid()[0].cpu().tolist()
        if len(values) != len(fragment):
            raise ValueError("Backbone output length disagrees with input sequence")
        scores.extend(values)
    return scores, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fasta", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--threshold", type=float,
                        help="Required for checkpoints other than the frozen asymmetric fold-4 reference")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--allow-download", action="store_true", help="Permit model download; default is cached/offline only")
    parser.add_argument("--output", type=Path, help="Optional JSON output; stdout otherwise")
    args = parser.parse_args()
    if args.device == "cuda" and not torch.cuda.is_available():
        raise SystemExit("CUDA unavailable; specify --device cpu for an inference-only smoke test")
    identifier, sequence = read_one_fasta(args.fasta)
    checkpoint_hash = file_hash(args.checkpoint)
    selected_epoch = None
    if args.threshold is None and checkpoint_hash != KNOWN_CHECKPOINT_SHA256:
        state = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
        point = state.get("validation", {}).get("validation_precision_90_operating_point", {})
        if state.get("architecture") != "frozen_esm2_residue_cnn_with_auxiliary_start_end_heads" or point.get("threshold") is None:
            raise SystemExit("Unknown checkpoint: supply its prespecified validation-selected --threshold")
        threshold = float(point["threshold"])
        selected_epoch = state.get("epoch")
    else:
        threshold = KNOWN_THRESHOLD if args.threshold is None else args.threshold
    scores, manifest = residue_scores(sequence, args.checkpoint, args.device, args.allow_download)
    calls = intervals(sequence, scores, threshold)
    config = {"threshold": threshold, "window_residues": 510, "checkpoint_sha256": checkpoint_hash}
    result = {
        "schema_version": "0.1.0", "task": "natural_protein_linker_identifier",
        "sequence_id": identifier, "sequence_length": len(sequence),
        "sequence_sha256": hashlib.sha256(sequence.encode()).hexdigest(),
        "predicted_linker_present": bool(calls), "predicted_linkers": calls,
        "coordinate_system": "1-based inclusive sequence positions",
        "threshold": threshold,
        "threshold_source": ("DLD fold-4 validation-selected at empirical residue precision >=0.90"
                             if args.threshold is None else
                             "caller-supplied; performance not independently calibrated"),
        "model": {"checkpoint_sha256": checkpoint_hash, "model_id": manifest["model_id"],
                  "revision": manifest["revision"], "selected_epoch": selected_epoch if selected_epoch is not None else
                  (5 if checkpoint_hash == KNOWN_CHECKPOINT_SHA256 else None),
                  "training_data_sha256": manifest["train_sha256"],
                  "validation_data_sha256": manifest["validation_sha256"]},
        "limitations": ["Predicted intervals are not experimentally verified linkers",
                        "Flanking segments are not independently confirmed protein domains",
                        "No call does not exclude a linker; the high-precision validation point had low recall",
                        "Precision on unrelated natural proteins is unknown"],
        "provenance": {
            "input_fasta_sha256": file_hash(args.fasta),
            "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
            "software": {"python": sys.version.split()[0], "torch": torch.__version__,
                         "transformers": __import__("transformers").__version__},
            "evidence_quality": "model_prediction_not_experimental_observation",
        },
    }
    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
