"""Reproduce the annotated-linker discovery count without storing the NRPS CSV.

This is an index-size audit, not a training or functional-validation dataset.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/processed/linker_catalog/unique_sequences.v1.jsonl"
SOURCE_COMMIT = "199d3284f76a2a8aa2fc0c5205b9240571ea8115"
SOURCE_URL = (
    "https://raw.githubusercontent.com/SWFarag/nrps-linker/"
    f"{SOURCE_COMMIT}/files2Read/NCBI_webapp_clean2.csv"
)
AA = set("ACDEFGHIKLMNPQRSTVWY")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    with urllib.request.urlopen(SOURCE_URL, timeout=60) as response:
        raw = response.read()
    decoded = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(decoded))
    required = {"Linker", "Cluster_file", "Assembly_accession"}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError(f"Unexpected NRPS columns: {reader.fieldnames}")
    total_rows = 0
    valid_rows = 0
    nrps = set()
    for row in reader:
        total_rows += 1
        sequence = row["Linker"].strip().upper()
        if sequence and set(sequence) <= AA and row["Cluster_file"] and row["Assembly_accession"]:
            nrps.add(sequence)
            valid_rows += 1

    catalog_bytes = CATALOG.read_bytes()
    catalog = set()
    for line in catalog_bytes.splitlines():
        record = json.loads(line)
        sequence = record["sequence"]
        if not sequence or not sequence.isalpha() or sequence != sequence.upper():
            raise ValueError("Invalid sequence in local catalog")
        catalog.add(sequence)

    union = nrps | catalog
    result = {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "interpretation": "exact unique amino-acid strings across two annotation sources; not function-tested and not train-ready",
        "source_paper": "https://doi.org/10.1093/bioinformatics/btz127",
        "nrps_source_url": SOURCE_URL,
        "nrps_source_commit": SOURCE_COMMIT,
        "nrps_source_sha256": sha256(raw),
        "nrps_total_rows": total_rows,
        "nrps_rows_with_standard_amino_acids_and_accessions": valid_rows,
        "nrps_unique_sequences": len(nrps),
        "catalog_path": str(CATALOG.relative_to(ROOT)).replace("\\", "/"),
        "catalog_sha256": sha256(catalog_bytes),
        "catalog_unique_sequences": len(catalog),
        "exact_overlap": len(nrps & catalog),
        "exact_union_unique_sequences": len(union),
        "threshold_10000_met": len(union) >= 10000,
        "caveats": [
            "NRPS inter-modular linkers are a specialized family, not generic fusion-linker evidence.",
            "NRPS linker boundaries derive from a parser over well-annotated and putative genomic clusters.",
            "The existing catalog mixes DLD, DisProt and protected CAID3 annotations; it is not a homogeneous training set.",
            "Exact deduplication does not remove homologous proteins or resolve label and split leakage.",
            "No individual linker-function assay is implied by this count.",
        ],
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
