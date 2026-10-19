"""Audit protected DFL label spans against the frozen trainer's 510-aa cuts.

This uses protected train/development labels only; CAID3 is never opened.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/caid3_protected_dfl_v1"
CONFIG = ROOT / "configs/dfl_caid3_protected_baselines_2026-10-16.json"
OUTPUT = ROOT / "reports/track-transfer/2026-10-17-protected-windowing-audit.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def spans(labels: str) -> list[tuple[int, int]]:
    found = []
    start = None
    for index, label in enumerate(labels + "0"):
        if label == "1" and start is None:
            start = index
        elif label != "1" and start is not None:
            found.append((start, index))
            start = None
    return found


def audit(path: Path, width: int) -> dict:
    result = {
        "proteins": 0,
        "proteins_longer_than_window": 0,
        "positive_spans": 0,
        "positive_spans_crossing_cut": 0,
        "positive_residues_total": 0,
        "positive_residues_in_crossing_spans": 0,
        "positive_residues_within_16_of_cut": 0,
        "known_residues_total": 0,
        "windows": 0,
        "windows_with_no_known_residues": 0,
        "windows_with_positive_residues": 0,
    }
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            labels = row["labels"]
            sequence = row["sequence"]
            if len(labels) != len(sequence) or set(labels) - set("01x"):
                raise ValueError(f"Malformed labels: {row['protein_id']}")
            length = len(sequence)
            cuts = list(range(width, length, width))
            result["proteins"] += 1
            result["proteins_longer_than_window"] += int(length > width)
            result["known_residues_total"] += sum(char != "x" for char in labels)
            result["positive_residues_total"] += labels.count("1")
            for start, end in spans(labels):
                result["positive_spans"] += 1
                if any(start < cut < end for cut in cuts):
                    result["positive_spans_crossing_cut"] += 1
                    result["positive_residues_in_crossing_spans"] += end - start
            result["positive_residues_within_16_of_cut"] += sum(
                char == "1" and any(abs(index - cut) < 16 for cut in cuts)
                for index, char in enumerate(labels)
            )
            for start in range(0, length, width):
                segment = labels[start:start + width]
                result["windows"] += 1
                result["windows_with_no_known_residues"] += int(set(segment) == {"x"})
                result["windows_with_positive_residues"] += int("1" in segment)
    return result


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    width = config["max_residues_per_window"]
    if width != 510:
        raise ValueError("Frozen window width changed; audit requires review")
    files = {name: DATA / f"{name}.jsonl" for name in ("train", "development")}
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "question": "How often do non-overlapping 510-aa training windows fragment protected DFL labels?",
        "scope": "CAID3-protected train and development only; no CAID3 labels accessed",
        "window_width": width,
        "windowing_implementation": "scripts/train_dfl_masked_cnn.py::windows",
        "interpretation_limit": "Counts alone cannot establish cause of poor transfer to another dataset.",
        "hashes_sha256": {
            "config": sha(CONFIG),
            "data_manifest": sha(DATA / "manifest.json"),
            "windowing_source": sha(ROOT / "scripts/train_dfl_masked_cnn.py"),
            **{name: sha(path) for name, path in files.items()},
            "audit_source": sha(Path(__file__)),
        },
        "splits": {name: audit(path, width) for name, path in files.items()},
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["splits"], indent=2))
    print(OUTPUT)


if __name__ == "__main__":
    main()
