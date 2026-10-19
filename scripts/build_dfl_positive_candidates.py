"""Build positive/unknown DisProt candidates, not a trainable dataset."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/processed/disprot_2026_06_flexible_linkers.jsonl"
CAID = ROOT / "artifacts/caid3-linker.fasta"
SPLITS = {name: ROOT / f"data/processed/published_dfl_splits/{name}.jsonl"
          for name in ("tr166", "te82", "te64")}
SCHEMA = ROOT / "schemas/dfl_positive_candidate_v0.1.0.schema.json"
OUTPUT = ROOT / "data/processed/dfl_positive_candidates_2026_10_12.jsonl"
MANIFEST = ROOT / "data/processed/dfl_positive_candidates_2026_10_12.manifest.json"
CONFIG = {"source": "DisProt_2026_06_curated_flexible_linker", "positive_term_id": "IDPO:0000033",
          "excluded_exact_ids": ["TR166", "TE82", "TE64", "CAID3"],
          "nonpositive_label": "x_masked_unknown", "training_eligibility": "pending_homology_audit"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUTPUT.exists() or MANIFEST.exists():
        raise FileExistsError("Candidate output already exists")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    groups = {}
    for line in SOURCE.read_text(encoding="utf-8").splitlines():
        region = json.loads(line)
        if region["linker"]["term_id"] != CONFIG["positive_term_id"]:
            raise ValueError("Unexpected annotation term")
        groups.setdefault(region["disprot_id"], []).append(region)
    protected = {}
    for name, path in SPLITS.items():
        protected[name] = {json.loads(line)["protein_id"] for line in path.read_text(encoding="utf-8").splitlines()}
    protected["caid3"] = {line[1:].strip().split()[0] for line in CAID.read_text(encoding="utf-8").splitlines()
                          if line.startswith(">")}
    excluded = set().union(*protected.values())
    config_hash = hashlib.sha256(json.dumps(CONFIG, sort_keys=True).encode()).hexdigest()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    provenance = {"source_url": "https://disprot.org/api/search?release=2026_06&show_ambiguous=false&show_obsolete=false&format=json&get_consensus=false",
                  "source_sha256": sha(SOURCE), "script_sha256": sha(Path(__file__)),
                  "config_sha256": config_hash, "pipeline_commit": commit,
                  "software": {"python": sys.version.split()[0], "jsonschema": jsonschema.__version__}}
    records = []
    for protein_id, regions in sorted(groups.items()):
        if protein_id in excluded:
            continue
        sequences = {r["sequence"] for r in regions}
        if len(sequences) != 1:
            raise ValueError(f"Sequence mismatch within {protein_id}")
        sequence = sequences.pop()
        if set(sequence) - set("ACDEFGHIKLMNPQRSTVWYX"):
            raise ValueError(f"Unsupported amino acid in {protein_id}")
        labels = ["x"] * len(sequence)
        spans = []
        seen_regions = set()
        for item in sorted(regions, key=lambda r: (r["linker"]["start"], r["region_id"])):
            linker = item["linker"]
            start, end = linker["start"], linker["end"]
            if not (1 <= start <= end <= len(sequence)) or sequence[start - 1:end] != linker["sequence"]:
                raise ValueError(f"Coordinate/sequence mismatch: {item['region_id']}")
            if item["region_id"] in seen_regions:
                continue
            seen_regions.add(item["region_id"])
            labels[start - 1:end] = ["1"] * (end - start + 1)
            spans.append({"region_id": item["region_id"], "start_1based": start, "end_1based": end,
                          "reference_id": str(item["evidence"]["reference_id"]),
                          "eco_id": item["evidence"]["eco_id"], "release": item["evidence"]["release"],
                          "evidence_quality": "curated_disprot_flexible_linker_region_not_independent_domain_pair_adjudication"})
        record = {"schema_version": "0.1.0", "record_type": "disprot_dfl_positive_candidate",
                  "protein_id": protein_id, "sequence": sequence, "labels": "".join(labels),
                  "positive_regions": spans,
                  "training_eligibility": "candidate_pending_homology_and_annotation_audit",
                  "provenance": provenance}
        jsonschema.validate(record, schema)
        if len(record["sequence"]) != len(record["labels"]):
            raise AssertionError("Label alignment failure")
        records.append(record)
    OUTPUT.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records), encoding="utf-8")
    manifest = {"schema_version": "0.1.0", "status": "positive_unknown_candidates_not_trainable",
                "records": len(records), "regions": sum(len(r["positive_regions"]) for r in records),
                "positive_residues": sum(r["labels"].count("1") for r in records),
                "unknown_residues": sum(r["labels"].count("x") for r in records),
                "negative_residues": 0,
                "exact_id_exclusion_counts": {name: len(ids & set(groups)) for name, ids in protected.items()},
                "output_sha256": sha(OUTPUT), "source_sha256": sha(SOURCE),
                "schema_sha256": sha(SCHEMA), "script_sha256": sha(Path(__file__)),
                "config_sha256": config_hash, "pipeline_commit": commit,
                "required_before_training": ["homology/domain-family overlap audit against all protected sets and within candidates",
                                             "annotation/sequence-release mapping audit", "frozen family-aware development split",
                                             "matched baseline and new model on the same additional data"]}
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("status", "records", "regions", "positive_residues", "unknown_residues", "negative_residues")}, indent=2))


if __name__ == "__main__":
    main()
