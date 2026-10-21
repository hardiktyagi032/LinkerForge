#!/usr/bin/env python3
"""Create a provenance-bearing structural evidence checklist for one fusion.

This performs deterministic coordinate and confidence calculations only.  It
does not substitute for Rosetta all-atom scoring, molecular dynamics, or an
experimental assay.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess


THREE_TO_ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLU": "E", "GLN": "Q", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_ca(path: Path, chain: str | None = None) -> list[tuple[str, float, float, float]]:
    records: list[tuple[str, float, float, float]] = []
    seen: set[tuple[str, str]] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("ENDMDL"):
            break
        if not line.startswith("ATOM  ") or line[12:16].strip() != "CA":
            continue
        if line[16:17] not in {" ", "A"}:
            continue
        line_chain = line[21:22]
        if chain is not None and line_chain != chain:
            continue
        key = (line_chain, line[22:27].strip())
        if key in seen:
            continue
        amino_acid = THREE_TO_ONE.get(line[17:20].strip())
        if amino_acid is None:
            raise ValueError(f"Unsupported residue {line[17:20].strip()} in {path}")
        seen.add(key)
        records.append((amino_acid, float(line[30:38]), float(line[38:46]), float(line[46:54])))
    if not records:
        raise ValueError(f"No C-alpha records found in {path}")
    return records


def distance(left: tuple[str, float, float, float], right: tuple[str, float, float, float]) -> float:
    return math.sqrt(sum((left[index] - right[index]) ** 2 for index in range(1, 4)))


def coordinate_audit(records: list[tuple[str, float, float, float]]) -> dict[str, float | int | None]:
    adjacent = [distance(records[index - 1], records[index]) for index in range(1, len(records))]
    overlaps = sum(
        distance(records[left], records[right]) < 3.0
        for left in range(len(records))
        for right in range(left + 3, len(records))
    )
    return {
        "residue_count": len(records),
        "chain_break_count": sum(value > 4.5 for value in adjacent),
        "max_adjacent_ca_distance_angstrom": round(max(adjacent), 4) if adjacent else None,
        "severe_ca_overlap_count": overlaps,
    }


def aligned_rmsd(mobile: list[tuple[str, float, float, float]], target: list[tuple[str, float, float, float]]) -> float:
    if len(mobile) != len(target) or len(mobile) < 3:
        raise ValueError("RMSD inputs must contain the same three or more residues")
    if "".join(row[0] for row in mobile) != "".join(row[0] for row in target):
        raise ValueError("Reference sequence does not exactly match the corresponding fusion region")
    mobile_xyz = [row[1:] for row in mobile]
    target_xyz = [row[1:] for row in target]
    cm = [sum(row[axis] for row in mobile_xyz) / len(mobile_xyz) for axis in range(3)]
    ct = [sum(row[axis] for row in target_xyz) / len(target_xyz) for axis in range(3)]
    m = [[row[axis] - cm[axis] for axis in range(3)] for row in mobile_xyz]
    t = [[row[axis] - ct[axis] for axis in range(3)] for row in target_xyz]
    s = [[sum(m[index][row] * t[index][column] for index in range(len(m))) for column in range(3)] for row in range(3)]
    sxx, sxy, sxz = s[0]
    syx, syy, syz = s[1]
    szx, szy, szz = s[2]
    matrix = [
        [sxx + syy + szz, syz - szy, szx - sxz, sxy - syx],
        [syz - szy, sxx - syy - szz, sxy + syx, szx + sxz],
        [szx - sxz, sxy + syx, -sxx + syy - szz, syz + szy],
        [sxy - syx, szx + sxz, syz + szy, -sxx - syy + szz],
    ]
    quaternion = [1.0, 0.0, 0.0, 0.0]
    for _ in range(100):
        next_q = [sum(row[index] * quaternion[index] for index in range(4)) for row in matrix]
        norm = math.sqrt(sum(value * value for value in next_q))
        quaternion = [value / norm for value in next_q]
    w, x, y, z = quaternion
    rotation = [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]
    squared = 0.0
    for index, vector in enumerate(m):
        rotated = [sum(rotation[row][axis] * vector[axis] for axis in range(3)) for row in range(3)]
        squared += sum((rotated[axis] - t[index][axis]) ** 2 for axis in range(3))
    return math.sqrt(squared / len(m))


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fusion-pdb", type=Path, required=True)
    parser.add_argument("--score-json", type=Path, required=True)
    parser.add_argument("--domain-a-reference", type=Path, required=True)
    parser.add_argument("--domain-b-reference", type=Path, required=True)
    parser.add_argument("--domain-a-length", type=int, required=True)
    parser.add_argument("--linker-length", type=int, required=True)
    parser.add_argument("--protected-site-assessment", type=Path)
    parser.add_argument("--matched-comparison", type=Path)
    parser.add_argument("--openmm-run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    fusion = read_ca(args.fusion_pdb)
    domain_a = read_ca(args.domain_a_reference, "A")
    domain_b = read_ca(args.domain_b_reference, "A")
    b_start = args.domain_a_length + args.linker_length
    scores = json.loads(args.score_json.read_text(encoding="utf-8"))
    plddt = scores["plddt"]
    pae = scores["pae"]
    if len(fusion) != len(plddt) or len(pae) != len(fusion):
        raise ValueError("Fusion coordinates and score arrays have different lengths")
    cross_domain = [
        pae[left][right]
        for left in range(args.domain_a_length)
        for right in range(b_start, len(fusion))
    ] + [
        pae[left][right]
        for left in range(b_start, len(fusion))
        for right in range(args.domain_a_length)
    ]
    fusion_sha = sha256(args.fusion_pdb)
    linked_evidence: dict[str, object] = {}
    source_ids = [
        f"fusion-pdb-sha256:{fusion_sha}",
        f"score-json-sha256:{sha256(args.score_json)}",
        f"domain-a-reference-sha256:{sha256(args.domain_a_reference)}",
        f"domain-b-reference-sha256:{sha256(args.domain_b_reference)}",
    ]
    if args.protected_site_assessment:
        protected = json.loads(args.protected_site_assessment.read_text(encoding="utf-8"))
        if protected.get("pdb_sha256") != fusion_sha:
            raise ValueError("Protected-site assessment does not refer to the fusion PDB")
        linked_evidence["protected_site_assessment"] = {
            "path": str(args.protected_site_assessment),
            "sha256": sha256(args.protected_site_assessment),
            "measurement_count": len(protected.get("measurements", [])),
            "threshold_status": protected.get("threshold_status"),
        }
        source_ids.append(f"protected-site-assessment-sha256:{sha256(args.protected_site_assessment)}")
    if args.matched_comparison:
        comparison = json.loads(args.matched_comparison.read_text(encoding="utf-8"))
        matched_rows = [row for row in comparison.get("records", []) if row.get("pdb_sha256") == fusion_sha]
        if len(matched_rows) != 1:
            raise ValueError("Matched comparison does not contain exactly one record for the fusion PDB")
        linked_evidence["matched_comparison"] = {
            "path": str(args.matched_comparison),
            "sha256": sha256(args.matched_comparison),
            "candidate_id": matched_rows[0].get("candidate_id"),
            "selection_status": comparison.get("selection_status"),
        }
        source_ids.append(f"matched-comparison-sha256:{sha256(args.matched_comparison)}")
    if args.openmm_run:
        openmm_run = json.loads(args.openmm_run.read_text(encoding="utf-8"))
        if openmm_run.get("input_pdb_sha256") != fusion_sha or openmm_run.get("status") != "complete":
            raise ValueError("OpenMM record is incomplete or does not refer to the fusion PDB")
        linked_evidence["openmm_run"] = {
            "path": str(args.openmm_run),
            "sha256": sha256(args.openmm_run),
            "replicates": len(openmm_run.get("replicates", [])),
            "evidence_quality": openmm_run.get("evidence_quality"),
        }
        source_ids.append(f"openmm-run-sha256:{sha256(args.openmm_run)}")
    config_record = {
        "domain_a_length": args.domain_a_length,
        "linker_length": args.linker_length,
        "linked_evidence_sha256": sorted(source_ids[4:]),
    }
    config_sha = hashlib.sha256(
        json.dumps(config_record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    root = Path(__file__).resolve().parents[1]
    commit_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    worktree_modified = bool(subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, check=True,
        capture_output=True, text=True,
    ).stdout.strip())
    not_performed = ["Rosetta closure and all-atom clash scoring"]
    if "protected_site_assessment" not in linked_evidence:
        not_performed.append("protected-site spatial clearance (no protected-site assessment linked)")
    if "matched_comparison" not in linked_evidence:
        not_performed.append("matched full structural prediction for every linker baseline")
    if "openmm_run" not in linked_evidence:
        not_performed.append("OpenMM or GROMACS minimization/dynamics")
    not_performed.append("experimental expression, stability, or activity testing")
    result = {
        "schema_version": "linkerforge.structure-evidence.v1",
        "source_ids": source_ids,
        "inputs": {
            "fusion_pdb": str(args.fusion_pdb),
            "fusion_pdb_sha256": fusion_sha,
            "score_json": str(args.score_json),
            "score_json_sha256": sha256(args.score_json),
            "domain_a_reference": str(args.domain_a_reference),
            "domain_a_reference_sha256": sha256(args.domain_a_reference),
            "domain_b_reference": str(args.domain_b_reference),
            "domain_b_reference_sha256": sha256(args.domain_b_reference),
        },
        "boundaries": {
            "domain_a_length": args.domain_a_length,
            "linker_length": args.linker_length,
            "domain_b_length": len(fusion) - b_start,
        },
        "coordinate_pre_screen": coordinate_audit(fusion),
        "confidence": {
            "source": "AlphaFold2 model executed by ColabFold",
            "mean_plddt": round(mean(plddt) or 0, 4),
            "domain_a_mean_plddt": round(mean(plddt[:args.domain_a_length]) or 0, 4),
            "linker_mean_plddt": round(mean(plddt[args.domain_a_length:b_start]) or 0, 4),
            "domain_b_mean_plddt": round(mean(plddt[b_start:]) or 0, 4),
            "ptm": scores.get("ptm"),
            "max_pae": scores.get("max_pae"),
            "mean_cross_domain_pae_angstrom": round(mean(cross_domain) or 0, 4),
        },
        "reference_domain_preservation": {
            "metric": "sequence-matched C-alpha RMSD after rigid-body superposition",
            "domain_a_rmsd_angstrom": round(aligned_rmsd(fusion[:args.domain_a_length], domain_a), 4),
            "domain_b_rmsd_angstrom": round(aligned_rmsd(fusion[b_start:], domain_b), 4),
        },
        "linked_evidence": linked_evidence,
        "not_performed": not_performed,
        "software": {"python": platform.python_version(), "structure_evidence_audit": "1.0.0"},
        "provenance": {
            "commit_sha": commit_sha,
            "worktree_modified": worktree_modified,
            "config_sha256": config_sha,
        },
        "evidence_quality": "predicted_unvalidated",
        "claim_boundary": "Deterministic audit of one prediction; not evidence of expression, function, or linker optimality.",
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
