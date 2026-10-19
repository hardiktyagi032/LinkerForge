"""Fail-closed exact/containment audit of protected DFL train vs development."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/caid3_protected_dfl_v1"
OUT = ROOT / "reports/track-transfer/2026-10-17-protected-train-dev-exact-overlap.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    for row in rows:
        if not row["protein_id"] or not row["sequence"] or len(row["sequence"]) != len(row["labels"]):
            raise ValueError(f"Malformed row in {path}")
    return rows


def main() -> None:
    train_path, dev_path = DATA / "train.jsonl", DATA / "development.jsonl"
    train, dev = load(train_path), load(dev_path)
    hits = []
    for left in train:
        for right in dev:
            a, b = left["sequence"].upper(), right["sequence"].upper()
            reasons = []
            if left["protein_id"] == right["protein_id"]:
                reasons.append("same_protein_id")
            if a == b:
                reasons.append("same_full_sequence")
            elif a in b or b in a:
                reasons.append("one_full_sequence_contained_in_other")
            if reasons:
                hits.append({"train_id": left["protein_id"], "development_id": right["protein_id"],
                             "train_length": len(a), "development_length": len(b), "reasons": reasons})
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "protected train vs development only; CAID3 labels never opened",
        "test": "exact protein ID, full-sequence equality, and either-direction full-sequence containment",
        "limit": "A zero-hit result does not exclude local similarity, homologs, or domain-family leakage.",
        "sha256": {"script": sha(Path(__file__)), "manifest": sha(DATA / "manifest.json"),
                   "train": sha(train_path), "development": sha(dev_path)},
        "train_records": len(train), "development_records": len(dev), "pairs_examined": len(train) * len(dev),
        "hit_count": len(hits), "hits": hits,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "hits"}, indent=2))


if __name__ == "__main__":
    main()
