"""Run a DFL baseline only after the CAID3 sequence blacklist passes.

Reuses the previously frozen SAM-like/YOLO-1D training function with explicit
versioned data paths. The original exploratory source is not modified.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import run_dfl_disorder_transfer as trial
from preflight_caid3_protected_training import verify

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/caid3_protected_dfl_v1"
CONFIG = ROOT / "configs/dfl_caid3_protected_baselines_2026-10-16.json"
ALIAS = DATA / "auxiliary_alias_manifest.json"
FROZEN_TRAINING_SOURCE_SHA = "43c529dd72cc42f4ff1a5ade38a5d5601a6e4c7ecdce6501c162219a8128a4d4"


def preflight() -> tuple[list[dict], list[dict]]:
    if trial.sha(Path(trial.__file__)) != FROZEN_TRAINING_SOURCE_SHA:
        raise ValueError("Original training implementation changed; review before running")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if config["data_manifest"] != str((DATA / "manifest.json").relative_to(ROOT)).replace("\\", "/"):
        raise ValueError("Training config does not name the protected data manifest")
    verified = verify(DATA / "manifest.json")
    if verified["status"] != "pass_under_declared_sequence_screen":
        raise ValueError("CAID3 blacklist did not pass")
    alias = json.loads(ALIAS.read_text(encoding="utf-8"))
    if alias["files"]["pretrain"]["sha256"] != trial.sha(DATA / "auxiliary.jsonl"):
        raise ValueError("Auxiliary alias hash mismatch")
    train = [json.loads(line) for line in (DATA / "train.jsonl").read_text(encoding="utf-8").splitlines()]
    development = [json.loads(line) for line in (DATA / "development.jsonl").read_text(encoding="utf-8").splitlines()]
    return train, development


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arch", choices=("samlike", "yolo1d"), required=True)
    parser.add_argument("--condition", choices=("direct", "disorder_transfer"), required=True)
    parser.add_argument("--seed", type=int, choices=(7, 17, 31), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-seconds", type=float, default=1800)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    preflight()
    if args.preflight_only:
        print(json.dumps({"status": "preflight_passed", "data_manifest_sha256": trial.sha(DATA / "manifest.json")}))
        return
    trial.CONFIG_PATH = CONFIG
    trial.TRAIN = DATA / "train.jsonl"
    trial.DEV = DATA / "development.jsonl"
    trial.AUX = DATA / "auxiliary.jsonl"
    trial.AUX_MANIFEST = ALIAS
    trial.DATA_MANIFEST = DATA / "manifest.json"
    trial.preflight = preflight
    try:
        trial.run_trial(args)
    finally:
        manifest_path = args.output_dir / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["launcher_sha256"] = trial.sha(Path(__file__))
            manifest["blacklist_manifest_sha256"] = trial.sha(DATA / "manifest.json")
            manifest["blacklist_status"] = "passed_before_training"
            manifest["claim_status"] = "CAID3_public_retrospective_not_fresh_blind"
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
