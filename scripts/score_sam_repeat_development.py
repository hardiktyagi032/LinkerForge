"""Checkpoint-only Fmax on the frozen protected development split; no CAID3 read."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np
import torch
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score
from transformers import AutoModel, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from linkerforge.models.sam_linker_variants import SAMLinkerVariant
from preflight_caid3_protected_training import verify
from run_dfl_disorder_transfer import configure_head, sha, target_batch
from train_dfl_masked_cnn import embed_group, windows

DATA = ROOT / "data/processed/caid3_protected_dfl_v1"
IDEAS = ROOT / "artifacts/dfl-sam-ideas-batch-2026-10-17"
REPEATS = ROOT / "artifacts/dfl-sam-repeat-2026-10-17"
BASELINES = ROOT / "artifacts/dfl-caid3-protected-baselines-2026-10-16"
OUTPUT = ROOT / "reports/dfl_sam_repeat_development_scores_2026-10-17.json"
MODEL_ID = "facebook/esm2_t12_35M_UR50D"


def runs():
    for seed in (7, 17, 31):
        yield "baseline", seed, BASELINES / f"samlike-disorder_transfer-seed{seed}"
    for variant in ("multiscale_features", "boundary_plus_query"):
        yield variant, 7, IDEAS / variant
        for seed in (17, 31):
            yield variant, seed, REPEATS / f"{variant}-seed{seed}"


@torch.no_grad()
def score(head, backbone, tokenizer, examples, device):
    truth, scores = [], []
    head.eval()
    for offset in range(0, len(examples), 2):
        group = examples[offset:offset + 2]
        hidden, _, _ = embed_group(backbone, tokenizer, group, device)
        valid, labels, _, _, _, concept = target_batch(group, device)
        logits = head(hidden, valid, concept)["semantic_logits"].sigmoid()
        known = valid & (labels >= 0)
        truth.extend(labels[known].cpu().numpy().astype(int).tolist())
        scores.extend(logits[known].cpu().numpy().tolist())
    truth = np.asarray(truth, dtype=np.uint8)
    scores = np.asarray(scores, dtype=np.float64)
    precision, recall, _ = precision_recall_curve(truth, scores)
    f1 = np.divide(2 * precision * recall, precision + recall,
                   out=np.zeros_like(precision), where=precision + recall > 0)
    return {"aps": float(average_precision_score(truth, scores)),
            "auroc": float(roc_auc_score(truth, scores)), "fmax": float(f1.max()),
            "known_residues": int(len(truth)), "positive_residues": int(truth.sum())}


def main():
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    if verify(DATA / "manifest.json")["status"] != "pass_under_declared_sequence_screen":
        raise ValueError("Protected-data gate failed")
    planned = list(runs())
    for variant, seed, folder in planned:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        if manifest["status"] != "completed" or manifest["seed"] != seed:
            raise ValueError(f"Incomplete run: {folder}")
        if variant != "baseline" and manifest["variant"] != variant:
            raise ValueError(f"Variant mismatch: {folder}")
        if manifest["dev_sha256"] != sha(DATA / "development.jsonl"):
            raise ValueError(f"Development hash mismatch: {folder}")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable")
    rows = [json.loads(line) for line in (DATA / "development.jsonl").read_text(encoding="utf-8").splitlines()]
    examples = windows(rows, 510)
    device = torch.device("cuda")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    backbone = AutoModel.from_pretrained(MODEL_ID).to(device).eval()
    backbone.requires_grad_(False)
    results = []
    for variant, seed, folder in planned:
        head = (configure_head("samlike", backbone.config.hidden_size, device) if variant == "baseline"
                else SAMLinkerVariant(backbone.config.hidden_size, variant).to(device))
        checkpoint = folder / "best.pt"
        payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
        head.load_state_dict(payload["head"])
        values = score(head, backbone, tokenizer, examples, device)
        recorded = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["best_development"]
        if abs(values["aps"] - recorded["masked_residue_aps"]) > 1e-5:
            raise ValueError(f"Checkpoint APS mismatch for {folder}: {values['aps']} vs {recorded['masked_residue_aps']}")
        results.append({"variant": variant, "seed": seed, "checkpoint": str(checkpoint.relative_to(ROOT)),
                        "checkpoint_sha256": sha(checkpoint), "metrics": values})
        print(json.dumps(results[-1]), flush=True)
        del head
    OUTPUT.write_text(json.dumps({"schema_version": "1.0.0", "created_utc": datetime.now(timezone.utc).isoformat(),
                                  "claim_status": "protected_development_only", "data_manifest_sha256": sha(DATA / "manifest.json"),
                                  "script_sha256": sha(Path(__file__)), "results": results}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
