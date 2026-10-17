"""Conservative C-alpha geometry diagnostics for one single-chain PDB model.

No fitted thresholds or biological pass/fail decision is made here. Missing
residues and mapping ambiguity are explicit errors, never silently ignored.
"""

from __future__ import annotations

from math import dist, sqrt
from pathlib import Path

Point = tuple[float, float, float]


def load_ca_pdb(path: str | Path, chain: str) -> dict[int, Point]:
    """Read first-model, unambiguous C-alpha coordinates keyed by PDB residue ID.

    This minimal parser supports one-character chain IDs and integer residue
    numbering without insertion codes. Other cases require a dedicated mmCIF
    residue mapper; refusing them is safer than mis-scoring a fusion.
    """
    result: dict[int, Point] = {}
    saw_model = False
    for line in Path(path).open(encoding="utf-8"):
        if line.startswith("MODEL "):
            if saw_model:
                break
            saw_model = True
        if line.startswith("ENDMDL"):
            break
        if not line.startswith("ATOM  ") or len(line) < 54:
            continue
        if line[12:16].strip() != "CA" or line[21] != chain:
            continue
        if line[16] not in (" ", "A") or line[26] != " ":
            raise ValueError("Ambiguous alternate location or insertion code; use an explicit mapper")
        try:
            residue = int(line[22:26])
            point = (float(line[30:38]), float(line[38:46]), float(line[46:54]))
        except ValueError as exc:
            raise ValueError(f"Malformed coordinate in {path}") from exc
        if residue in result:
            raise ValueError(f"Duplicate C-alpha for chain {chain} residue {residue}")
        result[residue] = point
    if not result:
        raise ValueError(f"No C-alpha coordinates for chain {chain} in {path}")
    return result


def _complete_span(coords: dict[int, Point], span: tuple[int, int], name: str) -> list[Point]:
    start, end = span
    if start < 1 or end < start:
        raise ValueError(f"Invalid {name} residue span")
    missing = [position for position in range(start, end + 1) if position not in coords]
    if missing:
        raise ValueError(f"{name} missing {len(missing)} C-alpha atoms; first={missing[0]}")
    return [coords[position] for position in range(start, end + 1)]


def _internal_distance_rmsd(predicted: list[Point], reference: list[Point]) -> float:
    """Rotation-invariant intra-domain dRMSD, not superposed coordinate RMSD."""
    if len(predicted) != len(reference):
        raise ValueError("Predicted and reference domains differ in length")
    if len(predicted) < 2:
        raise ValueError("Domain needs at least two C-alpha atoms")
    squared = count = 0
    for i in range(len(predicted)):
        for j in range(i + 1, len(predicted)):
            squared += (dist(predicted[i], predicted[j]) - dist(reference[i], reference[j])) ** 2
            count += 1
    return sqrt(squared / count)


def score_fusion(
    predicted: dict[int, Point],
    domain_a: tuple[int, int],
    linker: tuple[int, int],
    domain_b: tuple[int, int],
    reference_a: list[Point] | None = None,
    reference_b: list[Point] | None = None,
) -> dict[str, object]:
    """Measure geometry for one numbered complete-chain prediction.

    Coordinates must already be mapped to full-fusion sequence indices (1..L).
    Reference coordinates must be in the matching residue order. A C-alpha
    clash (<2 A) is only a severe-overlap flag, not an all-atom clash score.
    """
    if not (domain_a[1] + 1 == linker[0] and linker[1] + 1 == domain_b[0]):
        raise ValueError("Domain and linker spans must be contiguous")
    a = _complete_span(predicted, domain_a, "domain A")
    l = _complete_span(predicted, linker, "linker")
    b = _complete_span(predicted, domain_b, "domain B")
    positions = list(range(domain_a[0], domain_b[1] + 1))
    coords = a + l + b
    adjacent = [dist(coords[i], coords[i + 1]) for i in range(len(coords) - 1)]
    junctions = [dist(a[-1], l[0]), dist(l[-1], b[0])]
    severe_clashes = 0
    for i in range(len(coords)):
        for j in range(i + 4, len(coords)):
            if dist(coords[i], coords[j]) < 2.0:
                severe_clashes += 1
    return {
        "schema_version": "0.1.0",
        "residue_count": len(positions),
        "junction_ca_distances_angstrom": junctions,
        "maximum_adjacent_ca_distance_angstrom": max(adjacent),
        "ca_gaps_above_4_5_angstrom": sum(value > 4.5 for value in adjacent),
        "severe_nonlocal_ca_overlaps_below_2_angstrom": severe_clashes,
        "domain_a_internal_distance_rmsd_angstrom":
            _internal_distance_rmsd(a, reference_a) if reference_a is not None else None,
        "domain_b_internal_distance_rmsd_angstrom":
            _internal_distance_rmsd(b, reference_b) if reference_b is not None else None,
        "limitations": ["C-alpha-only diagnostic; not all-atom clash or molecular dynamics",
                        "No biological pass/fail thresholds applied"],
    }
