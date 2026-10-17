"""Merge explicit UniProt 'Linker' REGION features into a discovery index.

Feature annotation and ECO evidence are preserved; neither implies a measured
biophysical function unless the cited experiment is reviewed separately.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
AA = set("ACDEFGHIKLMNPQRSTVWY")
FEATURE = re.compile(r"REGION\s+(\d+)\.\.(\d+)")
NOTE = re.compile(r'/note="([^"]+)"')
EVIDENCE = re.compile(r'/evidence="([^"]+)"')


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def linker_regions(text: str, sequence: str):
    matches = list(FEATURE.finditer(text))
    for i, match in enumerate(matches):
        annotation = text[match.end():matches[i + 1].start() if i + 1 < len(matches) else None]
        note = NOTE.search(annotation)
        if note is None or "linker" not in note.group(1).lower():
            continue
        start, end = map(int, match.groups())
        if not 1 <= start <= end <= len(sequence):
            continue
        segment = sequence[start - 1:end]
        if segment and set(segment) <= AA:
            evidence = EVIDENCE.search(annotation)
            yield start, end, segment, note.group(1), evidence.group(1) if evidence else ""


def build(prior_index: Path, out: Path) -> dict:
    query = urllib.parse.urlencode({"query": "ft_region:linker", "format": "tsv",
                                    "fields": "accession,sequence,ft_region"})
    url = "https://rest.uniprot.org/uniprotkb/stream?" + query
    retrieved_at = datetime.now(timezone.utc).isoformat()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                            text=True, check=True).stdout.strip()
    raw_hash = hashlib.sha256()
    with tempfile.NamedTemporaryFile(prefix="linkerforge-regions-", suffix=".tsv",
                                     delete=False) as temp:
        temp_path = Path(temp.name)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "LinkerForge research audit"})
            with urllib.request.urlopen(req, timeout=180) as response:
                while block := response.read(1024 * 1024):
                    raw_hash.update(block)
                    temp.write(block)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise
    out.mkdir(parents=True, exist_ok=True)
    observations = out / "uniprot_explicit_linker_regions.v1.jsonl.gz"
    unique = out / "unique_discovery_sequences.v1.jsonl.gz"
    merged: dict[str, dict] = {}
    with gzip.open(prior_index, "rt", encoding="utf-8") as prior:
        for line in prior:
            row = json.loads(line)
            merged[row["sequence"]] = row["sources"]
    counts = {"rows": 0, "annotated_linker_observations": 0,
              "pubmed_supported_observations": 0, "proteins_with_linkers": 0}
    try:
        csv.field_size_limit(10_000_000)
        with temp_path.open("r", encoding="utf-8-sig", newline="") as raw, gzip.open(
                observations, "wt", encoding="utf-8", newline="\n") as output:
            reader = csv.DictReader(raw, delimiter="\t")
            if not {"Entry", "Sequence", "Region"}.issubset(reader.fieldnames or []):
                raise ValueError(f"Unexpected UniProt fields: {reader.fieldnames}")
            for row in reader:
                counts["rows"] += 1
                accession = row["Entry"].strip()
                sequence = row["Sequence"].strip().upper()
                if not accession or not sequence:
                    continue
                found = False
                for start, end, segment, note, evidence in linker_regions(row["Region"], sequence):
                    found = True
                    pubmed = "ECO:0000269|PubMed:" in evidence
                    tier = ("explicit_linker_region_with_pubmed_evidence" if pubmed
                            else "explicit_linker_region_annotation")
                    record = {"schema_version": "1.0.0", "source": "UniProtKB_Region_Linker",
                              "accession": accession, "start_1based": start,
                              "end_1based": end, "sequence": segment, "note": note,
                              "evidence": evidence, "evidence_tier": tier,
                              "provenance": {"source_url": url,
                                             "source_sha256": raw_hash.hexdigest(),
                                             "pipeline_commit": commit,
                                             "pipeline_sha256": sha256_file(Path(__file__)),
                                             "retrieved_at_utc": retrieved_at}}
                    output.write(json.dumps(record, separators=(",", ":")) + "\n")
                    counts["annotated_linker_observations"] += 1
                    counts["pubmed_supported_observations"] += int(pubmed)
                    merged.setdefault(segment, {}).setdefault("uniprot_explicit_linker_region", {
                        "accession": accession, "start_1based": start, "end_1based": end,
                        "note": note, "evidence": evidence, "evidence_tier": tier})
                counts["proteins_with_linkers"] += int(found)
    finally:
        temp_path.unlink(missing_ok=True)
    with gzip.open(unique, "wt", encoding="utf-8", newline="\n") as output:
        for sequence, sources in sorted(merged.items()):
            output.write(json.dumps({"sequence": sequence, "sources": sources},
                                    separators=(",", ":")) + "\n")
    manifest = {"schema_version": "1.0.0", "retrieved_at_utc": retrieved_at,
                "source_url": url, "source_sha256": raw_hash.hexdigest(),
                "pipeline_commit": commit, "pipeline_sha256": sha256_file(Path(__file__)),
                "prior_index_sha256": sha256_file(prior_index), "counts": counts,
                "explicit_linker_region_unique": sum(
                    "uniprot_explicit_linker_region" in sources for sources in merged.values()),
                "exact_union_unique": len(merged),
                "output_sha256": {observations.name: sha256_file(observations),
                                  unique.name: sha256_file(unique)},
                "warning": "Explicit region annotation, not guaranteed measured linker function; benchmark entries remain protected."}
    (out / "manifest.v1.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prior-index", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.prior_index, args.out), indent=2))
