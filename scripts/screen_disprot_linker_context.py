"""Screen DisProt disorder evidence between adjacent Pfam domains.

This produces review candidates, never natural-linker ground-truth labels.
DisProt coordinates are UniProt sequence coordinates; no PDB mapping is implied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def screen_entry(entry: dict) -> list[dict]:
    sequence = entry.get("sequence", "")
    domains = []
    for domain in entry.get("features", {}).get("pfam", []):
        start, end = domain.get("start"), domain.get("end")
        if isinstance(start, int) and isinstance(end, int) and 1 <= start <= end <= len(sequence):
            domains.append(domain)
    domains.sort(key=lambda value: (value["start"], value["end"], value.get("id", "")))
    # Remove identical duplicate intervals, but retain overlapping alternatives.
    domains = list({(d["start"], d["end"], d.get("id", "")): d for d in domains}.values())
    domains.sort(key=lambda value: (value["start"], value["end"], value.get("id", "")))
    results = []
    for a, b in zip(domains, domains[1:]):
        gap_start, gap_end = a["end"] + 1, b["start"] - 1
        length = gap_end - gap_start + 1
        if not 5 <= length <= 30:
            continue
        # Overlapping third-party domain calls make the boundary ambiguous.
        if any(d is not a and d is not b and d["start"] <= gap_end and d["end"] >= gap_start for d in domains):
            continue
        evidence = []
        for region in entry.get("regions", []):
            if region.get("disprot_namespace") != "Structural state" or region.get("term_name") != "disorder":
                continue
            start, end = region.get("start"), region.get("end")
            if not isinstance(start, int) or not isinstance(end, int):
                continue
            overlap = max(0, min(end, gap_end) - max(start, gap_start) + 1)
            if overlap:
                evidence.append({
                    "region_id": region.get("region_id"),
                    "start": start, "end": end, "overlap_residues": overlap,
                    "evidence_code": region.get("ec_id"),
                    "reference_id": region.get("reference_id"),
                    "release": region.get("released"),
                    "validated": region.get("validated"),
                })
        if not evidence:
            continue
        results.append({
            "schema_version": "0.1.0",
            "record_type": "disprot_domain_gap_screen_not_linker_label",
            "disprot_id": entry.get("disprot_id"), "uniprot_accession": entry.get("acc"),
            "sequence_length": len(sequence),
            "domain_a": {"pfam_id": a.get("id"), "start": a["start"], "end": a["end"]},
            "domain_b": {"pfam_id": b.get("id"), "start": b["start"], "end": b["end"]},
            "gap": {"start": gap_start, "end": gap_end, "sequence": sequence[gap_start - 1:gap_end], "length": length},
            "disorder_evidence": evidence,
            "review_status": "pending",
            "limitations": ["Pfam boundaries are third-party annotations", "disorder is not proof of linker function", "no PDB coordinate mapping"],
        })
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.input.read_text(encoding="utf-8"))
    entries = source["data"]
    records = [record for entry in entries for record in screen_entry(entry)]
    source_hash = sha256(args.input)
    config = {"release": "2026_06", "gap_min": 5, "gap_max": 30,
              "domain_source": "DisProt embedded Pfam", "region_term": "disorder"}
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unavailable"
    for record in records:
        record["provenance"] = {
            "source_id": record["disprot_id"], "source_sha256": source_hash,
            "pipeline_commit": commit, "config_sha256": config_hash,
            "software": {"screen_disprot_linker_context": "0.1.0", "python": sys.version.split()[0]},
            "evidence_quality": "screening_only",
        }
    records.sort(key=lambda row: (row["disprot_id"], row["gap"]["start"], row["gap"]["end"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records), encoding="utf-8")
    manifest = {
        "status": "screening_only_not_linker_labels",
        "source_url": "https://disprot.org/api/search?release=2026_06&show_ambiguous=false&show_obsolete=false&format=json&get_consensus=false",
        "source_sha256": source_hash, "config_sha256": config_hash,
        "pipeline_commit": commit, "software": {"screen_disprot_linker_context": "0.1.0", "python": sys.version.split()[0]},
        "source_entries": len(entries),
        "screened_gap_records": len(records),
        "unique_disprot_ids": len({row["disprot_id"] for row in records}),
        "review_status": dict(Counter(row["review_status"] for row in records)),
        "rule": "adjacent non-overlapping Pfam domains with a 5-30 residue gap and at least one overlapping DisProt experimental disorder region",
        "important_limit": "DisProt disorder evidence does not establish a natural interdomain linker; all candidates require domain/linker adjudication and sequence-to-structure mapping.",
    }
    args.output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
