"""Sequential, bounded baseline suite on the CAID3 sequence-screened DFL data."""

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
CONFIG = ROOT / "configs/dfl_caid3_protected_baselines_2026-10-16.json"
DATA_MANIFEST = ROOT / "data/processed/caid3_protected_dfl_v1/manifest.json"
RUNNER = ROOT / "scripts/run_caid3_protected_dfl_trial.py"
OUTPUT = ROOT / "artifacts/dfl-caid3-protected-baselines-2026-10-16"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, ledger: dict) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing duplicate baseline suite at {OUTPUT}")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    gate = verify(DATA_MANIFEST)
    if gate["status"] != "pass_under_declared_sequence_screen":
        raise ValueError("Protected-data gate failed")
    planned = [(arch, condition, seed, f"{arch}-{condition}-seed{seed}")
               for seed in config["seeds"] for arch in config["architecture"]
               for condition in config["conditions"]]
    if len(planned) != 12:
        raise ValueError("Unexpected baseline trial count")
    OUTPUT.mkdir(parents=True)
    ledger_path = OUTPUT / "ledger.json"
    ledger = {"schema_version": "1.0.0", "status": "running",
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "config_sha256": sha(CONFIG), "data_manifest_sha256": sha(DATA_MANIFEST),
              "runner_sha256": sha(RUNNER), "planned_runs": [row[3] for row in planned],
              "charged_trial_seconds": 0.0, "runs": [],
              "claim_status": "filtered_development_not_Caid3_independent"}
    save(ledger_path, ledger)
    budget = float(config["max_gpu_hours_total"]) * 3600
    try:
        for arch, condition, seed, name in planned:
            verify(DATA_MANIFEST)
            remaining = budget - ledger["charged_trial_seconds"]
            if remaining <= 0:
                ledger["status"] = "budget_exhausted"
                break
            limit = min(remaining, float(config["max_seconds_per_trial"]))
            command = [sys.executable, str(RUNNER), "--arch", arch,
                       "--condition", condition, "--seed", str(seed),
                       "--output-dir", str(OUTPUT / name), "--max-seconds", str(limit)]
            start = time.perf_counter()
            with (OUTPUT / f"{name}.log").open("w", encoding="utf-8") as log:
                try:
                    process = subprocess.run(command, cwd=ROOT, stdout=log,
                                             stderr=subprocess.STDOUT, timeout=limit + 90)
                    code = process.returncode
                except subprocess.TimeoutExpired:
                    code = "subprocess_timeout"
            elapsed = time.perf_counter() - start
            manifest_path = OUTPUT / name / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
            ledger["runs"].append({"name": name, "exit_code": code,
                                   "manifest": str(manifest_path),
                                   "trial_status": manifest.get("status") if manifest else "missing",
                                   "wall_seconds": round(elapsed, 3)})
            if elapsed > limit + 120:
                ledger["status"] = "suspension_or_clock_gap_requires_audit"
            else:
                ledger["charged_trial_seconds"] = round(ledger["charged_trial_seconds"] + elapsed, 3)
            if ledger["status"] == "running" and (code != 0 or not manifest or manifest["status"] != "completed"):
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


if __name__ == "__main__":
    main()
