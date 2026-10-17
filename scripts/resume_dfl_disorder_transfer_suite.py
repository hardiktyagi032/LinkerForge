"""Resume only incomplete trials from the frozen DFL transfer comparison.

The original run and its interrupted trial are never modified. This launcher
records actual completed-trial runtimes separately from suspended wall time.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/dfl_disorder_transfer_autoresearch_2026-10-13.json"
ORIGINAL = ROOT / "artifacts/dfl-disorder-transfer-2026-10-13"
OUTPUT = ROOT / "artifacts/dfl-disorder-transfer-resume-2026-10-16"
TRIAL = ROOT / "scripts/run_dfl_disorder_transfer.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_ledger(path: Path, ledger: dict) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def main() -> None:
    if (OUTPUT / "ledger.json").exists() or any(OUTPUT.glob("*/manifest.json")):
        raise FileExistsError(f"Refusing to overwrite trial output in {OUTPUT}")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config_sha = digest(CONFIG)
    source_sha = digest(TRIAL)
    planned = [
        (arch, condition, seed, f"{arch}-{condition}-seed{seed}")
        for seed in config["seeds"]
        for arch in config["architecture"]
        for condition in config["conditions"]
    ]
    valid = {}
    invalid = []
    for arch, condition, seed, name in planned:
        path = ORIGINAL / name / "manifest.json"
        if not path.exists():
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if record["config_sha256"] != config_sha or record["source_sha256"] != source_sha:
            raise ValueError(f"Frozen configuration/source mismatch: {name}")
        if record["status"] == "completed" and record.get("completed_epoch") == config["dfl_finetune_epochs"]:
            valid[name] = record
        else:
            invalid.append(name)
    if len(valid) + len(invalid) > len(planned):
        raise ValueError("Invalid trial enumeration")
    charged = sum(float(row["elapsed_seconds"]) for row in valid.values())
    budget = float(config["max_gpu_hours_total"]) * 3600
    OUTPUT.mkdir(parents=True, exist_ok=True)
    ledger_path = OUTPUT / "ledger.json"
    ledger = {
        "status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
        "config_sha256": config_sha, "trial_source_sha256": source_sha,
        "original_output": str(ORIGINAL), "valid_original_runs": sorted(valid),
        "invalid_original_runs": invalid, "charged_valid_trial_seconds": round(charged, 3),
        "note": "Interrupted elapsed time is not counted as GPU time; it is not a valid completed trial.",
        "runs": [],
    }
    write_ledger(ledger_path, ledger)
    try:
        for arch, condition, seed, name in planned:
            if name in valid:
                continue
            remaining = budget - charged
            if remaining <= 0:
                ledger["status"] = "gpu_budget_exhausted"
                break
            limit = min(remaining, 1800)
            command = [sys.executable, str(TRIAL), "trial", "--arch", arch,
                       "--condition", condition, "--seed", str(seed),
                       "--output-dir", str(OUTPUT / name), "--max-seconds", str(limit)]
            start = time.perf_counter()
            with (OUTPUT / f"{name}.log").open("w", encoding="utf-8") as log:
                try:
                    result = subprocess.run(command, cwd=ROOT, stdout=log,
                                            stderr=subprocess.STDOUT, timeout=limit + 90)
                    code = result.returncode
                except subprocess.TimeoutExpired:
                    code = "subprocess_timeout"
            manifest_path = OUTPUT / name / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
            observed = round(time.perf_counter() - start, 3)
            if observed > limit + 120:
                # A suspended machine may produce a huge elapsed time. Do not
                # silently convert it into GPU-hours or a successful run.
                ledger["status"] = "suspension_or_clock_gap_requires_audit"
            else:
                charged += observed
            ledger["runs"].append({"name": name, "exit_code": code,
                                   "manifest": str(manifest_path),
                                   "status": manifest.get("status") if manifest else "missing",
                                   "wall_seconds": observed})
            ledger["charged_valid_trial_seconds"] = round(charged, 3)
            write_ledger(ledger_path, ledger)
            if ledger["status"] != "running":
                break
            if code != 0 or not manifest or manifest.get("status") != "completed":
                ledger["status"] = "stopped_on_incomplete_trial"
                break
        else:
            ledger["status"] = "completed"
    except Exception as exc:
        ledger["status"] = "launcher_failed"
        ledger["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        ledger["finished_utc"] = datetime.now(timezone.utc).isoformat()
        write_ledger(ledger_path, ledger)


if __name__ == "__main__":
    main()
