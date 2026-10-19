"""Prepare and dispatch existing trainers. Never approve a run or acquire data.

The round reserves every job's maximum wall time, including failures. A local
exclusive lock prevents this dispatcher overlapping itself on one host; it
cannot inspect or rule out jobs on another host or scheduler.
"""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from linkerforge.attachment.data import preflight as site_preflight
from linkerforge.attachment.engine import SiteTrainConfig
from linkerforge.generation.contracts import canonical_hash
from linkerforge.generation.data import file_sha256, load_json, preflight as generator_preflight
from linkerforge.generation.engine import TrainConfig, environment, write_json


def source_identity():
    root = Path(__file__).resolve().parents[1]
    return {p.relative_to(root).as_posix(): file_sha256(p)
            for directory in ("attachment", "generation", "geometry", "pipeline", "properties")
            for p in sorted((root / directory).glob("*.py"))}


def _config(component, value):
    return (SiteTrainConfig if component == "attachment" else TrainConfig).from_dict(value)


def _preflight(component, manifest):
    return (site_preflight if component == "attachment" else generator_preflight)(manifest, synthetic=False)


def prepare(recipe_path, output):
    """Write immutable job configs and unsigned receipt templates, no fitting."""
    recipe_path, out = Path(recipe_path).resolve(), Path(output).resolve()
    recipe = load_json(recipe_path)
    if (set(recipe) != {"format", "round_id", "seeds", "variants", "max_total_wall_seconds", "review_reference"}
            or recipe["format"] != "design-training-round.v0" or not isinstance(recipe["round_id"], str) or not recipe["round_id"]):
        raise ValueError("Expected a named private design-training-round.v0 recipe")
    seeds, variants, ceiling = recipe["seeds"], recipe["variants"], recipe["max_total_wall_seconds"]
    if (not isinstance(seeds, list) or not 3 <= len(seeds) <= 8 or len(set(seeds)) != len(seeds)
            or any(type(s) is not int or s < 0 for s in seeds)):
        raise ValueError("Prepare at least three distinct seeds; no favourable-seed selection")
    if (not isinstance(variants, list) or not 1 <= len(variants) <= 3
            or type(ceiling) is not int or not 1 <= ceiling <= 21600):
        raise ValueError("At most three variants and six reserved GPU-hours per round")
    jobs, names, input_files, total, component_inputs = [], set(), {}, 0, {}
    for variant in variants:
        if (set(variant) != {"name", "component", "config", "manifest"}
                or variant["component"] not in {"attachment", "generator"}
                or not isinstance(variant["name"], str) or not variant["name"]
                or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in variant["name"])
                or variant["name"] in names):
            raise ValueError("Distinct safe variant names, component, config and nullable manifest required")
        names.add(variant["name"])
        config_path = (recipe_path.parent / variant["config"]).resolve()
        base = _config(variant["component"], load_json(config_path))
        input_files[str(config_path)] = file_sha256(config_path)
        manifest, data, blockers = variant["manifest"], None, []
        if manifest is None:
            blockers.append("reviewed_dataset_manifest_not_supplied")
        elif not isinstance(manifest, str) or not manifest:
            raise ValueError("Manifest must be a path or null, never a fabricated identity")
        else:
            manifest = str((recipe_path.parent / manifest).resolve())
            try:
                data = _preflight(variant["component"], manifest)
            except (OSError, ValueError, KeyError, TypeError) as error:
                blockers.append(f"dataset_preflight: {type(error).__name__}: {error}")
        if data:
            previous = component_inputs.setdefault(variant["component"], data["input_hashes"])
            if previous != data["input_hashes"]:
                raise ValueError("Variants within one component must use exactly matched fitting/development inputs")
        if not recipe["review_reference"]:
            blockers.append("round_review_not_supplied")
        for seed in seeds:
            config = replace(base, seed=seed)
            name = f"{variant['name']}-seed-{seed}"
            total += config.max_wall_seconds
            jobs.append({"job_id": name, "component": variant["component"], "seed": seed,
                         "config": asdict(config), "config_sha256": canonical_hash(asdict(config)),
                         "manifest": manifest, "input_hashes": data["input_hashes"] if data else None,
                         "reserved_wall_seconds": config.max_wall_seconds,
                         "preparation_status": "blocked" if blockers else "awaiting_execution_receipt",
                         "blockers": list(blockers), "output": "runs/" + name})
    if total > ceiling:
        raise ValueError("Sum of all variant/seed wall ceilings exceeds the aggregate round ceiling")
    out.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for job in jobs:
        directory = out / "jobs" / job["job_id"]
        directory.mkdir(parents=True)
        config_path = directory / "config.json"
        write_json(config_path, job.pop("config"))
        job["config_path"] = str(config_path.relative_to(out).as_posix())
        hashes[job["config_path"]] = file_sha256(config_path)
        receipt = directory / "execution-receipt.UNSIGNED.json"
        write_json(receipt, {"approved": False, "institution": None, "review_reference": None, "host": None,
                             "environment": None, "config_sha256": job["config_sha256"], "input_hashes": job["input_hashes"]})
    result = {"format": "prepared-design-training-round.v0", "round_id": recipe["round_id"],
              "recipe_sha256": file_sha256(recipe_path), "recipe_path": str(recipe_path),
              "source_hashes": source_identity(), "source_config_hashes": input_files,
              "prepared_files": hashes, "jobs": jobs, "max_total_wall_seconds": ceiling,
              "reserved_wall_seconds": total, "maximum_simultaneous_gpu_jobs": 1,
              "review_reference": recipe["review_reference"], "training_authorized": False,
              "remote_job_state": "unverified", "scientific_training_performed": False}
    write_json(out / "prepared.json", result)
    write_json(out / "prepared.sha256.json", {"prepared_sha256": file_sha256(out / "prepared.json")})
    return result


def checked_preparation(root):
    root = Path(root).resolve()
    value = load_json(root / "prepared.json")
    if (value.get("format") != "prepared-design-training-round.v0"
            or file_sha256(root / "prepared.json") != load_json(root / "prepared.sha256.json")["prepared_sha256"]
            or value["source_hashes"] != source_identity()):
        raise ValueError("Prepared plan/source identity changed; prepare a new reviewed round")
    for name, digest in value["prepared_files"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or file_sha256(path) != digest:
            raise ValueError("Prepared configuration identity mismatch")
    return value


def inspect(root):
    value = checked_preparation(root)
    states = {}
    for job in value["jobs"]:
        path = Path(root) / job["output"] / "dispatch.json"
        states[job["job_id"]] = load_json(path) if path.exists() else {"status": "not_dispatched"}
    return {"round_id": value["round_id"], "jobs": states, "training_authorized": False,
            "remote_job_state": "unverified", "local_lock": str(lock_path()),
            "local_lock_evidence": load_json(lock_path()) if lock_path().exists() else None,
            "limitation": "Ledger/lock state does not prove a remote scheduler or another launcher is idle."}


def lock_path():
    # Stable across checkouts and TMP/TEMP overrides for the current OS user.
    # Another account/host/scheduler still requires actual external inspection.
    return Path.home() / ".cache" / "linkerforge" / "design-training.lock"


def completed_checkpoint(root, job):
    target = Path(root) / job["output"] / "training"
    result = load_json(target / "run.json")
    checkpoint = Path(result["checkpoint"]).resolve()
    if (result.get("status") != "completed" or result.get("completed_steps") != _config(job["component"], load_json(Path(root) / job["config_path"])).max_steps
            or result.get("config_sha256") != job["config_sha256"] or result.get("input_hashes") != job["input_hashes"]
            or not checkpoint.is_relative_to(target.resolve())):
        raise ValueError("Completed run/checkpoint must bind this job, data and full step count")
    metadata = load_json(checkpoint / "model.json")
    state = load_json(checkpoint / "training.json")
    if (metadata.get("state_sha256") != file_sha256(checkpoint / "model.safetensors")
            or state.get("model_metadata_sha256") != file_sha256(checkpoint / "model.json")
            or state.get("identity", {}).get("config_sha256") != job["config_sha256"]
            or state.get("identity", {}).get("input_hashes") != job["input_hashes"]):
        raise ValueError("Completed checkpoint metadata/weights do not match the job")
    return checkpoint


def benchmark_commands(root, coverage_fraction=None, bootstrap_draws=200, seed=17):
    """Prepare argv, never evaluate labels or execute a benchmark implicitly."""
    root = Path(root).resolve()
    value = checked_preparation(root)
    if (coverage_fraction is not None and (type(coverage_fraction) not in (float, int) or not 0 < coverage_fraction <= 1)
            or type(bootstrap_draws) is not int or not 0 <= bootstrap_draws <= 1000 or type(seed) is not int or seed < 0):
        raise ValueError("Explicit development coverage and bounded resampling settings required")
    checkpoints, blockers = {}, []
    for job in value["jobs"]:
        dispatch = root / job["output"] / "dispatch.json"
        if not dispatch.exists() or load_json(dispatch).get("status") != "completed":
            blockers.append({"job_id": job["job_id"], "reason": "all requested seeds/control attempts must finish; none may be silently dropped"})
            continue
        try:
            checkpoints[job["job_id"]] = completed_checkpoint(root, job)
        except (OSError, KeyError, ValueError) as error:
            blockers.append({"job_id": job["job_id"], "reason": str(error)})
    if any(j["component"] == "attachment" for j in value["jobs"]) and coverage_fraction is None:
        blockers.append({"job_id": None, "reason": "freeze site coverage fraction on development before comparison"})
    commands = []
    if not blockers:
        common = ["--bootstrap-draws", str(bootstrap_draws), "--seed", str(seed)]
        site_jobs = [j for j in value["jobs"] if j["component"] == "attachment"]
        if site_jobs:
            command = [sys.executable, "-m", "linkerforge.attachment", "benchmark-development", "--manifest", site_jobs[0]["manifest"],
                       "--coverage-fraction", str(coverage_fraction), *common, "--output", str(root / "attachment-development.json")]
            for job in site_jobs:
                command += ["--checkpoint", f"{job['job_id']}={checkpoints[job['job_id']]}"]
            commands.append({"component": "attachment", "argv": command})
        for job in value["jobs"]:
            if job["component"] == "generator":
                commands.append({"component": "generator", "job_id": job["job_id"], "argv": [sys.executable, "-m", "linkerforge.generation",
                    "evaluate-development", "--manifest", job["manifest"], "--checkpoint", str(checkpoints[job["job_id"]]),
                    *common, "--output", str(root / (job["job_id"] + "-development.json"))]})
    return {"format": "design-development-commands.v0", "status": "blocked" if blockers else "prepared_not_executed",
            "blockers": blockers, "commands": commands, "prepared_sha256": file_sha256(root / "prepared.json"),
            "independent_test_evaluation": False, "benchmark_executed": False,
            "limitations": ["Run with the installed package or PYTHONPATH pointing to this exact src directory.",
                            "Inspect real jobs and review total benchmark compute before executing these argv.",
                            "Development sequence/site diagnostics do not establish the primary structural endpoint or fusion function.",
                            "No seed selection, cross-task pooling or automatic weight promotion."]}


def launch(root, job_id, receipt_path, device="cuda:0"):
    root, receipt_path = Path(root).resolve(), Path(receipt_path).resolve()
    value = checked_preparation(root)
    matches = [j for j in value["jobs"] if j["job_id"] == job_id]
    if len(matches) != 1:
        raise ValueError("Unknown job ID")
    job = matches[0]
    if job["blockers"] or job["preparation_status"] != "awaiting_execution_receipt":
        raise ValueError("Job is blocked; supply reviewed inputs and prepare a new round")
    config_path = root / job["config_path"]
    config = _config(job["component"], load_json(config_path))
    data = _preflight(job["component"], job["manifest"])
    receipt = load_json(receipt_path)
    if (data["input_hashes"] != job["input_hashes"] or receipt.get("approved") is not True
            or not receipt.get("institution") or not receipt.get("review_reference")
            or receipt.get("host") != platform.node() or receipt.get("environment") != environment()
            or receipt.get("config_sha256") != canonical_hash(asdict(config))
            or receipt.get("input_hashes") != data["input_hashes"]):
        raise ValueError("Exact reviewed institution/host/environment/config/input receipt required")
    if device != "cpu" and (not device.startswith("cuda:") or not device[5:].isdigit()):
        raise ValueError("One explicit CUDA device or cpu required")
    target = root / job["output"]
    if target.exists():
        raise ValueError("Job already attempted; inspect it. No silent retry or budget reset")
    command = [sys.executable, "-m", f"linkerforge.{'attachment' if job['component'] == 'attachment' else 'generation'}",
               "train", "--manifest", job["manifest"], "--config", str(config_path),
               "--output", str(target / "training"), "--device", device, "--execution-receipt", str(receipt_path)]
    # O_EXCL deliberately fails closed on a stale lock. Inspect actual processes
    # before a human removes one; never delete another run's lock automatically.
    lock = lock_path()
    lock.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    state = {"job_id": job_id, "host": platform.node(), "dispatcher_pid": os.getpid(), "child_pid": None,
             "status": "starting", "command": command, "device": device, "seed": config.seed,
             "started_utc": datetime.now(timezone.utc).isoformat(), "prepared_sha256": file_sha256(root / "prepared.json"),
             "execution_receipt_sha256": file_sha256(receipt_path), "input_hashes": data["input_hashes"],
             "environment": environment(), "source_hashes": value["source_hashes"],
             "reserved_wall_seconds": job["reserved_wall_seconds"], "scientific_performance": None}
    started, child, created = time.monotonic(), None, False
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump({"job_id": job_id, "dispatcher_pid": os.getpid(), "host": platform.node(), "root": str(root)}, stream)
        target.mkdir(parents=True, exist_ok=False)
        created = True
        write_json(target / "dispatch.json", state)
        child_environment = os.environ.copy()
        child_environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
        with (target / "stdout.log").open("w", encoding="utf-8") as stdout, (target / "stderr.log").open("w", encoding="utf-8") as stderr:
            child = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=child_environment)
            state.update(status="running", child_pid=child.pid)
            write_json(target / "dispatch.json", state)
            try:
                state["exit_code"] = child.wait(timeout=job["reserved_wall_seconds"])
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
                state.update(status="failed", failure="hard_wall_ceiling_reached", exit_code=child.returncode)
            else:
                run = target / "training" / "run.json"
                result = load_json(run) if run.exists() else {}
                state.update(status="failed", trainer_status=result.get("status"), checkpoint=result.get("checkpoint"))
                if child.returncode == 0 and result.get("status") == "completed":
                    state["checkpoint"] = str(completed_checkpoint(root, job))
                    state["status"] = "completed"
    except BaseException as error:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait()
        state.update(status="failed", failure=f"{type(error).__name__}: {error}")
        raise
    finally:
        state["measured_wall_seconds"] = time.monotonic()-started
        if created:
            write_json(target / "dispatch.json", state)
        lock.unlink()
    return state
