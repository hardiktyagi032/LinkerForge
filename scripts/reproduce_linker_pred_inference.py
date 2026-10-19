"""Reproduce released LINKER-Pred-Lite/2 checkpoint inference, not training.

Requires the authors' repository and matching precomputed ProtTrans/MSA arrays.
Uses a minimal independently implemented CNN and PyTorch restricted loading.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import torch
from Bio import SeqIO
from numpy._core.multiarray import scalar
from torch import nn


class PublishedCNN(nn.Module):
    def __init__(self, channels: int) -> None:
        super().__init__()
        self.conv1 = nn.Conv1d(channels, 50, kernel_size=1)
        self.conv2 = nn.Conv1d(50, 5, kernel_size=5, padding=2)
        self.last = nn.Conv1d(5, 1, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = torch.relu(self.conv1(x))
        x = torch.relu(self.conv2(x))
        return torch.sigmoid(self.last(x)).flatten(start_dim=1)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()


def git_dirty(path: Path) -> bool:
    return bool(subprocess.check_output(
        ["git", "-C", str(path), "status", "--porcelain"], text=True
    ).strip())


def load_feature(path: Path, length: int, width: int, device: str) -> torch.Tensor:
    feature = np.load(path, allow_pickle=False)
    if feature.shape != (1, length, width) or not np.isfinite(feature).all():
        raise ValueError(f"{path}: expected finite array (1, {length}, {width}), got {feature.shape}")
    return torch.from_numpy(feature[0].astype(np.float32, copy=False).T.copy()).unsqueeze(0).to(device)


def load_checkpoint(path: Path, channels: int, device: str) -> PublishedCNN:
    # The released files contain NumPy scalar metadata. Permit only these known
    # NumPy types; do not use weights_only=False on downloaded pickle files.
    with torch.serialization.safe_globals([scalar, np.dtype, type(np.dtype("float64"))]):
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(checkpoint, dict) or "model_state_dict" not in checkpoint:
        raise ValueError(f"Not a supported released checkpoint: {path}")
    model = PublishedCNN(channels)
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    return model.to(device).eval()


def predict(args: argparse.Namespace) -> dict:
    records = list(SeqIO.parse(args.fasta, "fasta"))
    if len(records) != 1:
        raise ValueError("Provide exactly one FASTA record per invocation")
    record = records[0]
    seq_id, length = record.id, len(record.seq)
    if not seq_id or length < 1:
        raise ValueError("FASTA ID and sequence must be nonempty")
    if args.model == "pred2" and length > 1022:
        raise ValueError("This adapter requires MSA features and supports at most 1022 residues for Pred2")
    device = args.device
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    features = {"protTrans": load_feature(args.prottrans, length, 1024, device)}
    if args.model == "pred2":
        if args.msa is None:
            raise ValueError("Pred2 requires --msa")
        features["msa_transformer"] = load_feature(args.msa, length, 768, device)
    names = [f"cv20_filter_cc5_cnn2_L3_50_protTrans.pth_f{i}" for i in range(1, 6)]
    if args.model == "pred2":
        names = (
            [f"cv20_filter_cc5_cnn2_L3_50_msa_transformer.pth_f{i}" for i in range(1, 6)]
            + names
            + [f"cv20_len10_filter_cc5_cnn2_L3_50_msa_transformer.pth_f{i}" for i in range(1, 6)]
        )
    predictions = []
    checkpoint_hashes = {}
    with torch.inference_mode():
        for name in names:
            path = args.upstream / "predictor" / name
            feature_type = "msa_transformer" if "msa_transformer" in name else "protTrans"
            model = load_checkpoint(path, features[feature_type].shape[1], device)
            predictions.append(model(features[feature_type]).cpu().numpy()[0])
            checkpoint_hashes[name] = sha256(path)
    scores = np.mean(predictions, axis=0)
    if scores.shape != (length,) or not np.isfinite(scores).all():
        raise ValueError("Invalid ensemble prediction")
    threshold = 0.07  # Authors' params/hyperparams.py; strict greater-than.
    config = {"model": args.model, "checkpoint_names": names, "threshold": threshold, "ensemble": "arithmetic_mean"}
    input_hashes = {"fasta": sha256(args.fasta), "prottrans": sha256(args.prottrans)}
    if args.msa is not None and args.model == "pred2":
        input_hashes["msa"] = sha256(args.msa)
    return {
        "schema_version": "0.1.0",
        "predictor": "LINKER-Pred2" if args.model == "pred2" else "LINKER-Pred-Lite",
        "sequence_id": seq_id,
        "sequence_length": length,
        "scores": scores.tolist(),
        "labels": (scores > threshold).astype(int).tolist(),
        "threshold": threshold,
        "evidence_quality": "published_checkpoint_inference",
        "provenance": {
            "source_ids": [f"{args.upstream.name}:{seq_id}"],
            "upstream_commit": git_commit(args.upstream),
            "pipeline_commit": git_commit(Path(__file__).resolve().parents[1]),
            "pipeline_dirty": git_dirty(Path(__file__).resolve().parents[1]),
            "adapter_sha256": sha256(Path(__file__).resolve()),
            "config_hash": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
            "input_hashes": input_hashes,
            "checkpoint_hashes": checkpoint_hashes,
            "software": {"python": sys.version.split()[0], "torch": torch.__version__, "numpy": np.__version__},
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("lite", "pred2"), required=True)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--fasta", type=Path, required=True)
    parser.add_argument("--prottrans", type=Path, required=True)
    parser.add_argument("--msa", type=Path)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = predict(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "model": result["predictor"], "sequence_id": result["sequence_id"], "positive_residues": sum(result["labels"])}))


if __name__ == "__main__":
    main()
