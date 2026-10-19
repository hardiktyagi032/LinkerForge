"""Build a tiered discovery index, never a train-ready linker label set."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/uniprot_domain_gap_catalog_v1.json"
BASE = ROOT / "data/processed/linker_catalog/unique_sequences.v1.jsonl"
OUT = ROOT / "data/processed/linker_catalog/expanded_v1"
NRPS_COMMIT = "199d3284f76a2a8aa2fc0c5205b9240571ea8115"
NRPS_URL = ("https://raw.githubusercontent.com/SWFarag/nrps-linker/"
            f"{NRPS_COMMIT}/files2Read/NCBI_webapp_clean2.csv")
AA = set("ACDEFGHIKLMNPQRSTVWY")
DOMAIN = re.compile(r"DOMAIN\s+(\d+)\.\.(\d+)")
RANGE = re.compile(r"(?:REPEAT|TRANSMEM)\s+(\d+)\.\.(\d+)")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def domains(feature_text: str) -> list[dict]:
    hits = list(DOMAIN.finditer(feature_text))
    result = []
    for i, hit in enumerate(hits):
        start, end = map(int, hit.groups())
        tail = feature_text[hit.end():hits[i + 1].start() if i + 1 < len(hits) else None]
        result.append({"start_1based": start, "end_1based": end,
                       "annotation": tail.strip(" ;")[:400]})
    return sorted(result, key=lambda item: (item["start_1based"], item["end_1based"]))


def blocked_ranges(*feature_texts: str) -> list[tuple[int, int]]:
    return [tuple(map(int, hit.groups())) for text in feature_texts for hit in RANGE.finditer(text)]


def candidates(sequence: str, feature_text: str, blocked: list[tuple[int, int]],
               min_gap: int, max_gap: int):
    ds = domains(feature_text)
    for left, right in zip(ds, ds[1:]):
        start, end = left["end_1based"] + 1, right["start_1based"] - 1
        length = end - start + 1
        if (left["start_1based"] < 1 or right["end_1based"] > len(sequence)
                or left["end_1based"] >= right["start_1based"]
                or not min_gap <= length <= max_gap):
            continue
        if any(other is not left and other is not right
               and other["start_1based"] <= end and other["end_1based"] >= start
               for other in ds):
            continue
        if any(a <= end and b >= start for a, b in blocked):
            continue
        segment = sequence[start - 1:end]
        if set(segment) <= AA:
            yield start, end, segment, left, right


def source_url(config: dict) -> str:
    params = urllib.parse.urlencode({"query": config["source_query"],
                                     "format": "tsv", "fields": config["source_fields"]})
    return "https://rest.uniprot.org/uniprotkb/stream?" + params


def build(out: Path = OUT, limit: int | None = None, config_path: Path = CONFIG,
          prior_index: Path | None = None) -> dict:
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    source_key = config["source_key"]
    retrieved_at = datetime.now(timezone.utc).isoformat()
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.strip()
    url = source_url(config)
    raw_hasher = hashlib.sha256()
    with tempfile.NamedTemporaryFile(prefix="linkerforge-uniprot-", suffix=".tsv",
                                     delete=False) as temp:
        temp_path = Path(temp.name)
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "LinkerForge research audit"})
            with urllib.request.urlopen(request, timeout=180) as response:
                source_headers = dict(response.headers.items())
                while chunk := response.read(1024 * 1024):
                    raw_hasher.update(chunk)
                    temp.write(chunk)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise

    out.mkdir(parents=True, exist_ok=True)
    obs_path = out / "uniprot_domain_gap_candidates.v1.jsonl.gz"
    unique_path = out / "unique_discovery_sequences.v1.jsonl.gz"
    summary_path = out / "manifest.v1.json"
    sequence_sources: dict[str, dict[str, dict]] = {}
    if prior_index is not None:
        with gzip.open(prior_index, "rt", encoding="utf-8") as prior:
            for line in prior:
                row = json.loads(line)
                sequence_sources[row["sequence"]] = row["sources"]
    stats = {"uniprot_rows": 0, "uniprot_candidate_observations": 0,
             "uniprot_proteins_with_candidates": 0}
    try:
        csv.field_size_limit(10_000_000)
        with temp_path.open("r", encoding="utf-8-sig", newline="") as raw, gzip.open(
                obs_path, "wt", encoding="utf-8", newline="\n") as obs_out:
            reader = csv.DictReader(raw, delimiter="\t")
            required = {"Entry", "Sequence", "Domain [FT]", "Repeat", "Transmembrane"}
            if not required.issubset(reader.fieldnames or []):
                raise ValueError(f"Unexpected UniProt columns: {reader.fieldnames}")
            for row in reader:
                stats["uniprot_rows"] += 1
                if limit is not None and stats["uniprot_rows"] > limit:
                    break
                seq = row["Sequence"].strip().upper()
                accession = row["Entry"].strip()
                if not accession or not seq or not set(seq) <= AA:
                    continue
                blocked = blocked_ranges(row["Repeat"], row["Transmembrane"])
                found = False
                for start, end, segment, left, right in candidates(
                        seq, row["Domain [FT]"], blocked,
                        config["min_gap_residues"], config["max_gap_residues"]):
                    found = True
                    record = {"schema_version": "1.0.0",
                              "source": config["source_name"],
                              "accession": accession, "start_1based": start,
                              "end_1based": end, "sequence": segment,
                              "left_domain": left, "right_domain": right,
                              "evidence_tier": config["evidence_tier"],
                              "provenance": {"source_url": url,
                                             "source_sha256": raw_hasher.hexdigest(),
                                             "config_sha256": digest(config_bytes),
                                             "pipeline_commit": sha,
                                             "pipeline_sha256": file_digest(Path(__file__)),
                                             "retrieved_at_utc": retrieved_at}}
                    obs_out.write(json.dumps(record, separators=(",", ":")) + "\n")
                    stats["uniprot_candidate_observations"] += 1
                    sequence_sources.setdefault(segment, {}).setdefault(source_key, {
                        "accession": accession, "start_1based": start,
                        "end_1based": end, "evidence_tier": config["evidence_tier"]})
                stats["uniprot_proteins_with_candidates"] += int(found)
    finally:
        temp_path.unlink(missing_ok=True)

    base_bytes = BASE.read_bytes()
    for line in base_bytes.splitlines():
        row = json.loads(line)
        sequence_sources.setdefault(row["sequence"], {}).setdefault("existing_catalog", {
            "observation_ids": row["observation_ids"],
            "sources": row["sources"], "usage_statuses": row["usage_statuses"]})

    with urllib.request.urlopen(NRPS_URL, timeout=60) as response:
        nrps_bytes = response.read()
    nrps_valid = 0
    for row in csv.DictReader(io.StringIO(nrps_bytes.decode("utf-8-sig"))):
        seq = row["Linker"].strip().upper()
        if seq and set(seq) <= AA and row["Cluster_file"] and row["Assembly_accession"]:
            nrps_valid += 1
            sequence_sources.setdefault(seq, {}).setdefault("nrps_intermodular", {
                "cluster_file": row["Cluster_file"],
                "assembly_accession": row["Assembly_accession"],
                "evidence_tier": "parsed_genomic_intermodular_linker"})

    all_source_keys = sorted({key for records in sequence_sources.values() for key in records})
    source_counts = {source: sum(source in records for records in sequence_sources.values())
                     for source in all_source_keys}
    with gzip.open(unique_path, "wt", encoding="utf-8", newline="\n") as handle:
        for seq, records in sorted(sequence_sources.items()):
            handle.write(json.dumps({"sequence": seq, "sources": records},
                                    separators=(",", ":")) + "\n")
    manifest = {"schema_version": "1.0.0", "retrieved_at_utc": retrieved_at,
                "uniprot_url": url, "uniprot_response_headers": {
                    key: source_headers.get(key) for key in
                    ("x-uniprot-release", "last-modified", "etag", "x-total-results")},
                "uniprot_raw_sha256": raw_hasher.hexdigest(),
                "nrps_url": NRPS_URL, "nrps_raw_sha256": digest(nrps_bytes),
                "base_catalog_sha256": digest(base_bytes),
                "config_sha256": digest(config_bytes), "pipeline_commit": sha,
                "pipeline_sha256": file_digest(Path(__file__)),
                "prior_index_sha256": file_digest(prior_index) if prior_index is not None else None,
                "stats": stats, "nrps_valid_rows": nrps_valid,
                "exact_unique_by_source": source_counts,
                "exact_union_unique": len(sequence_sources),
                "threshold_50000_met": len(sequence_sources) >= 50000,
                "threshold_100000_met": len(sequence_sources) >= 100000,
                "output_sha256": {obs_path.name: file_digest(obs_path),
                                  unique_path.name: file_digest(unique_path)},
                "warning": "Discovery index only. UniProt domain gaps are inferred candidates, not confirmed linkers or training positives. Existing CAID3 benchmark members remain protected."}
    summary_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--prior-index", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None,
                        help="Smoke-test limit; never interpret as a full-dataset count")
    args = parser.parse_args()
    print(json.dumps(build(args.out, args.limit, args.config, args.prior_index), indent=2))
