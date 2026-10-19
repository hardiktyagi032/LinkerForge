"""Run the two preregistered global-context repeat seeds, sequentially."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from preflight_caid3_protected_training import verify


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/caid3_protected_dfl_v1/manifest.json"
CONFIG = ROOT / "configs/dfl_global_context_repeat_2026-10-17.json"
RUNNER = ROOT / "scripts/run_caid3_protected_competitor_gap_trial.py"
MODEL = ROOT / "src/linkerforge/models/competitor_gap_segmenter.py"
OUTPUT = ROOT / "artifacts/dfl-global-context-repeat-2026-10-17"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: dict) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if "global_context" not in config["variants"]:
        raise ValueError("Global context missing from frozen trial config")
    frozen = {"data_manifest_sha256": sha(DATA), "config_sha256": sha(CONFIG),
              "runner_sha256": sha(RUNNER), "model_source_sha256": sha(MODEL)}
    if verify(DATA)["status"] != "pass_under_declared_sequence_screen":
        raise ValueError("Protected-data preflight failed")
    OUTPUT.mkdir(parents=True)
    ledger = {"schema_version": "1.0.0", "status": "running", "pid": os.getpid(),
              "started_utc": datetime.now(timezone.utc).isoformat(),
              **frozen, "planned_seeds": [17, 31], "charged_trial_seconds": 0.0, "runs": [],
              "claim_status": "protected_development_repeat_not_independent"}
    path = OUTPUT / "ledger.json"
    save(path, ledger)
    try:
        for seed in ledger["planned_seeds"]:
            if any(sha(file) != frozen[key] for key, file in (("data_manifest_sha256", DATA),
                    ("config_sha256", CONFIG), ("runner_sha256", RUNNER), ("model_source_sha256", MODEL))):
                raise ValueError("Frozen input or source changed")
            if verify(DATA)["status"] != "pass_under_declared_sequence_screen":
                raise ValueError("Protected-data preflight failed before trial")
            budget = min(1800.0, 6 * 3600 - ledger["charged_trial_seconds"])
            if budget <= 0:
                ledger["status"] = "budget_exhausted"
                break
            folder = OUTPUT / f"global_context-seed{seed}"
            command = [sys.executable, str(RUNNER), "--variant", "global_context", "--seed", str(seed),
                       "--config", str(CONFIG),
                       "--output-dir", str(folder), "--max-seconds", str(budget)]
            started = time.perf_counter()
            with (OUTPUT / f"seed{seed}.log").open("w", encoding="utf-8") as log:
                try:
                    code = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                          timeout=budget + 90).returncode
                except subprocess.TimeoutExpired:
                    code = "timeout"
            elapsed = time.perf_counter() - started
            manifest_path = folder / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
            ledger["runs"].append({"seed": seed, "exit_code": code, "wall_seconds": round(elapsed, 3),
                                   "manifest": str(manifest_path), "trial_status": manifest.get("status") if manifest else "missing",
                                   "best_development": manifest.get("best_development") if manifest else None})
            ledger["charged_trial_seconds"] = round(ledger["charged_trial_seconds"] + elapsed, 3)
            if code != 0 or not manifest or manifest.get("status") != "completed":
                ledger["status"] = "stopped_on_incomplete_trial"
            save(path, ledger)
            if ledger["status"] != "running":
                break
        else:
            ledger["status"] = "completed"
    except Exception as exc:
        ledger["status"] = "launcher_failed"
        ledger["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        ledger["finished_utc"] = datetime.now(timezone.utc).isoformat()
        save(path, ledger)


if __name__ == "__main__":
    main()
