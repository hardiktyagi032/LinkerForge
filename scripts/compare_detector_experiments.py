"""Compare validation-only detector ablations without opening the blind fold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_run(directory: Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    epochs = [json.loads(line) for line in (directory / "epochs.jsonl").read_text(
        encoding="utf-8").splitlines() if line.strip()]
    if not epochs:
        raise ValueError(f"No completed epochs in {directory}")
    best = max(epochs, key=lambda row: row["validation"]["residue_auprc"])
    return {
        "directory": str(directory.resolve()),
        "status": manifest["status"],
        "model_id": manifest["model_id"],
        "revision": manifest["revision"],
        "train_sha256": manifest["train_sha256"],
        "validation_sha256": manifest["validation_sha256"],
        "loss": manifest.get("loss", {"name": "weighted_bce", "focal_gamma": 0.0}),
        "completed_epochs": len(epochs),
        "selected_epoch": best["epoch"],
        "best_validation_auprc": best["validation"]["residue_auprc"],
        "selected_validation_operating_point": best["validation"][
            "validation_selected_operating_point"],
        "validation_precision_90_operating_point": best["validation"].get(
            "validation_precision_90_operating_point"),
    }


def compare(directories: list[Path]) -> dict:
    runs = [read_run(path) for path in directories]
    for key in ("model_id", "revision", "train_sha256", "validation_sha256"):
        if len({run[key] for run in runs}) != 1:
            raise ValueError(f"Incomparable experiments: {key} differs")
    return {"selection_set": "validation_only", "metric": "residue_auprc",
            "runs": runs,
            "winner_if_all_completed": (
                max(runs, key=lambda row: row["best_validation_auprc"])["directory"]
                if all(run["status"] == "completed" for run in runs) else None)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directories", nargs="+", type=Path)
    args = parser.parse_args()
    print(json.dumps(compare(args.run_directories), indent=2))


if __name__ == "__main__":
    main()
