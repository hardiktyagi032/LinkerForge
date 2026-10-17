"""One fail-closed SAM-like idea trial, using the frozen baseline trainer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import run_caid3_protected_dfl_trial as protected
import run_dfl_disorder_transfer as trial
from linkerforge.models.sam_linker_variants import SAMLinkerVariant, VARIANTS

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/dfl_sam_ideas_batch_2026-10-17.json"
MODEL_SOURCE = ROOT / "src/linkerforge/models/sam_linker_variants.py"
BASE_HEAD_SOURCE = ROOT / "src/linkerforge/models/promptable_linker_segmenter.py"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=VARIANTS, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-seconds", type=float, default=1800)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if args.variant not in [name for group in config["rounds"] for name in group]:
        raise ValueError("Variant absent from frozen batch")
    if config["data_manifest"] != str((protected.DATA / "manifest.json").relative_to(ROOT)).replace("\\", "/"):
        raise ValueError("Wrong protected data manifest")
    if not 0 < args.max_seconds <= config["max_seconds_per_trial"]:
        raise ValueError("Invalid trial time bound")
    protected.preflight()
    if args.preflight_only:
        print(json.dumps({"status": "preflight_passed", "variant": args.variant,
                          "data_manifest_sha256": trial.sha(protected.DATA / "manifest.json")}))
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
    args.seed = 7
    try:
        trial.run_trial(args)
    finally:
        path = args.output_dir / "manifest.json"
        if path.exists():
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest.update({"variant": args.variant,
                             "launcher_sha256": trial.sha(Path(__file__)),
                             "model_source_sha256": trial.sha(MODEL_SOURCE),
                             "base_head_source_sha256": trial.sha(BASE_HEAD_SOURCE),
                             "blacklist_manifest_sha256": trial.sha(protected.DATA / "manifest.json"),
                             "blacklist_status": "passed_before_training",
                             "claim_status": "CAID3_public_retrospective_not_fresh_blind"})
            path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
