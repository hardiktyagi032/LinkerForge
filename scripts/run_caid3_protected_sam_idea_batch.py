"""Run five protected-data SAM-like trials sequentially in two bounded rounds."""

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
CONFIG = ROOT / "configs/dfl_sam_ideas_batch_2026-10-17.json"
DATA_MANIFEST = ROOT / "data/processed/caid3_protected_dfl_v1/manifest.json"
RUNNER = ROOT / "scripts/run_caid3_protected_sam_idea_trial.py"
MODEL = ROOT / "src/linkerforge/models/sam_linker_variants.py"
OUTPUT = ROOT / "artifacts/dfl-sam-ideas-batch-2026-10-17"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, payload: dict) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing duplicate suite: {OUTPUT}")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    rounds = config["rounds"]
    if len(rounds) != 2 or [len(group) for group in rounds] != [3, 2]:
        raise ValueError("Expected exactly two rounds of 3 and 2 variants")
    names = [name for group in rounds for name in group]
    if len(set(names)) != 5:
        raise ValueError("Expected five unique variants")
    if verify(DATA_MANIFEST)["status"] != "pass_under_declared_sequence_screen":
        raise ValueError("Protected-data preflight failed")
    frozen = {"config_sha256": sha(CONFIG), "data_manifest_sha256": sha(DATA_MANIFEST),
              "runner_sha256": sha(RUNNER), "model_source_sha256": sha(MODEL)}
    OUTPUT.mkdir(parents=True)
    for round_index, group in enumerate(rounds, start=1):
        ledger_path = OUTPUT / f"round{round_index}-ledger.json"
        ledger = {"schema_version": "1.0.0", "status": "running", "round": round_index,
                  "started_utc": datetime.now(timezone.utc).isoformat(), **frozen,
                  "planned_variants": group, "charged_trial_seconds": 0.0, "runs": [],
                  "claim_status": "filtered_development_not_Caid3_independent"}
        save(ledger_path, ledger)
        budget = float(config["max_gpu_hours_per_round"]) * 3600
        try:
            for name in group:
                if any(sha(path) != digest for path, digest in ((CONFIG, frozen["config_sha256"]),
                        (DATA_MANIFEST, frozen["data_manifest_sha256"]),
                        (RUNNER, frozen["runner_sha256"]), (MODEL, frozen["model_source_sha256"]))):
                    raise ValueError("Source, config, or data manifest changed during queue")
                if verify(DATA_MANIFEST)["status"] != "pass_under_declared_sequence_screen":
                    raise ValueError("Protected-data preflight failed before job")
                remaining = budget - ledger["charged_trial_seconds"]
                if remaining <= 0:
                    ledger["status"] = "budget_exhausted"
                    break
                limit = min(remaining, float(config["max_seconds_per_trial"]))
                output = OUTPUT / name
                command = [sys.executable, str(RUNNER), "--variant", name,
                           "--output-dir", str(output), "--max-seconds", str(limit)]
                start = time.perf_counter()
                with (OUTPUT / f"{name}.log").open("w", encoding="utf-8") as log:
                    try:
                        code = subprocess.run(command, cwd=ROOT, stdout=log,
                                              stderr=subprocess.STDOUT, timeout=limit + 90).returncode
                    except subprocess.TimeoutExpired:
                        code = "subprocess_timeout"
                elapsed = time.perf_counter() - start
                manifest_path = output / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
                ledger["runs"].append({"variant": name, "exit_code": code,
                                       "manifest": str(manifest_path),
                                       "trial_status": manifest.get("status") if manifest else "missing",
                                       "wall_seconds": round(elapsed, 3),
                                       "best_development": manifest.get("best_development") if manifest else None})
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
        if ledger["status"] != "completed":
            break


if __name__ == "__main__":
    main()
