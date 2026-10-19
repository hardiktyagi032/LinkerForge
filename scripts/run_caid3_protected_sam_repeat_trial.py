"""Fail-closed repeat of a SAM-like variant on protected DFL data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import run_caid3_protected_dfl_trial as protected
import run_dfl_disorder_transfer as trial
from linkerforge.models.sam_linker_variants import SAMLinkerVariant

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/dfl_sam_repeat_2026-10-17.json"
MODEL_SOURCE = ROOT / "src/linkerforge/models/sam_linker_variants.py"
BASE_HEAD_SOURCE = ROOT / "src/linkerforge/models/promptable_linker_segmenter.py"
ORIGINAL_BATCH = ROOT / "configs/dfl_sam_ideas_batch_2026-10-17.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-seconds", type=float, default=1800)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    original = json.loads(ORIGINAL_BATCH.read_text(encoding="utf-8"))
    if [args.variant, args.seed] not in config["rounds"]:
        raise ValueError("Variant/seed absent from preregistered repeat queue")
    for key in ("data_manifest", "architecture", "conditions", "frozen_encoder", "batch_size",
                "max_residues_per_window", "auxiliary_semantic_epochs", "dfl_finetune_epochs",
                "optimizer", "learning_rate", "development_selection"):
        if config[key] != original[key]:
            raise ValueError(f"Repeat differs from original training recipe: {key}")
    if not 0 < args.max_seconds <= config["max_seconds_per_trial"]:
        raise ValueError("Invalid time bound")
    protected.preflight()
    if args.preflight_only:
        print(json.dumps({"status": "preflight_passed", "variant": args.variant,
                          "seed": args.seed, "data_manifest_sha256": trial.sha(protected.DATA / "manifest.json")}))
        return
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    trial.CONFIG_PATH = CONFIG
    trial.TRAIN = protected.DATA / "train.jsonl"
    trial.DEV = protected.DATA / "development.jsonl"
    trial.AUX = protected.DATA / "auxiliary.jsonl"
    trial.AUX_MANIFEST = protected.ALIAS
    trial.DATA_MANIFEST = protected.DATA / "manifest.json"
    trial.preflight = protected.preflight
    trial.configure_head = lambda arch, dimension, device: SAMLinkerVariant(
        dimension, args.variant).to(device) if arch == "samlike" else None
    args.arch = "samlike"
    args.condition = "disorder_transfer"
    try:
        trial.run_trial(args)
    finally:
        path = args.output_dir / "manifest.json"
        if path.exists():
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest.update({"variant": args.variant, "launcher_sha256": trial.sha(Path(__file__)),
                             "model_source_sha256": trial.sha(MODEL_SOURCE),
                             "base_head_source_sha256": trial.sha(BASE_HEAD_SOURCE),
                             "blacklist_manifest_sha256": trial.sha(protected.DATA / "manifest.json"),
                             "blacklist_status": "passed_before_training",
                             "claim_status": "CAID3_public_retrospective_not_fresh_blind"})
            path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
