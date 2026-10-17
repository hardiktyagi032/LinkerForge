"""Fmax rescore of already APS-selected global-context checkpoints only."""

from __future__ import annotations

import json
from pathlib import Path

import torch
from transformers import AutoModel, AutoTokenizer

import run_caid3_protected_dfl_trial as protected
import run_dfl_disorder_transfer as trial
from score_protected_dfl_development import score_one
from linkerforge.models.competitor_gap_segmenter import CompetitorGapSegmenter


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/track-ml/2026-10-17-global-context-fmax.json"
SCREEN_CONFIG = ROOT / "configs/dfl_competitor_gap_round_2026-10-17.json"
REPEAT_CONFIG = ROOT / "configs/dfl_global_context_repeat_2026-10-17.json"
SCREEN = ROOT / "artifacts/dfl-competitor-gap-round-2026-10-17/global_context"
REPEAT = ROOT / "artifacts/dfl-global-context-repeat-2026-10-17"


def main() -> None:
    if OUT.exists():
        raise FileExistsError(OUT)
    train, development = protected.preflight()
    if len(train) != 79 or len(development) != 42:
        raise ValueError("Protected split counts changed")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required for matched checkpoint scoring")
    repeat_ledger = json.loads((REPEAT / "ledger.json").read_text(encoding="utf-8"))
    if repeat_ledger["status"] != "completed" or [r["seed"] for r in repeat_ledger["runs"]] != [17, 31]:
        raise ValueError("Repeat round incomplete")
    dev = trial.windows(development, 510)
    device = torch.device("cuda")
    tokenizer = AutoTokenizer.from_pretrained(trial.MODEL_ID)
    backbone = AutoModel.from_pretrained(trial.MODEL_ID).to(device).eval()
    backbone.requires_grad_(False)
    trial.configure_head = lambda arch, dimension, target: CompetitorGapSegmenter(
        dimension, "global_context").to(target) if arch == "samlike" else None
    fixed = {"train_sha256": trial.sha(protected.DATA / "train.jsonl"),
             "dev_sha256": trial.sha(protected.DATA / "development.jsonl"),
             "aux_sha256": trial.sha(protected.DATA / "auxiliary.jsonl"),
             "data_manifest_sha256": trial.sha(protected.DATA / "manifest.json")}
    runs = ((7, SCREEN, SCREEN_CONFIG), (17, REPEAT / "global_context-seed17", REPEAT_CONFIG),
            (31, REPEAT / "global_context-seed31", REPEAT_CONFIG))
    rows = []
    for seed, folder, config in runs:
        row = score_one(backbone, tokenizer, device, folder, dev,
                        {**fixed, "config_sha256": trial.sha(config)})
        if row["seed"] != seed:
            raise ValueError("Seed/manifest mismatch")
        rows.append(row)
    payload = {"schema_version": "1.0.0", "status": "protected_development_only",
               "method": "Fmax over exact score ties on known 0/1 residues of APS-selected checkpoints",
               "data_manifest_sha256": fixed["data_manifest_sha256"], "runs": rows,
               "claim_status": "does_not_reverse_preregistered_proxy_guardrail_failure"}
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "completed", "fmax_by_seed": {row["seed"]: row["fmax"] for row in rows}}))


if __name__ == "__main__":
    main()
