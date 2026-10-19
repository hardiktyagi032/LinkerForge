"""Bounded head fitting on frozen caches; no encoder downloads or blind data."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import random
import time

import torch

from linkerforge.generation.contracts import canonical_hash, strict_dataclass
from linkerforge.generation.data import file_sha256, load_json
from linkerforge.generation.engine import TrainConfig, environment, write_json
from .data import collate, preflight
from .model import SiteModel, SiteModelConfig, TASKS


def source_hashes():
    here = Path(__file__).parent
    sources = list(here.glob("*.py")) + [here.parent / "generation" / f for f in ("contracts.py", "data.py", "engine.py")]
    return {p.relative_to(here.parent).as_posix(): file_sha256(p) for p in sorted(sources)}


@dataclass(frozen=True)
class SiteTrainConfig(TrainConfig):
    model: SiteModelConfig

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["model"] = SiteModelConfig.from_dict(value["model"])
        return strict_dataclass(cls, value)


@torch.no_grad()
def validate(model, rows, embeddings, batch_size, device):
    prior = model.training
    model.eval()
    loss_sum, known, bce = 0., 0, 0.
    try:
        for start in range(0, len(rows), batch_size):
            subset = rows[start:start+batch_size]
            result = model.loss(*collate(subset, embeddings, device))
            loss_sum += float(result["loss"]) * len(subset)
            known += int(result["known_sites"])
            bce += float(result["bce_sum"])
    finally:
        model.train(prior)
    return {"records": len(rows), "known_sites": known, "bce_sum": bce,
            "record_mean_bce": loss_sum / len(rows), "known_site_mean_bce": bce / known}


def train(manifest, config, output, synthetic=False, device="cpu", resume=None, execution=None, stop_after=None):
    data = preflight(manifest, synthetic)
    if config.model.embedding_dim != data["manifest"]["encoder"]["embedding_dim"]:
        raise ValueError("Model and frozen encoder feature dimensions differ")
    if synthetic:
        if device != "cpu" or config.max_steps > 8 or config.model.hidden_size > 64 or config.model.embedding_dim > 64:
            raise ValueError("Synthetic software fitting is CPU-only, <=8 updates and <=64 feature/hidden dimensions")
    else:
        receipt = load_json(execution) if execution else {}
        if not (receipt.get("approved") is True and receipt.get("institution") and receipt.get("review_reference")
                and receipt.get("host") == platform.node() and receipt.get("environment") == environment()
                and receipt.get("config_sha256") == canonical_hash(asdict(config)) and receipt.get("input_hashes") == data["input_hashes"]):
            raise ValueError("Reviewed execution receipt binding actual host/environment/config/inputs required")
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    identity = json.loads(json.dumps({"config": asdict(config), "input_hashes": data["input_hashes"],
                "source_hashes": source_hashes(), "encoder": data["manifest"]["encoder"],
                "supported_tasks": data["supported_tasks"], "synthetic_software_fixture": synthetic,
                "environment": environment(), "device": device, "counts": data["counts"]}))
    job = {**identity, "pid": os.getpid(), "status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
           "resume": str(resume) if resume else None, "execution_receipt_sha256": file_sha256(execution) if execution else None}
    write_json(out / "run.json", job)
    step, history, checkpoint = 0, [], None
    observed = {task: [] for task in TASKS}
    try:
        torch.set_num_threads(config.cpu_threads)
        torch.use_deterministic_algorithms(True)
        torch.manual_seed(config.seed)
        random.seed(config.seed)
        model = SiteModel(config.model).to(device)
        if resume:
            model, previous = SiteModel.load(resume, device)
            if previous["identity"] != identity:
                raise ValueError("Resume requires identical model/config/inputs/source/environment/device")
            observed = previous["observed_training_labels"]
        optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)
        if resume:
            previous = load_json(Path(resume) / "training.json")
            if previous["identity"] != identity or file_sha256(Path(resume) / "optimizer.pt") != previous["optimizer_sha256"] or file_sha256(Path(resume) / "model.json") != previous["model_metadata_sha256"]:
                raise ValueError("Resume state or identity changed")
            state = torch.load(Path(resume) / "optimizer.pt", weights_only=True, map_location="cpu")
            optimizer.load_state_dict(state["optimizer"])
            torch.set_rng_state(state["cpu_rng"])
            random.setstate(state["python_rng"])
            if state["cuda_rng"] is not None:
                torch.cuda.set_rng_state(state["cuda_rng"], device)
            step, history = previous["step"], previous["history"]
        rows = data["records"]["train"]
        batches = math.ceil(len(rows) / config.batch_size)
        model.train()
        while step < config.max_steps:
            if time.monotonic() - started >= config.max_wall_seconds:
                raise TimeoutError("Reviewed wall-clock ceiling reached; retain failure, do not retry automatically")
            epoch, batch = divmod(step, batches)
            order = torch.randperm(len(rows), generator=torch.Generator().manual_seed(config.seed + epoch)).tolist()
            chosen = [rows[i] for i in order[batch * config.batch_size:(batch+1)*config.batch_size]]
            optimizer.zero_grad(set_to_none=True)
            result = model.loss(*collate(chosen, data["embeddings"], device))
            if not torch.isfinite(result["loss"]):
                raise FloatingPointError("Nonfinite site loss")
            result["loss"].backward()
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), config.gradient_clip, error_if_nonfinite=True)
            optimizer.step()
            for row in chosen:
                observed[row.task] = sorted(set(observed[row.task]) | {y for y in row.labels if y != -1})
            step += 1
            entry = {"step": step, "epoch": epoch, "record_ids": [r.record_id for r in chosen],
                     "record_mean_bce": float(result["loss"].detach()), "known_sites": int(result["known_sites"]),
                     "bce_sum": float(result["bce_sum"].detach()), "gradient_norm_before_clip": float(norm)}
            history.append(entry)
            if step % config.checkpoint_every == 0 or step == config.max_steps or step == stop_after:
                entry["development"] = validate(model, data["records"]["development"], data["embeddings"], config.batch_size, device)
                checkpoint = out / f"step-{step:06d}"
                model.save(checkpoint, {"identity": identity, "completed_steps": step,
                           "observed_training_labels": observed,
                           "trained_tasks": [task for task, values in observed.items() if values == [0, 1]]})
                torch.save({"optimizer": optimizer.state_dict(), "cpu_rng": torch.get_rng_state(), "python_rng": random.getstate(),
                            "cuda_rng": torch.cuda.get_rng_state(device) if torch.device(device).type == "cuda" else None}, checkpoint / "optimizer.pt")
                write_json(checkpoint / "training.json", {"identity": identity, "step": step, "history": history,
                    "optimizer_sha256": file_sha256(checkpoint / "optimizer.pt"), "model_metadata_sha256": file_sha256(checkpoint / "model.json")})
                write_json(out / "history.json", history)
            if step == stop_after:
                break
        job.update(status="completed" if step == config.max_steps else "interrupted_for_software_test", completed_steps=step,
                   checkpoint=str(checkpoint.resolve()), measured_wall_seconds=time.monotonic()-started,
                   trainable_parameters=sum(p.numel() for p in model.parameters()), scientific_performance=None)
        write_json(out / "run.json", job)
        return job
    except Exception as error:
        job.update(status="failed", completed_steps=step, error_type=type(error).__name__, error=str(error), measured_wall_seconds=time.monotonic()-started)
        write_json(out / "run.json", job)
        raise


@torch.no_grad()
def score_domain(model, seq, embeddings, training):
    from .data import sequence_sha256
    from .model import allowed_positions
    if embeddings.shape != (len(seq), model.config.embedding_dim):
        raise ValueError("Wrong residue alignment")
    prior = model.training
    model.eval()
    try:
        logits = model(embeddings[None].to(next(model.parameters()).device))[0].cpu()
    finally:
        model.train(prior)
    supported = training["trained_tasks"]
    return {"sequence_sha256": sequence_sha256(seq), "length": len(seq),
            "synthetic_software_fixture": training["identity"]["synthetic_software_fixture"],
            "tasks": {task: {"status": "scored_uncalibrated" if task in supported else "untrained_no_score",
                              "sites": [{"residue_position": i, "insertion_after_residue": i if task == "internal_insertion" else None,
                                         "logit": float(logits[i-1, index]) if task in supported else None}
                                        for i in allowed_positions(task, len(seq))]} for index, task in enumerate(TASKS)},
            "interpretation": "Operation-specific uncalibrated score; not a fusion-success or insertion-function probability."}
