"""Quantify protected DFL 0/1/x coverage without opening CAID3 labels."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/caid3_protected_dfl_v1"
OUT = ROOT / "reports/track-transfer/2026-10-17-protected-label-coverage.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(path: Path) -> dict:
    residue_counts: Counter[str] = Counter()
    by_record: Counter[str] = Counter()
    known_fractions: list[float] = []
    lengths: list[int] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            labels, sequence = row["labels"], row["sequence"]
            if not sequence or len(labels) != len(sequence) or set(labels) - set("01x"):
                raise ValueError(f"Malformed protected record: {row['protein_id']}")
            counts = Counter(labels)
            residue_counts.update(counts)
            known = counts["0"] + counts["1"]
            lengths.append(len(sequence))
            known_fractions.append(known / len(sequence))
            by_record["records"] += 1
            by_record["has_positive"] += int(counts["1"] > 0)
            by_record["no_positive_but_known"] += int(counts["1"] == 0 and known > 0)
            by_record["all_unknown"] += int(known == 0)
            by_record["partially_unknown"] += int(0 < counts["x"] < len(labels))
            by_record["fully_known"] += int(counts["x"] == 0)
    return {
        "records": dict(by_record),
        "residues": {label: residue_counts[label] for label in "01x"},
        "known_fraction": (residue_counts["0"] + residue_counts["1"]) / sum(residue_counts.values()),
        "mean_record_known_fraction": sum(known_fractions) / len(known_fractions),
        "min_record_known_fraction": min(known_fractions),
        "max_record_known_fraction": max(known_fractions),
        "length_min": min(lengths),
        "length_max": max(lengths),
    }


def main() -> None:
    names = ("train", "development", "auxiliary")
    paths = {name: DATA / f"{name}.jsonl" for name in names}
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "CAID3-protected DFL train/development and auxiliary; CAID3 labels not opened",
        "semantics": "0 and 1 are source labels; x is unknown and must remain masked. Auxiliary labels have a different source task.",
        "limits": "Coverage difference does not establish a causal explanation for external transfer.",
        "sha256": {
            "script": sha(Path(__file__)),
            "manifest": sha(DATA / "manifest.json"),
            **{name: sha(path) for name, path in paths.items()},
        },
        "splits": {name: inspect(path) for name, path in paths.items()},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["splits"], indent=2))


if __name__ == "__main__":
    main()
