"""Validate the annotated linker catalog without inventing segmentation labels.

The input contains linker subsequences, not full-protein 0/1/x masks. This
script makes a versioned, source-tiered inventory and quarantines malformed
records. It deliberately does not mark any record as DFL-detector ready.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/processed/linker_catalog/annotated_only_v1/annotated_linker_sequences.v1.jsonl.gz"
DEFAULT_MANIFEST = ROOT / "data/processed/linker_catalog/annotated_only_v1/manifest.v1.json"
DEFAULT_OUTPUT = ROOT / "data/processed/linker_catalog/training_readiness_v1"
AA = set("ACDEFGHIKLMNPQRSTVWY")
SOURCE_KEYS = {"existing_catalog", "nrps_intermodular", "uniprot_explicit_linker_region"}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_record(record: dict) -> tuple[dict | None, list[str]]:
    errors = []
    sequence = record.get("sequence")
    if not isinstance(sequence, str) or not sequence or set(sequence) - AA:
        errors.append("invalid_sequence")
        sequence = ""
    if record.get("length") != len(sequence):
        errors.append("length_mismatch")
    if record.get("sequence_sha256") != hashlib.sha256(sequence.encode("ascii")).hexdigest():
        errors.append("sequence_hash_mismatch")
    keys = record.get("qualifying_source_keys")
    sources = record.get("qualifying_sources")
    if not isinstance(keys, list) or not keys or len(keys) != len(set(keys)) or set(keys) - SOURCE_KEYS:
        errors.append("invalid_source_keys")
        keys = []
    if not isinstance(sources, dict) or set(keys) != set(sources):
        errors.append("source_key_mismatch")
        sources = {}
    if record.get("usage_status") not in {
        "protected_benchmark", "quarantined", "needs_boundary_and_homology_audit"
    }:
        errors.append("invalid_usage_status")

    uniprot = sources.get("uniprot_explicit_linker_region", {})
    if uniprot:
        start, end = uniprot.get("start_1based"), uniprot.get("end_1based")
        if (not isinstance(start, int) or not isinstance(end, int)
                or start < 1 or end < start or end - start + 1 != len(sequence)
                or not uniprot.get("accession")):
            errors.append("uniprot_coordinate_or_accession_error")
    nrps = sources.get("nrps_intermodular", {})
    if nrps and (not nrps.get("cluster_file") or not nrps.get("assembly_accession")):
        errors.append("nrps_source_id_missing")
    existing = sources.get("existing_catalog", {})
    if existing and not existing.get("observation_ids"):
        errors.append("existing_observation_id_missing")
    if errors:
        return None, errors

    protected = record["usage_status"] == "protected_benchmark"
    quarantine = record["usage_status"] == "quarantined"
    if protected:
        review_tier = "protected_do_not_train"
    elif quarantine:
        review_tier = "quarantine_overlap"
    elif "uniprot_explicit_linker_region" in keys:
        review_tier = "explicit_uniprot_region_pending_homology_and_evidence_review"
    elif "existing_catalog" in keys:
        review_tier = "existing_annotation_pending_homology_and_ontology_review"
    else:
        review_tier = "nrps_intermodular_pending_full_protein_mapping"

    cleaned = {
        "schema_version": "1.0.0",
        "sequence": sequence,
        "sequence_sha256": record["sequence_sha256"],
        "length": len(sequence),
        "qualifying_source_keys": sorted(keys),
        "qualifying_sources": sources,
        "usage_status": record["usage_status"],
        "review_tier": review_tier,
        "annotation_scope": "positive_linker_subsequence_only",
        "full_protein_sequence_in_this_record": False,
        "verified_nonlinker_residues_in_this_record": 0,
        "dfl_segmentation_training_ready": False,
        "reason_not_dfl_training_ready": (
            "Protected benchmark" if protected else
            "Quarantined pending overlap audit" if quarantine else
            "No verified full-protein negative/unknown residue mask or family-separated split"
        ),
        "source_provenance": record["provenance"],
    }
    return cleaned, []


def build(source: Path, source_manifest: Path, output: Path) -> dict:
    upstream = json.loads(source_manifest.read_text(encoding="utf-8"))
    expected_hash = upstream["output_sha256"][source.name]
    actual_hash = file_hash(source)
    if actual_hash != expected_hash:
        raise ValueError("Input SHA-256 differs from annotated-only source manifest")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing audit: {output}")
    output.mkdir(parents=True)
    accepted_path = output / "validated_linker_subsequences.v1.jsonl"
    rejected_path = output / "rejected_records.v1.jsonl"
    seen = set()
    counts = Counter()
    source_counts = Counter()
    reasons = Counter()
    with gzip.open(source, "rt", encoding="utf-8") as raw, accepted_path.open(
        "w", encoding="utf-8", newline="\n"
    ) as accepted, rejected_path.open("w", encoding="utf-8", newline="\n") as rejected:
        for line_number, line in enumerate(raw, 1):
            counts["input_records"] += 1
            try:
                record = json.loads(line)
                cleaned, errors = audit_record(record)
            except (ValueError, TypeError, KeyError) as exc:
                record, cleaned, errors = None, None, [f"parse_or_shape_error:{type(exc).__name__}"]
            if cleaned is not None and cleaned["sequence_sha256"] in seen:
                cleaned, errors = None, ["duplicate_sequence_hash"]
            if cleaned is None:
                counts["rejected_records"] += 1
                reasons.update(errors)
                rejected.write(json.dumps({"line_number": line_number, "errors": errors,
                                           "sequence_sha256": (record or {}).get("sequence_sha256")}) + "\n")
                continue
            seen.add(cleaned["sequence_sha256"])
            counts["validated_records"] += 1
            counts[cleaned["review_tier"]] += 1
            source_counts.update(cleaned["qualifying_source_keys"])
            accepted.write(json.dumps(cleaned, sort_keys=True, separators=(",", ":")) + "\n")

    manifest = {
        "schema_version": "1.0.0", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(source), "source_manifest": str(source_manifest),
        "source_sha256": actual_hash, "source_manifest_sha256": file_hash(source_manifest),
        "script_sha256": file_hash(Path(__file__)),
        "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "counts": dict(sorted(counts.items())), "source_counts_overlapping": dict(sorted(source_counts.items())),
        "rejection_reasons": dict(sorted(reasons.items())),
        "dfl_segmentation_training_ready": 0,
        "outputs_sha256": {accepted_path.name: file_hash(accepted_path),
                           rejected_path.name: file_hash(rejected_path)},
        "warning": "Validated linker subsequences are not full-protein DFL segmentation examples.",
    }
    (output / "manifest.v1.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build(args.input, args.source_manifest, args.output), indent=2))
