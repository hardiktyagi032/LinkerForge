"""One-time frozen public-benchmark comparison; never selects checkpoints here.

CAID3 common-27 and TransDFL TE64 are already-viewed diagnostic references,
not a fresh blind test. Checkpoints were selected on TE82 only.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import torch
from sklearn.metrics import average_precision_score, roc_auc_score, precision_recall_curve
from transformers import AutoModel, AutoTokenizer

from audit_caid3_dld_overlap import caid_records
from compare_dfl_caid3_common import competitor_scores
from train_dfl_masked_cnn import MODEL_ID, ResidueHead, load
from train_dfl_masked_span import SpanHead
from linkerforge.models.promptable_linker_segmenter import PromptableLinkerSegmenter
from linkerforge.models.yolo1d_linker_segmenter import Yolo1DLinkerSegmenter


ROOT = Path(__file__).resolve().parents[1]
CAID = ROOT / "artifacts/caid3-common-coverage-001/linker-common.fasta"
COMPETITORS = ROOT / "artifacts/caid3-common-coverage-001/predictions"
TE64 = ROOT / "data/processed/published_dfl_splits/te64.jsonl"
OUTPUT = ROOT / "reports/dfl_yolo_sam_public_retrospective_2026-10-13.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(truth, scores):
    truth = np.asarray(truth, dtype=np.uint8)
    scores = np.asarray(scores, dtype=np.float64)
    if len(truth) != len(scores) or not np.isfinite(scores).all() or len(np.unique(truth)) != 2:
        raise ValueError("Invalid truth/scores or a single-class benchmark")
    precision, recall, _ = precision_recall_curve(truth, scores)
    f1 = np.divide(2 * precision * recall, precision + recall,
                   out=np.zeros_like(precision), where=precision + recall > 0)
    return {"scored_residues": int(len(truth)), "positive_residues": int(truth.sum()),
            "aps": float(average_precision_score(truth, scores)),
            "auroc": float(roc_auc_score(truth, scores)), "fmax": float(f1.max())}


@torch.no_grad()
def embed_records(backbone, tokenizer, records, device):
    result = {}
    for name, sequence, _ in records:
        fragments = []
        for offset in range(0, len(sequence), 510):
            peptide = sequence[offset:offset + 510]
            tokens = tokenizer(peptide, return_tensors="pt", add_special_tokens=True,
                               truncation=False)
            tokens = {key: value.to(device) for key, value in tokens.items()}
            hidden = backbone(**tokens).last_hidden_state[:, 1:1 + len(peptide)].cpu()
            if hidden.shape[1] != len(peptide):
                raise ValueError(f"Embedding length mismatch for {name}")
            fragments.append(hidden)
        result[name] = fragments
    return result


def checkpoints():
    fixed = [
        ("LinkerForge_CNN_seed7", "dfl-cnn-seed7-001", "cnn"),
        ("LinkerForge_span_seed7", "dfl-span-seed7-001", "span"),
        ("LinkerForge_precision_seed7", "dfl-precision-seed7-001", "cnn"),
    ]
    for seed in (7, 17, 31):
        fixed.extend([
            (f"SAMlike_seed{seed}", f"samlike-dfl-seed{seed}-001", "sam"),
            (f"YOLO1D_w128_seed{seed}", f"yolo1d-dfl-padmask-seed{seed}-001", "yolo"),
            (f"YOLO1D_w256_seed{seed}", f"yolo1d-dfl-w256-seed{seed}-001", "yolo"),
        ])
    return fixed


def head_from_checkpoint(kind, state, embedding_dim, device):
    if kind == "cnn":
        head = ResidueHead(embedding_dim)
    elif kind == "span":
        head = SpanHead(embedding_dim)
    elif kind == "sam":
        head = PromptableLinkerSegmenter(embedding_dim)
    elif kind == "yolo":
        width = state.get("width")
        prototypes = state.get("prototypes")
        if width is None:
            # Earlier padding-safe run predates explicit architecture fields.
            width = state["head"]["stem.weight"].shape[0]
            prototypes = state["head"]["prototype_head.weight"].shape[0]
        head = Yolo1DLinkerSegmenter(embedding_dim, width=width, prototypes=prototypes)
    else:
        raise ValueError(kind)
    head.load_state_dict(state["head"], strict=True)
    return head.to(device).eval()


@torch.no_grad()
def scores_for(head, kind, fragments, device):
    scores = []
    for fragment in fragments:
        hidden = fragment.to(device)
        if kind == "cnn":
            logits = head(hidden)
        elif kind == "span":
            logits = head(hidden)[:, :, 0]
        elif kind == "sam":
            valid = torch.ones(hidden.shape[:2], dtype=torch.bool, device=device)
            concept = torch.zeros(hidden.shape[0], dtype=torch.long, device=device)
            logits = head(hidden, valid, concept)["semantic_logits"]
        else:
            valid = torch.ones(hidden.shape[:2], dtype=torch.bool, device=device)
            logits = head(hidden, valid)["semantic_logits"][:, :, 0]
        scores.extend(logits.sigmoid()[0].cpu().tolist())
    return scores


def main():
    if OUTPUT.exists():
        raise FileExistsError("Frozen public comparison output already exists")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable")
    caid = caid_records(CAID)
    te64_rows = load(TE64)
    te64 = [(row["protein_id"], row["sequence"], row["labels"]) for row in te64_rows]
    if (len(caid) != 27 or sum(labels.count("1") for _, _, labels in caid) != 1214
            or len(te64) != 64 or sum(labels.count("1") for _, _, labels in te64) != 949):
        raise ValueError("Published benchmark reference changed")
    competitor_paths = sorted(COMPETITORS.glob("*.caid"))
    if len(competitor_paths) != 7:
        raise ValueError("Seven released CAID3 predictors required")
    caid_truth = [label == "1" for _, _, labels in caid for label in labels]
    released = {}
    for path in competitor_paths:
        by_id = competitor_scores(path, caid)
        released[path.stem] = metrics(caid_truth,
            [score for name, _, _ in caid for score in by_id[name]])
    # Reproduce the already archived common-target reference as a guard.
    prior = json.loads((ROOT / "reports/dfl_caid3_common_retrospective_2026-10-12.json").read_text())
    for name, result in released.items():
        if abs(result["aps"] - prior["results"][name]["aps"]) > 1e-9:
            raise ValueError(f"Released baseline evaluation drifted: {name}")
    device = torch.device("cuda")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    backbone = AutoModel.from_pretrained(MODEL_ID).to(device).eval()
    backbone.requires_grad_(False)
    embedded_records = ([(f"caid3:{name}", sequence, labels) for name, sequence, labels in caid]
                        + [(f"te64:{name}", sequence, labels) for name, sequence, labels in te64])
    if len({name for name, _, _ in embedded_records}) != 91:
        raise ValueError("Duplicate identifiers within a benchmark source")
    embeddings = embed_records(backbone, tokenizer, embedded_records, device)
    results_caid, results_te64, hashes = {}, {}, {}
    for label, dirname, kind in checkpoints():
        path = ROOT / "artifacts" / dirname / "best.pt"
        manifest_path = path.parent / "manifest.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest["status"] != "completed":
                raise ValueError(f"Unfinished trial: {label}")
        state = torch.load(path, map_location="cpu", weights_only=False)
        if state["model_id"] != MODEL_ID:
            raise ValueError(f"Backbone mismatch: {label}")
        head = head_from_checkpoint(kind, state, backbone.config.hidden_size, device)
        by_id = {name: scores_for(head, kind, embeddings[name], device)
                 for name, _, _ in embedded_records}
        if any(len(by_id[name]) != len(sequence) for name, sequence, _ in embedded_records):
            raise ValueError(f"Output coverage mismatch: {label}")
        results_caid[label] = metrics(caid_truth,
            [score for name, _, _ in caid for score in by_id[f"caid3:{name}"]])
        te64_truth, te64_scores = [], []
        for name, sequence, annotations in te64:
            for annotation, score in zip(annotations, by_id[f"te64:{name}"]):
                if annotation != "x":
                    te64_truth.append(annotation == "1")
                    te64_scores.append(score)
        results_te64[label] = metrics(te64_truth, te64_scores)
        hashes[label] = sha(path)
        print(json.dumps({"model": label, "caid3": results_caid[label],
                          "te64": results_te64[label]}), flush=True)
        del head
    report = {
        "schema_version": "0.1.0",
        "status": "public_retrospective_not_independent_or_model_selection",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "benchmarks": {
            "caid3_common_27": {"reference_proteins": 27, "released_submissions": released,
                                "local_frozen_checkpoints": results_caid},
            "transdfl_te64": {"reference_proteins": 64,
                               "local_frozen_checkpoints": results_te64,
                               "released_baseline_inference": "not_reproduced"},
        },
        "provenance": {
            "input_sha256": {"caid3_common_fasta": sha(CAID), "te64_jsonl": sha(TE64)},
            "released_score_sha256": {p.name: sha(p) for p in competitor_paths},
            "checkpoint_sha256": hashes,
            "script_sha256": sha(Path(__file__)),
            "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "versions": {"python": sys.version.split()[0], "torch": torch.__version__,
                         "transformers": __import__("transformers").__version__},
        },
        "limitations": [
            "CAID3 and TE64 are public, previously viewed retrospective diagnostics, not fresh blind tests.",
            "All local checkpoints were selected on TE82 before this comparison; never reselect on CAID3 or TE64.",
            "TR166 versus CAID3/TE64 remote homology and source overlap are not certified absent.",
            "CAID3 common 27 includes only linker-positive proteins, so no-linker specificity cannot be measured.",
            "Released CAID3 scores represent historical models with different training data and some different input modalities; this is a same-target deployed-score comparison, not equal-training-data efficiency.",
            "Original TransDFL inference was not reproduced on TE64; only local models are compared there.",
            "Per-residue metrics do not validate predicted span boundaries or biological function.",
        ],
    }
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
