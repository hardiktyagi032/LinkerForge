"""Create an unchanged-score common-target CAID3 Linker subset for seven baselines."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from audit_caid3_dld_overlap import caid_records, sha256


def blocks(path: Path) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    current: str | None = None
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if line.startswith(">"):
                current = line[1:].strip()
                if current in result:
                    raise ValueError(f"Duplicate target {current} in {path}")
                result[current] = [line]
            elif current is not None:
                result[current].append(line)
            elif line.strip():
                raise ValueError(f"Prediction precedes header in {path}")
    return result


def fully_scored(block: list[str], sequence: str) -> bool:
    rows = [line.split() for line in block[1:] if line.strip()]
    if len(rows) != len(sequence):
        return False
    try:
        return all(int(row[0]) == index and row[1] == residue and
                   0 <= float(row[2]) <= 1
                   for index, (row, residue) in enumerate(zip(rows, sequence), start=1))
    except (ValueError, IndexError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError("Common-coverage output directory must be empty")
    reference = caid_records(args.reference)
    if len(reference) != 31:
        raise ValueError("Expected 31 CAID3 Linker proteins")
    sources = sorted(args.predictions.glob("*.caid"))
    expected_names = {"APOD", "DFLpred", "DisoFLAG-DFL", "IPA-AF2-Linker",
                      "LINKER-Pred-Lite", "LINKER-Pred", "LINKER-Pred2"}
    if {path.stem for path in sources} != expected_names:
        raise ValueError("Expected seven specified CAID3 method files")
    method_blocks = {path.stem: blocks(path) for path in sources}
    reference_map = {name: (sequence, labels) for name, sequence, labels in reference}
    coverage = {
        method: {name for name, (sequence, _) in reference_map.items()
                 if name in file_blocks and fully_scored(file_blocks[name], sequence)}
        for method, file_blocks in method_blocks.items()
    }
    common = set(reference_map).intersection(*coverage.values())
    if len(common) < 1:
        raise ValueError("No full-residue common target")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reference_output = args.output_dir / "linker-common.fasta"
    with reference_output.open("w", encoding="utf-8") as stream:
        for name, sequence, labels in reference:
            if name in common:
                stream.write(f">{name}\n{sequence}\n{labels}\n")
    predictions_output = args.output_dir / "predictions"
    predictions_output.mkdir()
    for method, file_blocks in method_blocks.items():
        with (predictions_output / f"{method}.caid").open("w", encoding="utf-8") as stream:
            for name, _, _ in reference:
                if name in common:
                    stream.writelines(file_blocks[name])
    config = {"methods": sorted(expected_names), "coverage": "full_residue_score_and_sequence_match"}
    root = Path(__file__).resolve().parents[1]
    report = {
        "schema_version": "0.1.0", "status": "common_target_subset_not_independent_test",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "reference_sha256": sha256(args.reference),
        "prediction_sha256": {path.name: sha256(path) for path in sources},
        "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "script_sha256": sha256(Path(__file__)),
        "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
        "software": {"python": sys.version.split()[0]},
        "common_proteins": sorted(common),
        "common_reference_sha256": sha256(reference_output),
        "methods": {name: {"full_residue_covered_proteins": len(covered),
                            "missing_or_partial_ids": sorted(set(reference_map) - covered)}
                    for name, covered in coverage.items()},
        "output_dir": str(args.output_dir.resolve().relative_to(root)),
        "limitations": [
            "This is a retrospective public-CAID3 reanalysis, not independent model selection.",
            "Common coverage is computed for these seven archived submissions only; later methods are absent.",
            "CAID3 contains only linker-positive proteins; no-linker specificity is unavailable."
        ]
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"common_proteins": len(common),
                      "method_coverage": {name: len(rows) for name, rows in coverage.items()}}), flush=True)


if __name__ == "__main__":
    main()
