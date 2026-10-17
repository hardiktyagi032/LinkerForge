"""Standalone CUDA-only detector training from bounded JSONL streams.

Input records need sequence, residue labels (0/1/2), domain_tokens (0..3),
homology_cluster_id, and split. This script does not create labels or data.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

try:
    import torch
except ImportError as exc:
    raise SystemExit("PyTorch with CUDA is required; install and test it on the GPU host") from exc

from linkerforge.data.streaming import prefetch_one_batch
from linkerforge.models.linker_detector_gpu import AA_TO_ID, LinkerDetector, detector_loss
from preflight_detector_data import preflight


def records_from(source: str):
    """Stream one source each epoch; no raw local cache is created."""
    if source.startswith(("https://", "http://")):
        handle = urlopen(Request(source, headers={"User-Agent": "LinkerForge-detector/0.1"}), timeout=60)
    else:
        handle = open(source, "rb")
    try:
        stream = gzip.GzipFile(fileobj=handle) if source.endswith(".gz") else handle
        for line in stream:
            if line.strip():
                yield json.loads(line)
    finally:
        handle.close()


def batches(source: str, split: str, batch_size: int):
    group = []
    for record in records_from(source):
        if record.get("split") != split:
            raise ValueError(f"Unexpected split in {source}: {record.get('split')}")
        if not record.get("homology_cluster_id"):
            raise ValueError("Missing homology cluster ID")
        sequence = record["sequence"].upper()
        labels = record["labels"]
        domains = record["domain_tokens"]
        if not (len(sequence) == len(labels) == len(domains) and sequence):
            raise ValueError(f"Misaligned residue annotations for {record.get('source_id')}")
        if any(label not in (0, 1, 2) for label in labels):
            raise ValueError("Labels must be 0=none, 1=IDL, 2=DDL")
        if any(token not in (0, 1, 2, 3) for token in domains):
            raise ValueError("Domain tokens must be 0..3")
        group.append((sequence, labels, domains))
        if len(group) == batch_size:
            yield group
            group = []
    if group:
        yield group


def encode(group, device):
    length = max(len(row[0]) for row in group)
    size = len(group)
    amino = torch.zeros((size, length), dtype=torch.long)
    domain = torch.zeros((size, length), dtype=torch.long)
    labels = torch.full((size, length), -100, dtype=torch.long)
    starts = torch.zeros((size, length), dtype=torch.float32)
    ends = torch.zeros((size, length), dtype=torch.float32)
    valid = torch.zeros((size, length), dtype=torch.bool)
    for row, (sequence, region_labels, domain_tokens) in enumerate(group):
        n = len(sequence)
        amino[row, :n] = torch.tensor([AA_TO_ID.get(aa, AA_TO_ID["X"]) for aa in sequence])
        domain[row, :n] = torch.tensor(domain_tokens)
        labels[row, :n] = torch.tensor(region_labels)
        valid[row, :n] = True
        for i, label in enumerate(region_labels):
            if label == 0:
                continue
            if i == 0 or region_labels[i - 1] != label:
                starts[row, i] = 1
            if i == n - 1 or region_labels[i + 1] != label:
                ends[row, i] = 1
    return tuple(x.to(device, non_blocking=True) for x in (amino, domain, labels, starts, ends, valid))


def save_checkpoint(state, directory: Path, fallback: Path | None) -> Path:
    """Retry sharing locks; WinError 5 uses only an explicit fallback path."""
    for target in (directory, fallback):
        if target is None:
            continue
        try:
            target.mkdir(parents=True, exist_ok=True)
            final = target / "latest.pt"
            temporary = target / f"latest.{uuid4().hex}.tmp"
            torch.save(state, temporary)
            for attempt in range(5):
                try:
                    os.replace(temporary, final)
                    return final
                except OSError as exc:
                    if getattr(exc, "winerror", None) not in (32, 33) or attempt == 4:
                        raise
                    time.sleep(0.25 * 2**attempt)
        except PermissionError:
            if target == fallback or fallback is None:
                raise
        finally:
            if "temporary" in locals() and temporary.exists():
                temporary.unlink(missing_ok=True)
    raise RuntimeError("Checkpoint could not be saved")


@torch.no_grad()
def validate(model, source: str, batch_size: int, device):
    model.eval()
    tp = fp = fn = tn_none = fp_none = 0
    evaluated = 0
    for group in prefetch_one_batch(batches(source, "validation", batch_size)):
        evaluated += len(group)
        amino, domain, labels, _, _, valid = encode(group, device)
        output = model(amino, domain, valid)
        prediction = output["residue_logits"].argmax(dim=-1)
        truth = (labels > 0) & valid
        predicted = (prediction > 0) & valid
        tp += (truth & predicted).sum().item()
        fp += ((~truth) & predicted & valid).sum().item()
        fn += (truth & (~predicted)).sum().item()
        none_truth = ~truth.any(dim=1)
        none_prediction = torch.sigmoid(output["presence_logit"]) < 0.5
        tn_none += (none_truth & none_prediction).sum().item()
        fp_none += (none_truth & (~none_prediction)).sum().item()
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    if not evaluated:
        raise RuntimeError("Validation stream is empty")
    return {"precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "no_linker_specificity": tn_none / (tn_none + fp_none) if tn_none + fp_none else None,
            "positive_residues": tp + fn, "evaluated_proteins": evaluated}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", required=True, help="Local path or HTTPS JSONL(.gz) stream")
    parser.add_argument("--validation", required=True)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--fallback-checkpoint-dir", type=Path)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=0.0003)
    parser.add_argument("--checkpoint-every", type=int, default=500)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("CUDA GPU unavailable: refusing CPU training")
    if args.epochs < 1 or args.batch_size < 1 or args.checkpoint_every < 1:
        raise ValueError("Epochs, batch size, and checkpoint interval must be positive")
    preflight_report = preflight(args.train, args.validation)
    print(json.dumps({"event": "preflight", "report": preflight_report}), flush=True)
    device = torch.device("cuda")
    torch.manual_seed(7)
    model = LinkerDetector().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    first_epoch = global_step = resume_batch = 0
    if args.resume:
        state = torch.load(args.resume, map_location=device, weights_only=False)
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        first_epoch = state["epoch"]
        global_step = state["global_step"]
        resume_batch = state["batch_index"]
    for epoch in range(first_epoch, args.epochs):
        model.train()
        losses = []
        for index, group in enumerate(prefetch_one_batch(batches(args.train, "train", args.batch_size))):
            if epoch == first_epoch and index < resume_batch:
                continue
            amino, domain, labels, starts, ends, valid = encode(group, device)
            optimizer.zero_grad(set_to_none=True)
            output = model(amino, domain, valid)
            loss = detector_loss(output, labels, starts, ends, valid)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            losses.append(loss.item())
            global_step += 1
            if global_step % args.checkpoint_every == 0:
                save_checkpoint({"model": model.state_dict(), "optimizer": optimizer.state_dict(),
                                 "epoch": epoch, "batch_index": index + 1,
                                 "global_step": global_step, "config": vars(args)},
                                args.checkpoint_dir, args.fallback_checkpoint_dir)
        if not losses:
            raise RuntimeError("No training batches were consumed; check source and resume position")
        metrics = validate(model, args.validation, args.batch_size, device)
        save_checkpoint({"model": model.state_dict(), "optimizer": optimizer.state_dict(),
                         "epoch": epoch + 1, "batch_index": 0,
                         "global_step": global_step, "config": vars(args),
                         "validation": metrics},
                        args.checkpoint_dir, args.fallback_checkpoint_dir)
        print(json.dumps({"epoch": epoch + 1, "global_step": global_step,
                          "train_loss": sum(losses) / len(losses), "validation": metrics}), flush=True)
        resume_batch = 0


if __name__ == "__main__":
    main()
