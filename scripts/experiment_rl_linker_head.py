"""Exploratory RL fine-tuning of an ESM-2 linker head with a matched control.

Only DLD train is used for updates; validation chooses/report metrics. This
never opens the blind shard and cannot establish a held-out gain. The RL arm
uses self-critical REINFORCE on sampled residue masks with F0.5 reward; the
control continues supervised BCE from the identical frozen base checkpoint.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import average_precision_score, roc_auc_score
from torch import nn
from torch.nn import functional as F
from transformers import AutoModel, AutoTokenizer, __version__ as transformers_version

from evaluate_esm2_linker_blind import scores_for, select_thresholds
from preflight_detector_data import preflight
from train_esm2_linker_detector import (ResidueHead, atomic_checkpoint,
                                        batch_embedding, file_hash, make_windows,
                                        read_records)


@torch.no_grad()
def f05_reward(actions: torch.Tensor, targets: torch.Tensor,
               mask: torch.Tensor) -> torch.Tensor:
    """Non-differentiable per-window reward; penalize false calls on negatives."""
    positive = targets.bool() & mask
    selected = actions.bool() & mask
    tp = (selected & positive).sum(dim=1).float()
    fp = (selected & ~positive).sum(dim=1).float()
    fn = (~selected & positive).sum(dim=1).float()
    f05 = 1.25 * tp / (1.25 * tp + 0.25 * fn + fp).clamp_min(1)
    no_positive = positive.sum(dim=1) == 0
    negative_reward = -fp / (fp + 5)
    return torch.where(no_positive, negative_reward, f05)


def policy_loss(logits: torch.Tensor, targets: torch.Tensor,
                mask: torch.Tensor) -> torch.Tensor:
    distribution = torch.distributions.Bernoulli(logits=logits)
    sampled = distribution.sample()
    greedy = (logits >= 0).float()
    advantage = f05_reward(sampled, targets, mask) - f05_reward(greedy, targets, mask)
    mean_log_probability = (distribution.log_prob(sampled) * mask).sum(dim=1) / mask.sum(dim=1)
    return -(advantage.detach() * mean_log_probability).mean()


@torch.no_grad()
def validate(backbone, tokenizer, head, records, batch_size, device) -> dict:
    truth, scores, protein_truth, protein_max = scores_for(
        backbone, tokenizer, head, records, batch_size, device)
    chosen = select_thresholds(truth, scores, protein_truth, protein_max, 0.90)
    return {
        "residue_auprc": float(average_precision_score(truth, scores)),
        "residue_auroc": float(roc_auc_score(truth, scores)),
        "positive_residues": int(truth.sum()),
        "residues": int(len(truth)),
        "f1_selected": chosen["f1_selected"],
        "precision_90_candidate": chosen["high_precision"],
        "precision_90_status": chosen["high_precision_status"],
    }


def train_arm(mode: str, backbone: nn.Module, tokenizer, base_state: dict,
              train_windows: list, validation_records: list, args, device) -> tuple[dict, dict]:
    torch.manual_seed(args.seed)
    random.seed(args.seed)
    head = ResidueHead(backbone.config.hidden_size).to(device)
    head.load_state_dict(copy.deepcopy(base_state))
    optimizer = torch.optim.AdamW(head.parameters(), lr=args.learning_rate)
    history = []
    for epoch in range(args.epochs):
        head.train()
        order = list(range(len(train_windows)))
        random.Random(args.seed + epoch).shuffle(order)
        losses = []
        for offset in range(0, len(order), args.batch_size):
            group = [train_windows[index] for index in order[offset:offset + args.batch_size]]
            embeddings, targets, mask = batch_embedding(backbone, tokenizer, group, device)
            logits = head(embeddings)
            supervised_loss = F.binary_cross_entropy_with_logits(
                logits[mask], targets[mask],
                pos_weight=torch.tensor(args.positive_weight, device=device))
            loss = supervised_loss
            if mode == "hybrid_rl":
                loss = loss + args.rl_weight * policy_loss(logits, targets, mask)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
            optimizer.step()
            losses.append(float(loss.item()))
        head.eval()
        metrics = validate(backbone, tokenizer, head, validation_records,
                           args.batch_size, device)
        history.append({"epoch": epoch + 1, "training_loss": sum(losses) / len(losses),
                        "validation": metrics})
        print(json.dumps({"arm": mode, **history[-1]}), flush=True)
    return {"history": history, "final_validation": history[-1]["validation"]}, {
        "head": head.state_dict(), "mode": mode, "base_checkpoint_sha256": file_hash(args.base_checkpoint),
        "model_id": args.model_id, "revision": args.revision,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    parser.add_argument("--base-checkpoint", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--positive-weight", type=float, default=6.0)
    parser.add_argument("--rl-weight", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required")
    if args.epochs < 1 or args.batch_size < 1 or args.rl_weight <= 0:
        raise ValueError("Invalid training settings")
    preflight(str(args.train), str(args.validation))
    state = torch.load(args.base_checkpoint, map_location="cpu", weights_only=False)
    args.model_id, args.revision = state["model_id"], state["revision"]
    tokenizer = AutoTokenizer.from_pretrained(args.model_id, revision=args.revision, local_files_only=True)
    backbone = AutoModel.from_pretrained(args.model_id, revision=args.revision, local_files_only=True).to("cuda").eval()
    backbone.requires_grad_(False)
    train_windows = make_windows(read_records(args.train), 510)
    validation_records = read_records(args.validation)
    baseline_head = ResidueHead(backbone.config.hidden_size).to("cuda").eval()
    baseline_head.load_state_dict(state["head"])
    baseline = validate(backbone, tokenizer, baseline_head, validation_records,
                        args.batch_size, "cuda")
    root = Path(__file__).resolve().parents[1]
    config = {key: value for key, value in vars(args).items() if key not in ("train", "validation", "base_checkpoint", "output_dir")}
    result = {
        "schema_version": "0.1.0", "status": "completed",
        "method": "self_critical_policy_gradient_vs_supervised_continuation",
        "data": {"train_sha256": file_hash(args.train), "validation_sha256": file_hash(args.validation),
                 "base_checkpoint_sha256": file_hash(args.base_checkpoint),
                 "train_windows": len(train_windows), "validation_proteins": len(validation_records)},
        "config": config, "results": {"frozen_base": baseline},
        "provenance": {"source_ids": ["DLD:train", "DLD:validation"],
                       "pipeline_commit": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
                       "script_sha256": file_hash(Path(__file__).resolve()),
                       "config_hash": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
                       "software": {"python": sys.version.split()[0], "torch": torch.__version__,
                                    "transformers": transformers_version},
                       "evidence_quality": "validation_only_exploratory"},
        "limitations": ["Validation was used to select the frozen base checkpoint; this is exploratory, not independent testing.",
                        "The original blind fold was already examined and is not used here.",
                        "A later fresh homology-audited test set is required to establish an RL performance gain.",
                        "REINFORCE may be higher variance than direct supervised optimization; equal-compute control is mandatory."],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for mode in ("supervised_control", "hybrid_rl"):
        arm, checkpoint = train_arm(mode, backbone, tokenizer, state["head"],
                                    train_windows, validation_records, args, "cuda")
        result["results"][mode] = arm
        atomic_checkpoint(checkpoint, args.output_dir / f"{mode}.pt")
    (args.output_dir / "report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output_dir / "report.json"),
                      "base_ap": baseline["residue_auprc"],
                      "control_ap": result["results"]["supervised_control"]["final_validation"]["residue_auprc"],
                      "rl_ap": result["results"]["hybrid_rl"]["final_validation"]["residue_auprc"]}), flush=True)


if __name__ == "__main__":
    main()
