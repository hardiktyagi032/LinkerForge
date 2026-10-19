"""Prepare DisoFLAG's published training IDR track for a DFL transfer pilot.

Conservatively excludes exact and candidate local-homology matches to every
published DFL split and CAID3. This is a development pilot, not certified
independence or a reproduction of TransDFL's 2,645-protein pretraining corpus.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import parasail

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/disoflag/train_data.txt"
DFL = ROOT / "data/processed/published_dfl_splits"
CAID = ROOT / "artifacts/caid3-linker.fasta"
OUTPUT = ROOT / "data/processed/disorder_transfer_pilot_v1"
CONFIG = {"identity_min": 0.30, "aligned_length_min": 50,
          "shorter_sequence_coverage_min": 0.50,
          "aligner": "parasail.sw_stats_striped_16 BLOSUM62 gap_open=10 gap_extend=1",
          "policy": "exclude any candidate local-homology match; no unannotated residue relabeling"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_nine_lines(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) % 9:
        raise ValueError("DisoFLAG source is not nine-line records")
    result = []
    for at in range(0, len(lines), 9):
        block = lines[at:at + 9]
        if not block[0].startswith(">") or len({len(x) for x in block[1:]}) != 1:
            raise ValueError(f"Malformed DisoFLAG record at line {at + 1}")
        if set(block[2]) - {"0", "1"}:
            raise ValueError("Unexpected IDR label")
        result.append({"protein_id": block[0][1:].split()[0], "sequence": block[1].upper(),
                       "labels": block[2]})
    return result


def protected() -> list[dict]:
    records = []
    for name in ("tr166", "te82", "te64"):
        for line in (DFL / f"{name}.jsonl").read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            records.append({"protein_id": record["protein_id"], "sequence": record["sequence"].upper(),
                            "source": name.upper()})
    current_id, pieces = None, []
    for line in CAID.read_text(encoding="utf-8").splitlines():
        if line.startswith(">"):
            if current_id is not None:
                records.append({"protein_id": current_id, "sequence": "".join(pieces).upper(), "source": "CAID3"})
            current_id, pieces = line[1:].split()[0], []
        else:
            pieces.append(line.strip())
    if current_id is not None:
        records.append({"protein_id": current_id, "sequence": "".join(pieces).upper(), "source": "CAID3"})
    return records


def build(output: Path = OUTPUT) -> dict:
    items, guards = parse_nine_lines(SOURCE), protected()
    source_hashes = {str(p.relative_to(ROOT)): sha(p) for p in [SOURCE, CAID, *sorted(DFL.glob("*.jsonl"))]}
    config_hash = hashlib.sha256(json.dumps(CONFIG, sort_keys=True).encode()).hexdigest()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    guard_ids = {r["protein_id"] for r in guards}
    guard_sequences = {r["sequence"] for r in guards}
    repeated = Counter(r["sequence"] for r in items)
    retained, excluded = [], []
    scored = 0
    for item in items:
        reason = None
        if item["protein_id"] in guard_ids or item["sequence"] in guard_sequences:
            reason = "protected_exact_id_or_sequence"
        elif repeated[item["sequence"]] > 1:
            reason = "duplicate_auxiliary_sequence"
        else:
            for guard in guards:
                alignment = parasail.sw_stats_striped_16(item["sequence"], guard["sequence"],
                                                         10, 1, parasail.blosum62)
                scored += 1
                if (alignment.length >= CONFIG["aligned_length_min"] and
                        alignment.length / min(len(item["sequence"]), len(guard["sequence"])) >= CONFIG["shorter_sequence_coverage_min"] and
                        alignment.matches / max(alignment.length, 1) >= CONFIG["identity_min"]):
                    reason = "candidate_protected_local_homology"
                    break
        record = {"schema_version": "1.0.0", "source": "DisoFLAG_train_line3_IDR",
                  "protein_id": item["protein_id"], "sequence": item["sequence"],
                  "labels": item["labels"], "task": "intrinsic_disorder_auxiliary",
                  "status": "excluded" if reason else "eligible_for_development_pilot",
                  "reason": reason, "provenance": {"source_sha256": sha(SOURCE),
                  "source_url": "https://github.com/YihePang/DisoFLAG/blob/main/dataset/train_data.txt",
                  "pipeline_commit": commit, "config_hash": config_hash,
                  "software": {"python": sys.version.split()[0], "parasail": parasail.__version__}}}
        (excluded if reason else retained).append(record)
    output.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, values in (("pretrain", retained), ("excluded", excluded)):
        path = output / f"{name}.jsonl"
        path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in values), encoding="utf-8")
        paths[name] = {"records": len(values), "sha256": sha(path),
                       "positive_residues": sum(row["labels"].count("1") for row in values),
                       "negative_residues": sum(row["labels"].count("0") for row in values)}
    manifest = {"schema_version": "1.0.0", "status": "development_pilot_not_homology_certified",
                "source": "DisoFLAG published train line 3 IDR labels", "source_sha256": source_hashes,
                "config": CONFIG, "config_hash": config_hash, "pipeline_commit": commit,
                "protected_records": len(guards), "alignments_scored": scored, "files": paths,
                "exclusion_reasons": dict(Counter(r["reason"] for r in excluded)),
                "limitations": ["Local-alignment screen is a conservative candidate filter, not a family clustering certificate.",
                                "DisoFLAG IDR zero semantics follow its published source; this is not TransDFL's original IDR corpus.",
                                "TE82 is previously viewed development; TE64/CAID3 must not guide model selection."]}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = build(args.output_dir)
    print(json.dumps({"eligible": result["files"]["pretrain"]["records"],
                      "excluded": result["files"]["excluded"]["records"],
                      "alignments_scored": result["alignments_scored"]}))


if __name__ == "__main__":
    main()
