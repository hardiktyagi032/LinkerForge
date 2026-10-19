"""Export a readable sequence list from the provenance-rich discovery index.

The output is for discovery only: inferred domain gaps are not confirmed linkers.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path


def export(source: Path, destination: Path) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with gzip.open(source, "rt", encoding="utf-8") as records, destination.open(
        "w", encoding="utf-8", newline=""
    ) as output:
        writer = csv.writer(output, delimiter="\t")
        writer.writerow(["sequence", "length", "source_keys", "representative_accession",
                         "evidence_tiers", "protected_benchmark", "training_excluded", "status"])
        for line in records:
            row = json.loads(line)
            sources = row["sources"]
            existing = sources.get("existing_catalog", {})
            usage_statuses = existing.get("usage_statuses", [])
            protected = any(status.startswith("protected_") for status in usage_statuses)
            training_excluded = protected or "quarantine_pending_overlap_audit" in usage_statuses
            accession = next((value["accession"] for value in sources.values()
                              if "accession" in value), "")
            tiers = sorted({value["evidence_tier"] for value in sources.values()
                            if "evidence_tier" in value})
            writer.writerow([row["sequence"], len(row["sequence"]),
                             ";".join(sorted(sources)), accession, ";".join(tiers),
                             str(protected).lower(), str(training_excluded).lower(),
                             "discovery_only_not_training_labels"])
            count += 1
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(export(args.source, args.destination))
