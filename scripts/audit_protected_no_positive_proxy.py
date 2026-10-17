"""Audit unknown-label coverage of the protected development proxy proteins."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/processed/caid3_protected_dfl_v1/development.jsonl"
MANIFEST = SOURCE.parent / "manifest.json"
OUTPUT = ROOT / "reports/track-transfer/2026-10-17-no-positive-proxy-coverage.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line]
    proxy = []
    for row in rows:
        labels = row["labels"]
        if len(labels) != len(row["sequence"]) or set(labels) - set("01x"):
            raise ValueError(f"Malformed record {row['protein_id']}")
        if "1" not in labels and "0" in labels:
            proxy.append({"protein_id": row["protein_id"], "length": len(labels),
                          "known_zero": labels.count("0"), "unknown": labels.count("x"),
                          "known_fraction": labels.count("0") / len(labels)})
    if len(proxy) != 17:
        raise ValueError("Expected exactly 17 protected development no-positive proxy records")
    fractions = sorted(row["known_fraction"] for row in proxy)
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Protected development only; no CAID3 labels accessed",
        "interpretation": "No annotated positive is not verified absence of a DFL where the source label is x.",
        "sha256": {"script": sha(Path(__file__)), "development": sha(SOURCE), "manifest": sha(MANIFEST)},
        "proxy_proteins": len(proxy),
        "fully_known_proteins": sum(row["unknown"] == 0 for row in proxy),
        "partially_unknown_proteins": sum(row["unknown"] > 0 for row in proxy),
        "known_zero_residues": sum(row["known_zero"] for row in proxy),
        "unknown_residues": sum(row["unknown"] for row in proxy),
        "known_fraction_min": fractions[0],
        "known_fraction_median": median(fractions),
        "known_fraction_max": fractions[-1],
        "protein_evidence": proxy,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "protein_evidence"}, indent=2))


if __name__ == "__main__":
    main()
