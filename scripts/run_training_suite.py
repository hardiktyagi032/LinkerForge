"""Reproducible launcher for implemented LinkerForge training tracks.

The suite never substitutes a planned architecture with an unrelated model.
It runs the provisional hand-feature pilot when requested, and launches the
CUDA detector only after its reference-data preflight passes. Other tracks
remain explicitly pending until their implementations and data exist.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str], env: dict[str, str]) -> None:
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-records", type=Path)
    parser.add_argument("--detector-train")
    parser.add_argument("--detector-validation")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--resume", type=Path)
    args = parser.parse_args()
    if bool(args.detector_train) != bool(args.detector_validation):
        parser.error("Detector train and validation sources must be supplied together")
    if not args.pilot_records and not args.detector_train:
        parser.error("Supply pilot records, detector streams, or both")
    if args.epochs < 1 or args.batch_size < 1:
        parser.error("Epochs and batch size must be positive")
    config_path = ROOT / "configs" / "training-suite.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            text=True, capture_output=True, check=True).stdout.strip()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outcomes = {item["id"]: "not_run" for item in config["detector_experiments"] +
                config["ranker_experiments"]}
    manifest = {"schema_version": "0.1.0", "created_utc": datetime.now(timezone.utc).isoformat(),
                "suite_config_sha256": file_sha(config_path), "pipeline_commit": commit,
                "status": "running", "outcomes": outcomes,
                "notes": "Planned/unimplemented models are never reported as trained."}
    manifest_path = args.output_dir / "training-suite-manifest.json"

    def save_manifest():
        temporary = manifest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, manifest_path)

    save_manifest()
    try:
        if args.pilot_records:
            pilot = args.pilot_records.resolve()
            report = args.output_dir / "pilot-baselines.json"
            run([sys.executable, str(ROOT / "scripts" / "train_pilot_baseline.py"),
                 "--records", str(pilot), "--output", str(report),
                 "--seed", str(config["seed"])], env)
            manifest["pilot_source_sha256"] = file_sha(pilot)
            manifest["pilot_report_sha256"] = file_sha(report)
            outcomes["nearest_training"] = "evaluated_provisional_pilot"
            outcomes["hand_feature_pairwise"] = "trained_evaluated_provisional_pilot"
            for name in ("fixed_gs", "length_heuristic", "hand_features_rule"):
                outcomes[name] = "evaluated_provisional_pilot"
            save_manifest()
        if args.detector_train:
            preflight = args.output_dir / "detector-preflight.json"
            run([sys.executable, str(ROOT / "scripts" / "preflight_detector_data.py"),
                 "--train", args.detector_train, "--validation", args.detector_validation,
                 "--output", str(preflight)], env)
            manifest["detector_preflight_sha256"] = file_sha(preflight)
            save_manifest()
            command = [sys.executable, str(ROOT / "scripts" / "train_linker_detector_gpu.py"),
                       "--train", args.detector_train,
                       "--validation", args.detector_validation,
                       "--checkpoint-dir", str(args.output_dir / "detector-checkpoints"),
                       "--epochs", str(args.epochs), "--batch-size", str(args.batch_size)]
            if args.resume:
                command += ["--resume", str(args.resume)]
            run(command, env)
            outcomes["residue_cnn_gpu"] = "training_command_completed_check_metrics_and_checkpoint"
            save_manifest()
        manifest["status"] = "completed_requested_tracks_only"
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        save_manifest()
    print(json.dumps({"manifest": str(manifest_path), "status": manifest["status"]}))


if __name__ == "__main__":
    main()
