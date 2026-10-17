"""Sequential, two-round SAM repeat queue; no concurrent GPU jobs."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from preflight_caid3_protected_training import verify

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/dfl_sam_repeat_2026-10-17.json"
DATA = ROOT / "data/processed/caid3_protected_dfl_v1/manifest.json"
RUNNER = ROOT / "scripts/run_caid3_protected_sam_repeat_trial.py"
MODEL = ROOT / "src/linkerforge/models/sam_linker_variants.py"
OUTPUT = ROOT / "artifacts/dfl-sam-repeat-2026-10-17"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Repeat output already exists: {OUTPUT}")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    jobs = config["rounds"]
    if len(jobs) != 4 or len({(name, seed) for name, seed in jobs}) != 4:
        raise ValueError("Expected exactly four unique repeat jobs")
    if verify(DATA)["status"] != "pass_under_declared_sequence_screen":
        raise ValueError("Protected-data gate failed")
    frozen = {"config_sha256": sha(CONFIG), "data_manifest_sha256": sha(DATA),
              "runner_sha256": sha(RUNNER), "model_source_sha256": sha(MODEL)}
    OUTPUT.mkdir(parents=True)
    for round_number, group in enumerate((jobs[:2], jobs[2:]), 1):
        ledger_path = OUTPUT / f"round{round_number}-ledger.json"
        ledger = {"schema_version": "1.0.0", "status": "running", "round": round_number,
                  "started_utc": datetime.now(timezone.utc).isoformat(), **frozen,
                  "planned_jobs": group, "charged_trial_seconds": 0.0, "runs": [],
                  "claim_status": "protected_development_not_independent"}
        save(ledger_path, ledger)
        budget = float(config["max_gpu_hours_per_round"]) * 3600
        try:
            for variant, seed in group:
                if any(sha(path) != expected for path, expected in (
                        (CONFIG, frozen["config_sha256"]), (DATA, frozen["data_manifest_sha256"]),
                        (RUNNER, frozen["runner_sha256"]), (MODEL, frozen["model_source_sha256"]))):
                    raise ValueError("Config/source/data hash changed during queue")
                if verify(DATA)["status"] != "pass_under_declared_sequence_screen":
                    raise ValueError("Protected-data gate failed before job")
                remaining = budget - ledger["charged_trial_seconds"]
                if remaining <= 0:
                    ledger["status"] = "budget_exhausted"
                    break
                limit = min(remaining, float(config["max_seconds_per_trial"]))
                name = f"{variant}-seed{seed}"
                output = OUTPUT / name
                command = [sys.executable, str(RUNNER), "--variant", variant,
                           "--seed", str(seed), "--output-dir", str(output),
                           "--max-seconds", str(limit)]
                start = time.perf_counter()
                with (OUTPUT / f"{name}.log").open("w", encoding="utf-8") as log:
                    try:
                        code = subprocess.run(command, cwd=ROOT, stdout=log,
                                              stderr=subprocess.STDOUT, timeout=limit + 90).returncode
                    except subprocess.TimeoutExpired:
                        code = "subprocess_timeout"
                elapsed = time.perf_counter() - start
                path = output / "manifest.json"
                manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
                ledger["runs"].append({"variant": variant, "seed": seed, "exit_code": code,
                                       "manifest": str(path), "wall_seconds": round(elapsed, 3),
                                       "trial_status": manifest.get("status") if manifest else "missing",
                                       "best_development": manifest.get("best_development") if manifest else None})
                ledger["charged_trial_seconds"] = round(ledger["charged_trial_seconds"] + elapsed, 3)
                if elapsed > limit + 120:
                    ledger["status"] = "suspension_or_clock_gap_requires_audit"
                elif code != 0 or not manifest or manifest["status"] != "completed":
                    ledger["status"] = "stopped_on_incomplete_trial"
                save(ledger_path, ledger)
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
            save(ledger_path, ledger)
        if ledger["status"] != "completed":
            break


if __name__ == "__main__":
    main()
