"""Run three protected competitor-gap ablations sequentially and fail closed."""

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
CONFIG = ROOT / "configs/dfl_competitor_gap_round_2026-10-17.json"
DATA = ROOT / "data/processed/caid3_protected_dfl_v1/manifest.json"
RUNNER = ROOT / "scripts/run_caid3_protected_competitor_gap_trial.py"
MODEL = ROOT / "src/linkerforge/models/competitor_gap_segmenter.py"
OUTPUT = ROOT / "artifacts/dfl-competitor-gap-round-2026-10-17"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main():
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    variants = config["variants"]
    if len(variants) != 3 or len(set(variants)) != 3:
        raise ValueError("Expected exactly three distinct variants")
    if verify(DATA)["status"] != "pass_under_declared_sequence_screen":
        raise ValueError("Protected-data gate failed")
    frozen = {"config_sha256": sha(CONFIG), "data_manifest_sha256": sha(DATA),
              "runner_sha256": sha(RUNNER), "model_source_sha256": sha(MODEL)}
    OUTPUT.mkdir(parents=True)
    ledger = {"schema_version": "1.0.0", "status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
              **frozen, "planned_variants": variants, "charged_trial_seconds": 0.0, "runs": [],
              "claim_status": "protected_development_not_Caid3_selection"}
    path = OUTPUT / "ledger.json"
    save(path, ledger)
    try:
        for variant in variants:
            if any(sha(p) != digest for p, digest in ((CONFIG, frozen["config_sha256"]),
                    (DATA, frozen["data_manifest_sha256"]), (RUNNER, frozen["runner_sha256"]),
                    (MODEL, frozen["model_source_sha256"]))):
                raise ValueError("Frozen config, source, or data changed")
            if verify(DATA)["status"] != "pass_under_declared_sequence_screen":
                raise ValueError("Protected-data preflight failed before trial")
            remaining = config["max_gpu_hours_per_round"] * 3600 - ledger["charged_trial_seconds"]
            if remaining <= 0:
                ledger["status"] = "budget_exhausted"
                break
            limit = min(remaining, config["max_seconds_per_trial"])
            folder = OUTPUT / variant
            command = [sys.executable, str(RUNNER), "--variant", variant,
                       "--output-dir", str(folder), "--max-seconds", str(limit)]
            start = time.perf_counter()
            with (OUTPUT / f"{variant}.log").open("w", encoding="utf-8") as log:
                try:
                    code = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                          timeout=limit + 90).returncode
                except subprocess.TimeoutExpired:
                    code = "subprocess_timeout"
            elapsed = time.perf_counter() - start
            manifest_path = folder / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
            ledger["runs"].append({"variant": variant, "exit_code": code, "wall_seconds": round(elapsed, 3),
                                   "manifest": str(manifest_path),
                                   "trial_status": manifest.get("status") if manifest else "missing",
                                   "best_development": manifest.get("best_development") if manifest else None})
            ledger["charged_trial_seconds"] = round(ledger["charged_trial_seconds"] + elapsed, 3)
            if elapsed > limit + 120:
                ledger["status"] = "suspension_or_clock_gap_requires_audit"
            elif code != 0 or not manifest or manifest["status"] != "completed":
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
