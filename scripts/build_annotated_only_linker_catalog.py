"""Separate explicitly labeled linkers from inferred interdomain candidates."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/processed/linker_catalog/expanded_wheat_v2/unique_discovery_sequences.v1.jsonl.gz"
DEFAULT_CONFIG = ROOT / "configs/annotated_only_linker_catalog_v1.json"
DEFAULT_OUT = ROOT / "data/processed/linker_catalog/annotated_only_v1"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def annotated_record(row: dict, qualifying_keys: set[str], config: dict,
                     provenance: dict) -> dict | None:
    sources = row["sources"]
    qualifying = {key: sources[key] for key in sorted(qualifying_keys & sources.keys())}
    if not qualifying:
        return None
    existing_statuses = sources.get("existing_catalog", {}).get("usage_statuses", [])
    if any(value.startswith(config["protected_usage_prefix"]) for value in existing_statuses):
        status = "protected_benchmark"
    elif config["quarantined_usage_status"] in existing_statuses:
        status = "quarantined"
    else:
        status = "needs_boundary_and_homology_audit"
    sequence = row["sequence"]
    return {"schema_version": "1.0.0", "sequence": sequence,
            "sequence_sha256": hashlib.sha256(sequence.encode("ascii")).hexdigest(),
            "length": len(sequence), "qualifying_source_keys": sorted(qualifying),
            "qualifying_sources": qualifying, "usage_status": status,
            "provenance": provenance}


def build(source: Path, config_path: Path, out: Path) -> dict:
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    qualifying_keys = set(config["qualifying_source_keys"])
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    provenance = {"input_sha256": sha256_file(source),
                  "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
                  "pipeline_commit": commit,
                  "pipeline_sha256": sha256_file(Path(__file__))}
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "annotated_linker_sequences.v1.jsonl.gz"
    tsv_path = out / "annotated_linker_sequences.v1.tsv"
    counts = {"input_exact_unique": 0, "annotated_exact_unique": 0,
              "inferred_only_excluded": 0, "protected_benchmark": 0,
              "quarantined": 0, "needs_boundary_and_homology_audit": 0}
    by_source = {key: 0 for key in sorted(qualifying_keys)}
    with gzip.open(source, "rt", encoding="utf-8") as raw, gzip.open(
            json_path, "wt", encoding="utf-8", newline="\n") as output, tsv_path.open(
            "w", encoding="utf-8", newline="") as table:
        writer = csv.writer(table, delimiter="\t")
        writer.writerow(["sequence", "length", "qualifying_source_keys",
                         "representative_accession", "usage_status"])
        for line in raw:
            counts["input_exact_unique"] += 1
            record = annotated_record(json.loads(line), qualifying_keys, config, provenance)
            if record is None:
                counts["inferred_only_excluded"] += 1
                continue
            counts["annotated_exact_unique"] += 1
            counts[record["usage_status"]] += 1
            for key in record["qualifying_source_keys"]:
                by_source[key] += 1
            output.write(json.dumps(record, separators=(",", ":")) + "\n")
            accession = next((s["accession"] for s in record["qualifying_sources"].values()
                              if "accession" in s), "")
            writer.writerow([record["sequence"], record["length"],
                             ";".join(record["qualifying_source_keys"]), accession,
                             record["usage_status"]])
    manifest = {"schema_version": "1.0.0", "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "input": str(source), "config": str(config_path), "provenance": provenance,
                "counts": counts, "annotated_by_source_overlapping": by_source,
                "output_sha256": {json_path.name: sha256_file(json_path),
                                  tsv_path.name: sha256_file(tsv_path)},
                "qualification_rule": config["source_rule"],
                "warning": "Explicit source labeling, not necessarily experimental confirmation or training readiness."}
    (out / "manifest.v1.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                          encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    print(json.dumps(build(args.input, args.config, args.out), indent=2))
