"""Extract DisProt's explicit flexible-linker annotations with provenance.

These curated functional annotations are separate from DLD IDL/DDL labels;
they are not automatically an independent test or two-domain linker labels.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys


TERM_ID = "IDPO:0000033"
SOURCE_URL = "https://disprot.org/api/search?release=2026_06&show_ambiguous=false&show_obsolete=false&format=json&get_consensus=false"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def extract(entries: list[dict], provenance: dict) -> list[dict]:
    records = []
    for entry in entries:
        sequence = entry.get("sequence", "").upper()
        for region in entry.get("regions", []):
            if region.get("term_id") != TERM_ID:
                continue
            start, end = region.get("start"), region.get("end")
            if not isinstance(start, int) or not isinstance(end, int) or not 1 <= start <= end <= len(sequence):
                raise ValueError(f"Invalid linker coordinates: {entry.get('disprot_id')}:{region.get('region_id')}")
            records.append({
                "schema_version": "0.1.0", "record_type": "disprot_curated_flexible_linker_annotation",
                "disprot_id": entry["disprot_id"], "uniprot_accession": entry["acc"],
                "region_id": region["region_id"], "sequence": sequence,
                "linker": {"start": start, "end": end, "sequence": sequence[start - 1:end],
                           "length": end - start + 1, "term_id": TERM_ID,
                           "term_name": region.get("term_name")},
                "evidence": {"eco_id": region.get("ec_id"), "reference_id": region.get("reference_id"),
                             "reference_source": region.get("reference_source"),
                             "release": region.get("released"),
                             "curator_id": region.get("curator_id"),
                             "validated_by": (region.get("validated") or {}).get("curator_id")},
                "domain_pair_status": "not_adjudicated", "dld_overlap_status": "not_audited",
                "training_eligibility": "holdout_pending_overlap_audit",
                "provenance": provenance,
            })
    records.sort(key=lambda row: (row["disprot_id"], row["linker"]["start"], row["region_id"]))
    if len({row["region_id"] for row in records}) != len(records):
        raise ValueError("Repeated DisProt region IDs")
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    config = {"term_id": TERM_ID, "release": "2026_06", "exclude_ambiguous": True, "exclude_obsolete": True}
    provenance = {"source_url": SOURCE_URL, "source_sha256": digest(args.input),
                  "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
                  "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                  "software": {"extractor": "0.1.0", "python": sys.version.split()[0]},
                  "evidence_quality": "curated_disprot_function_annotation_not_domain_pair_adjudicated"}
    records = extract(payload["data"], provenance)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in records), encoding="utf-8")
    manifest = {"status": "extracted_pending_overlap_and_domain_pair_audit",
                "source_url": SOURCE_URL, "source_sha256": provenance["source_sha256"],
                "config_sha256": provenance["config_sha256"], "pipeline_commit": provenance["pipeline_commit"],
                "regions": len(records), "proteins": len({row["disprot_id"] for row in records}),
                "length_5_to_30": sum(5 <= row["linker"]["length"] <= 30 for row in records),
                "evidence_codes": dict(Counter(row["evidence"]["eco_id"] for row in records)),
                "not_independent_test_until_overlap_audit": True}
    args.output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
