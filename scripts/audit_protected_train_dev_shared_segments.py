"""Exploratory train/dev shared 12-mer screen; not a homology classifier."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/caid3_protected_dfl_v1"
OUT = ROOT / "reports/track-transfer/2026-10-17-protected-shared-segments.json"
K = 12


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def kmers(sequence: str) -> set[str]:
    return {sequence[i:i + K] for i in range(max(0, len(sequence) - K + 1))
            if len(set(sequence[i:i + K])) >= 5}


def load(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if any(not row.get("protein_id") or not row.get("sequence") for row in rows):
        raise ValueError("Missing protein ID or sequence")
    return rows


def main() -> None:
    train_path, dev_path = DATA / "train.jsonl", DATA / "development.jsonl"
    train, dev = load(train_path), load(dev_path)
    train_sets = [(row, kmers(row["sequence"].upper())) for row in train]
    dev_sets = [(row, kmers(row["sequence"].upper())) for row in dev]
    hits = []
    for left, a in train_sets:
        for right, b in dev_sets:
            shared = a & b
            if not shared:
                continue
            fraction = len(shared) / max(1, min(len(a), len(b)))
            if len(shared) >= 10 and fraction >= 0.05:
                hits.append({"train_id": left["protein_id"], "development_id": right["protein_id"],
                             "shared_distinct_12mers": len(shared),
                             "fraction_of_smaller_12mer_set": round(fraction, 6),
                             "train_length": len(left["sequence"]), "development_length": len(right["sequence"])})
    hits.sort(key=lambda row: (-row["shared_distinct_12mers"], -row["fraction_of_smaller_12mer_set"],
                               row["train_id"], row["development_id"]))
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "protected train vs development; no CAID3 labels accessed",
        "method": "distinct exact 12-mers with >=5 residue types; flag >=10 shared and >=5% of smaller set",
        "interpretation_limit": "A flag is not proof of homology; no flag is not proof of family independence. Low-complexity and distant homology need dedicated alignment/cluster review.",
        "sha256": {"script": sha(Path(__file__)), "manifest": sha(DATA / "manifest.json"),
                   "train": sha(train_path), "development": sha(dev_path)},
        "pairs_examined": len(train) * len(dev), "flagged_pairs": len(hits), "hits": hits,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pairs_examined": payload["pairs_examined"], "flagged_pairs": len(hits),
                      "top_hits": hits[:5]}, indent=2))


if __name__ == "__main__":
    main()
