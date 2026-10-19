#!/usr/bin/env python3
"""Validate the curated linker property library, fit the rigidity classifier,
and emit a provenance-bearing JSON record.

Usage:
    python scripts/build_linker_property_report.py [--out PATH]

Standard library only, by design: the repository commits no backend
environment (see AGENTS.md), so this must run on a clean clone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from linkerforge.properties import (  # noqa: E402
    call_cleavability,
    fit_rigidity_model,
    leave_one_out_report,
    load_library,
    modelling_subset,
)
from linkerforge.properties.cleavability import build_motif_table  # noqa: E402

LIBRARY_PATH = REPO_ROOT / "data" / "curated" / "linker_property_library_sources.v1.json"
SCHEMA_PATH = REPO_ROOT / "schemas" / "linker_property_library.v1.schema.json"
DEFAULT_OUT = REPO_ROOT / "reports" / "linker_property_library_2026-10-17.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def coverage_matrix(library) -> Dict[str, Any]:
    """Count entries in each cell of the rigidity x cleavability grid.

    ``unassigned`` is reported as its own row and column rather than folded
    into a label, because the whole point of the coverage question is how much
    of the grid the literature actually populates.
    """
    rig_labels = ["rigid", "flexible", "unassigned"]
    clv_labels = ["cleavable", "non_cleavable", "unassigned"]
    grid = {r: {c: [] for c in clv_labels} for r in rig_labels}
    for entry in library.entries:
        grid[entry.rigidity_label][entry.cleavability_label].append(entry.entry_id)
    return {
        "counts": {r: {c: len(ids) for c, ids in row.items()} for r, row in grid.items()},
        "entry_ids": grid,
    }


def basis_audit(library) -> Dict[str, Any]:
    """How many labels are source-stated versus inferred by this project."""
    out: Dict[str, Dict[str, int]] = {"rigidity": {}, "cleavability": {}}
    for entry in library.entries:
        out["rigidity"][entry.rigidity_basis] = (
            out["rigidity"].get(entry.rigidity_basis, 0) + 1
        )
        out["cleavability"][entry.cleavability_basis] = (
            out["cleavability"].get(entry.cleavability_basis, 0) + 1
        )
    return out


def self_check_cleavability(library) -> Dict[str, Any]:
    """Run the motif caller over every entry that has a sequence.

    This is a consistency check, not an evaluation: the motifs come from these
    very entries, so a cleavable entry matching itself is guaranteed and proves
    nothing. The informative numbers are (a) whether any NON-cleavable entry
    trips a motif, which would be a real false positive, and (b) how many
    cleavable entries are unreachable because their motif is too short to match
    safely.
    """
    table = build_motif_table(library)
    short = sorted(m for m in table if len(m) < 4)
    false_positives: List[Dict[str, Any]] = []
    unreachable: List[str] = []
    for entry in library.entries:
        if entry.sequence is None:
            continue
        call = call_cleavability(entry.sequence, library=library)
        if entry.cleavability_label == "non_cleavable" and call.label == "cleavable":
            false_positives.append(
                {
                    "entry_id": entry.entry_id,
                    "sequence": entry.sequence,
                    "matched": [m.motif for m in call.matches],
                }
            )
        if entry.cleavability_label == "cleavable" and call.label != "cleavable":
            unreachable.append(entry.entry_id)
    return {
        "method": "cited-motif substring lookup; not a learned model",
        "motifs_in_table": len(table),
        "motifs_excluded_as_too_short": short,
        "false_positives_on_non_cleavable_entries": false_positives,
        "cleavable_entries_not_self_matched": unreachable,
        "honest_note": (
            "Recall against proteases outside the table is unmeasured and "
            "cannot be measured from this library. Treat the negative call as "
            "'no known motif', never as 'not cleavable'."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--permutation-rounds", type=int, default=200)
    args = parser.parse_args()

    library = load_library(LIBRARY_PATH)

    rigidity_entries = modelling_subset(library, "rigidity")
    sequences = [e.sequence for e in rigidity_entries]
    labels = [e.rigidity_label for e in rigidity_entries]

    report = leave_one_out_report(
        sequences, labels, permutation_rounds=args.permutation_rounds
    )
    final_model = fit_rigidity_model(sequences, labels)

    record = {
        "record_type": "linker_property_library_report",
        "schema_version": "1.0.0",
        "generated_for_library": library.library_id,
        "curated_on": library.curated_on,
        "provenance": {
            "library_sha256": sha256_file(LIBRARY_PATH),
            "schema_sha256": sha256_file(SCHEMA_PATH),
            "script_sha256": sha256_file(Path(__file__).resolve()),
            "pipeline_commit": git_commit(),
            "python": sys.version.split()[0],
        },
        "evidence_tier": (
            "literature-reported engineered use. NOT function-tested: see "
            "reports/EXPERIMENTALLY_TESTED_LINKER_SOURCE_SEARCH_2026-10-12.md "
            "for the distinction. No count here may be presented as a count of "
            "experimentally function-tested linkers."
        ),
        "library_size": {
            "entries_total": len(library.entries),
            "entries_with_exact_sequence": sum(
                1 for e in library.entries if e.sequence is not None
            ),
            "entries_usable_for_rigidity_model": len(rigidity_entries),
        },
        "coverage_matrix": coverage_matrix(library),
        "label_basis_audit": basis_audit(library),
        "composite_templates": library.composite_templates,
        "acquisition_status": library.acquisition_status,
        "cleavability_axis": self_check_cleavability(library),
        "rigidity_axis": {
            "method": "L2 logistic regression on six cited compositional features",
            "features": final_model.feature_names,
            "coefficients": {k: round(v, 4) for k, v in final_model.coefficients().items()},
            "bias": round(final_model.bias, 4),
            "n": report.n,
            "n_rigid": report.n_rigid,
            "n_flexible": report.n_flexible,
            "leave_one_out_accuracy": round(report.accuracy, 4),
            "majority_baseline": round(report.majority_baseline, 4),
            "permutation_p": report.permutation_p,
            "permutation_rounds": report.permutation_rounds,
            "linearly_separable_in_sample": report.separable_in_sample,
            "out_of_fold_predictions": report.out_of_fold,
            "interpretation": report.interpretation,
            "calibration_note": (
                "No calibration curve is reported. With this many labelled "
                "entries a reliability diagram would be noise. The "
                "out-of-fold probabilities are published instead so a reader "
                "can judge the spread directly."
            ),
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=False)
        handle.write("\n")

    print("wrote %s" % args.out)
    print(
        "rigidity axis: n=%d (rigid=%d, flexible=%d) LOO=%.3f majority=%.3f p=%s"
        % (
            report.n,
            report.n_rigid,
            report.n_flexible,
            report.accuracy,
            report.majority_baseline,
            report.permutation_p,
        )
    )
    counts = record["coverage_matrix"]["counts"]
    print("coverage (rigidity x cleavability):")
    for rig, row in counts.items():
        print("  %-11s %s" % (rig, row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
