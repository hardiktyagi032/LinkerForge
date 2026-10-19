"""One fail-closed PU-loss SAM-like trial (separate from the frozen idea launcher).

Replaces only the DFL-stage semantic residue BCE with a uPU/nnPU risk; the
auxiliary stage, other loss terms, data, encoder and scoring are unchanged.
Refuses to run unless the config carries an explicit class prior.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import run_caid3_protected_dfl_trial as protected
import run_dfl_disorder_transfer as trial
from linkerforge.models.promptable_linker_segmenter import PromptableLinkerSegmenter, segmenter_loss
from linkerforge.models.pu_loss import PUConfig, pu_semantic_loss

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/dfl_pu_loss_2026-10-17.json"
PU_SOURCE = ROOT / "src/linkerforge/models/pu_loss.py"


def load_config() -> tuple[dict, PUConfig]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if config["data_manifest"] != str((protected.DATA / "manifest.json").relative_to(ROOT)).replace("\\", "/"):
        raise ValueError("Wrong protected data manifest")
    return config, PUConfig.from_dict(config.get("pu", {}))


def make_forward_loss(pu: PUConfig):
    original = trial.forward_loss

    def forward_loss(arch, head, embeddings, group, device, *, auxiliary=False):
        if arch != "samlike":
            raise ValueError("PU arm supports only the SAM-like head")
        if auxiliary:  # auxiliary IDR stage stays identical to the baseline
            return original(arch, head, embeddings, group, device, auxiliary=True)
        valid, residue, presence, spans, exhaustive, concept = trial.target_batch(group, device)
        output = head(embeddings, valid, concept)
        parts = segmenter_loss(output, valid, residue, presence, spans, exhaustive)
        semantic = pu_semantic_loss(output["semantic_logits"], residue, valid, pu)["objective"]
        return parts["total"] - parts["semantic"] + semantic

    return forward_loss


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-seconds", type=float, default=1800)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    config, pu = load_config()  # raises on missing/invalid prior before anything else
    if args.seed not in config["seeds"]:
        raise ValueError("Seed absent from frozen config")
    if not 0 < args.max_seconds <= config["max_seconds_per_trial"]:
        raise ValueError("Invalid trial time bound")
    protected.preflight()
    if args.preflight_only:
        print(json.dumps({"status": "preflight_passed", "seed": args.seed, "pu": pu.__dict__}))
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
    trial.configure_head = lambda arch, dimension, device: (
        PromptableLinkerSegmenter(dimension).to(device) if arch == "samlike" else None)
    trial.forward_loss = make_forward_loss(pu)
    args.arch, args.condition = "samlike", "disorder_transfer"
    try:
        trial.run_trial(args)
    finally:
        path = args.output_dir / "manifest.json"
        if path.exists():
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest.update({"loss": "pu_" + pu.mode, "pu_config": pu.__dict__,
                             "launcher_sha256": trial.sha(Path(__file__)),
                             "pu_source_sha256": trial.sha(PU_SOURCE),
                             "blacklist_manifest_sha256": trial.sha(protected.DATA / "manifest.json"),
                             "blacklist_status": "passed_before_training",
                             "claim_status": "development_only_not_independent"})
            path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
