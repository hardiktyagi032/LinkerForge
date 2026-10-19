"""Build a provenance-preserving index of *annotated* linker spans.

This is a catalog, not a train-ready dataset. Exact sequence deduplication does
not remove repeated observations, resolve label conflicts, or prevent leakage.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/linker_catalog_2026-10-12.json"
OUT = ROOT / "data/processed/linker_catalog"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def lines(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def runs(labels, target):
    start = None
    for i, label in enumerate(list(labels) + [None], 1):
        if label == target and start is None:
            start = i
        elif label != target and start is not None:
            yield start, i - 1
            start = None


def commit_sha():
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True, check=True)
    return result.stdout.strip()


def build(config_path: Path = CONFIG, out: Path = OUT):
    config_path = config_path.resolve()
    raw_config = config_path.read_bytes()
    config = json.loads(raw_config)
    config_hash = digest(raw_config)
    sha = commit_sha()
    observations = []
    inputs = {}

    def source(path):
        path = (ROOT / path).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        if not path.is_relative_to(ROOT):
            raise ValueError("Input outside repository")
        inputs[str(path.relative_to(ROOT)).replace("\\", "/")] = file_digest(path)
        return path

    def add(name, source_id, full, start, end, label, status, quality, url, input_hash):
        full = full.upper()
        assert 1 <= start <= end <= len(full), (name, source_id, start, end)
        seq = full[start - 1:end]
        assert seq.isalpha() and seq.isupper()
        obs_id = f"{name}:{source_id}:{start}-{end}:{label}"
        observations.append({"schema_version": "1.0.0", "observation_id": obs_id,
            "source": name, "source_record_id": str(source_id),
            "protein_sequence_sha256": digest(full.encode()),
            "start_1based": start, "end_1based": end, "sequence": seq,
            "sequence_sha256": digest(seq.encode()), "label": label,
            "usage_status": status, "evidence_quality": quality,
            "provenance": {"source_url": url, "input_sha256": input_hash,
                           "config_sha256": config_hash, "pipeline_commit": sha,
                           "software": {"catalog_builder": "1.0.0", "python": sys.version.split()[0]}}})

    p = source(config["sources"]["disprot"])
    for row in lines(p):
        region = row["linker"]
        start, end = int(region["start"]), int(region["end"])
        assert row["sequence"][start - 1:end].upper() == region["sequence"].upper()
        add("DisProt_2026_06", row["region_id"], row["sequence"], start, end,
            "curated_flexible_linker", "quarantine_pending_overlap_audit",
            row["provenance"]["evidence_quality"], row["provenance"]["source_url"], inputs[str(p.relative_to(ROOT)).replace("\\", "/")])

    for path in config["sources"]["dld"]:
        p = source(path)
        ihash = inputs[str(p.relative_to(ROOT)).replace("\\", "/")]
        for row in lines(p):
            full = row["sequence"]
            labels = row["labels"]
            assert len(full) == len(labels)
            for value, name in [(1, "independent_domain_linker"), (2, "dependent_domain_linker")]:
                for start, end in runs(labels, value):
                    status = "protected_blind" if row["split"] == "blind" else "development_split"
                    add("DLD", row["source_id"], full, start, end, name, status,
                        row["evidence_quality"], row["provenance"]["source_url"], ihash)

    p = source(config["sources"]["caid3"])
    ihash = inputs[str(p.relative_to(ROOT)).replace("\\", "/")]
    content = [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(content) % 3 == 0
    for i in range(0, len(content), 3):
        ident, full, labels = content[i:i + 3]
        assert ident.startswith(">") and len(full) == len(labels) and set(labels) <= {"0", "1"}
        for start, end in runs(labels, "1"):
            add("CAID3_Linkers", ident[1:], full, start, end,
                "caid3_disordered_flexible_linker", "protected_benchmark_only",
                "official_benchmark_reference_not_training", "https://github.com/BioComputingUP/caid-reference", ihash)

    ids = [row["observation_id"] for row in observations]
    assert len(ids) == len(set(ids)), "Duplicate observation identifier"
    grouped = defaultdict(list)
    for row in observations:
        grouped[row["sequence_sha256"]].append(row)
    unique = []
    for key, group in grouped.items():
        seq = group[0]["sequence"]
        assert all(row["sequence"] == seq for row in group)
        unique.append({"schema_version": "1.0.0", "sequence": seq,
            "sequence_sha256": key, "length": len(seq),
            "observation_ids": sorted(row["observation_id"] for row in group),
            "sources": sorted({row["source"] for row in group}),
            "labels": sorted({row["label"] for row in group}),
            "usage_statuses": sorted({row["usage_status"] for row in group})})
    observations.sort(key=lambda row: row["observation_id"])
    unique.sort(key=lambda row: row["sequence_sha256"])
    out.mkdir(parents=True, exist_ok=True)
    observation_path = out / "observations.v1.jsonl"
    unique_path = out / "unique_sequences.v1.jsonl"
    for path, rows in [(observation_path, observations), (unique_path, unique)]:
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    manifest = {"schema_version": "1.0.0", "pipeline_commit": sha,
        "config_sha256": config_hash, "inputs_sha256": inputs,
        "outputs_sha256": {p.name: file_digest(p) for p in (observation_path, unique_path)},
        "observation_count": len(observations), "unique_sequence_count": len(unique),
        "observations_by_source": dict(Counter(row["source"] for row in observations)),
        "observations_by_label": dict(Counter(row["label"] for row in observations)),
        "unique_with_multiple_sources": sum(len(row["sources"]) > 1 for row in unique),
        "unique_with_multiple_labels": sum(len(row["labels"]) > 1 for row in unique),
        "protected_unique_sequences": sum(any(s.startswith("protected_") for s in row["usage_statuses"]) for row in unique),
        "unavailable_sources": config["unavailable_sources"],
        "warning": "Not train-ready. Exact dedup does not resolve homology, overlap, label ontology, licensing, or negative/unknown semantics."}
    (out / "manifest.v1.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    print(json.dumps(build(args.config, args.out), indent=2))
