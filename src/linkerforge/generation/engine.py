"""Bounded training, reproducible resume, and known-length development diagnostics."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from importlib import metadata
import math
import os
from pathlib import Path
import platform
import random
import time

import torch

from .baselines import edit_distance, template_baselines
from .constraints import generate
from .contracts import GeneratorConfig, canonical_hash, strict_dataclass
from .data import file_sha256, load_json, preflight
from .model import LinkerInfiller


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def environment():
    import safetensors
    optional = {}
    for package in ("transformers", "tokenizers", "numpy"):
        try:
            optional[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            optional[package] = None
    return {"python": platform.python_version(), "torch": torch.__version__,
            "safetensors": safetensors.__version__, "host": platform.node(),
            "platform": platform.platform(), "cuda": torch.version.cuda, **optional}


def source_hashes():
    return {p.name: file_sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))}


@dataclass(frozen=True)
class TrainConfig:
    model: GeneratorConfig
    max_steps: int = 1000
    batch_size: int = 8
    learning_rate: float = 0.0003
    weight_decay: float = 0.01
    gradient_clip: float = 1.0
    seed: int = 17
    checkpoint_every: int = 100
    cpu_threads: int = 2
    max_wall_seconds: int = 1800

    def __post_init__(self):
        for name in ("max_steps", "batch_size", "checkpoint_every", "cpu_threads", "max_wall_seconds"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")
        if type(self.seed) is not int or self.seed < 0:
            raise ValueError("seed must be a nonnegative integer")
        if not all(math.isfinite(x) for x in (self.learning_rate, self.weight_decay, self.gradient_clip)) or self.learning_rate <= 0 or self.weight_decay < 0 or self.gradient_clip <= 0:
            raise ValueError("Invalid optimizer settings")
        if self.max_wall_seconds > 21600:
            raise ValueError("One reviewed round is bounded to six hours")

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["model"] = GeneratorConfig.from_dict(value["model"])
        return strict_dataclass(cls, value)


@torch.no_grad()
def validation_nll(model, records, batch_size, device):
    was_training = model.training
    model.eval()
    nll, residues, query_mean_sum = 0., 0, 0.
    try:
        for offset in range(0, len(records), batch_size):
            chunk = records[offset:offset + batch_size]
            result = model(**model.tokenizer.batch(chunk, model.config, device))
            nll += float(result["target_nll_sum"])
            residues += int(result["target_residues"])
            query_mean_sum += float(result["loss"]) * len(chunk)
    finally:
        model.train(was_training)
    return {"records": len(records), "learnable_residues": residues, "nll_sum": nll,
            "residue_mean_nll": nll / residues, "record_mean_nll": query_mean_sum / len(records)}


def save_checkpoint(model, optimizer, path, state):
    model.save(path)
    path = Path(path)
    device = next(model.parameters()).device
    rng = {"cpu": torch.get_rng_state(), "cuda": torch.cuda.get_rng_state(device) if device.type == "cuda" else None,
           "python": random.getstate()}
    torch.save({"optimizer": optimizer.state_dict(), "rng": rng}, path / "optimizer.pt")
    write_json(path / "training.json", {**state, "optimizer_sha256": file_sha256(path / "optimizer.pt"),
                                        "model_metadata_sha256": file_sha256(path / "model.json")})


def train(manifest_path, config: TrainConfig, output, *, synthetic=False, device="cpu", resume=None, execution=None, stop_after=None):
    # Must fail on unavailable/unreviewed inputs before constructing/downloading any model.
    data = preflight(manifest_path, synthetic=synthetic)
    if synthetic:
        if (device != "cpu" or config.max_steps > 8 or config.model.backend != "native"
                or config.model.hidden_size > 64 or config.model.layers > 2 or config.model.max_positions > 256):
            raise ValueError("Synthetic smoke is CPU-only, native <=64 hidden/2 layers/256 positions and <=8 updates")
    else:
        receipt = load_json(execution) if execution else {}
        if not (receipt.get("approved") is True and receipt.get("institution") and receipt.get("review_reference")
                and receipt.get("host") == platform.node() and receipt.get("environment") == environment()
                and receipt.get("config_sha256") == canonical_hash(asdict(config))
                and receipt.get("input_hashes") == data["input_hashes"]):
            raise ValueError("Scientific training requires a reviewed execution receipt binding this host, environment, config and data")
    # Validate every serialized example, including learnable positions/window, before weights.
    from .tokenizer import FIMTokenizer
    tokenizer = FIMTokenizer(config.model.max_linker_length)
    for records in data["records"].values():
        for record in records:
            tokenizer.batch([record], config.model)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    identity = {"config": asdict(config), "config_sha256": canonical_hash(asdict(config)),
                "input_hashes": data["input_hashes"], "source_hashes": source_hashes(),
                "environment": environment(), "synthetic_software_fixture": synthetic,
                "device": device, "counts": data["counts"]}
    identity = json.loads(json.dumps(identity))
    job = {**identity, "pid": os.getpid(), "started_utc": datetime.now(timezone.utc).isoformat(),
           "status": "running", "resume": str(resume) if resume else None,
           "execution_receipt_sha256": file_sha256(execution) if execution else None}
    write_json(out / "run.json", job)
    torch.set_num_threads(config.cpu_threads)
    random.seed(config.seed)
    torch.manual_seed(config.seed)
    torch.use_deterministic_algorithms(True)
    history, step, last_checkpoint = [], 0, None
    try:
        model = LinkerInfiller.load(resume, device) if resume else LinkerInfiller(config.model).to(device)
        optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                                     lr=config.learning_rate, weight_decay=config.weight_decay)
        if resume:
            previous = load_json(Path(resume) / "training.json")
            if previous["identity"] != identity:
                raise ValueError("Resume requires identical config, inputs, source, environment, mode and device")
            if (file_sha256(Path(resume) / "optimizer.pt") != previous["optimizer_sha256"]
                    or file_sha256(Path(resume) / "model.json") != previous["model_metadata_sha256"]):
                raise ValueError("Resume state hash mismatch")
            state = torch.load(Path(resume) / "optimizer.pt", map_location="cpu", weights_only=True)
            optimizer.load_state_dict(state["optimizer"])
            torch.set_rng_state(state["rng"]["cpu"])
            if state["rng"]["cuda"] is not None:
                torch.cuda.set_rng_state(state["rng"]["cuda"], device)
            random.setstate(state["rng"]["python"])
            step, history = previous["step"], previous["history"]
        records = data["records"]["train"]
        batches_per_epoch = math.ceil(len(records) / config.batch_size)
        model.train()
        while step < config.max_steps:
            if time.monotonic() - started >= config.max_wall_seconds:
                raise TimeoutError("Reviewed wall-clock ceiling reached; no automatic retry")
            epoch, batch_index = divmod(step, batches_per_epoch)
            order = torch.randperm(len(records), generator=torch.Generator().manual_seed(config.seed + epoch)).tolist()
            selected = order[batch_index * config.batch_size:(batch_index + 1) * config.batch_size]
            optimizer.zero_grad(set_to_none=True)
            result = model(**model.tokenizer.batch([records[i] for i in selected], model.config, device))
            if not torch.isfinite(result["loss"]):
                raise FloatingPointError("Non-finite training loss")
            result["loss"].backward()
            norm = torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], config.gradient_clip, error_if_nonfinite=True)
            optimizer.step()
            step += 1
            entry = {"step": step, "epoch": epoch, "record_ids": [records[i].record_id for i in selected],
                     "record_mean_nll": float(result["loss"].detach()),
                     "nll_sum": float(result["target_nll_sum"].detach()), "learnable_residues": int(result["target_residues"]),
                     "gradient_norm_before_clip": float(norm)}
            history.append(entry)
            if step % config.checkpoint_every == 0 or step == config.max_steps or step == stop_after:
                entry["development"] = validation_nll(model, data["records"]["development"], config.batch_size, device)
                last_checkpoint = out / f"step-{step:06d}"
                save_checkpoint(model, optimizer, last_checkpoint, {"identity": identity, "step": step, "history": history})
                write_json(out / "history.json", history)
            if step == stop_after:
                break
        job.update(status="completed" if step == config.max_steps else "interrupted_for_software_test",
                   completed_steps=step, checkpoint=str(last_checkpoint.resolve()),
                   measured_wall_seconds=time.monotonic() - started,
                   trainable_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad),
                   total_parameters=sum(p.numel() for p in model.parameters()), scientific_performance=None)
        write_json(out / "run.json", job)
        return job
    except Exception as error:
        job.update(status="failed", completed_steps=step, error_type=type(error).__name__, error=str(error),
                   measured_wall_seconds=time.monotonic() - started)
        write_json(out / "run.json", job)
        raise


def evaluate_development(model, data, *, seed=17, device="cpu", bootstrap_draws=200, library=None, library_exposure_review=None):
    """One candidate/attempt per method; no best-of-k or blind set access."""
    rows = []
    if library is not None and (not isinstance(library_exposure_review, str) or not library_exposure_review.strip()):
        raise ValueError("Source-library comparison requires explicit source/family exposure review")
    for i, example in enumerate(data["records"]["development"]):
        sampled = generate(model, example.request, count=1, max_attempts=1, seed=seed + i)
        candidate = sampled["candidates"][0]["linker_sequence"] if sampled["candidates"] else None
        baselines = template_baselines(data["records"]["train"], example.request, model.config.flank_residues)
        calls = {"infiller": candidate, **{key: baselines[key] for key in ("length_matched_frequency", "training_only_context_retrieval")}}
        library_report = None
        if library is not None:
            from .templates import template_candidates
            library_report = template_candidates(library, example.request, count=1)
            calls["cited_source_library"] = library_report["candidates"][0]["linker_sequence"] if library_report["candidates"] else None
        rows.append({"record_id": example.record_id, "family_ids": example.family_ids,
                     "calls": calls, "exact": {key: value == example.linker for key, value in calls.items()},
                     "edit_distance": {key: edit_distance(value, example.linker) if value is not None else None for key, value in calls.items()},
                     "generation": sampled, "baseline_eligibility": baselines["eligible_training_templates"],
                     "source_library": library_report})
    methods = list(rows[0]["calls"])
    from .benchmark import compare_reconstruction
    comparison = compare_reconstruction(data["records"]["development"],
        {name: {row["record_id"]: row["calls"][name] for row in rows} for name in methods},
        bootstrap_draws=bootstrap_draws, seed=seed)
    return {"task": "known_length_natural_linker_reconstruction_development_only", "synthetic_software_fixture": data["synthetic"],
            "seed": seed, "candidate_budget": 1, "attempt_budget_per_method": 1, "rows": rows,
            "summary": {key: {"attempted_records": len(rows), "valid_calls": sum(row["calls"][key] is not None for row in rows),
                               "exact_matches": sum(row["exact"][key] for row in rows),
                               "missing_or_rejected": sum(row["calls"][key] is None for row in rows)} for key in methods},
            "input_hashes": data["input_hashes"],
            "paired_comparison": comparison, "library_exposure_review": library_exposure_review,
            "limitation": "Sequence reconstruction only; no structural, functional, uncertainty-calibration or frontier claim. This helper does not implement blind evaluation."}
