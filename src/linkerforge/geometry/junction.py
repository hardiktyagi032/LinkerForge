"""Attachment-point reports: one junction, and sets of simultaneous tethers.

``evaluate_junction`` answers the single-linker question for two domains that
are already in a common coordinate frame (two chains of one crystal structure,
or two models the caller has already placed): how many linker residues the
junction needs, how exposed each attachment point is, which way the chain
leaves each domain, and whether the straight path is blocked.

``evaluate_tether_set`` answers the multi-linker question, where the relative
placement of domain B is *not* fixed: it solves for a placement, or certifies
that none exists. See ``linkerforge.geometry.tether`` for what each half of
that answer proves.

Neither function predicts expression, folding or activity, and neither returns
a success probability. The nearest published zero-shot signal for whether a
designed fusion folds and expresses is ESMFold pLDDT at about AUC 0.73, which
is a weak flag and is not computed here.
"""

from __future__ import annotations

from math import acos, degrees, dist, sqrt

from .constants import (
    CITATIONS,
    DEFAULT_GS_COMPOSITION,
    DISULFIDE_CA_CA_WINDOW_ANGSTROM,
    HELIX_RISE_DEFAULT_ANGSTROM,
    LINKER_TYPES,
    TETHER_TYPES,
)
from .occlusion import CHAIN_CLEARANCE_ANGSTROM, required_path_length
from .sasa import DEFAULT_SPHERE_POINTS, relative_accessibility, sphere_points
from .span import (
    HELICAL_JUNCTION_TOLERANCE_ANGSTROM,
    flexible_strain,
    maximum_span,
    required_length,
    verdict_for_requested_length,
)
from .structure import Atom, Chain, Point, Residue
from .tether import (
    TetherConstraint,
    find_placement,
    implied_chain_topology,
    pairwise_consistency,
    placement_violation,
)
from .rigid import apply

# Heavy-atom overlap beyond this is counted as a steric clash between domains.
# Crystal contacts routinely show small overlaps against Bondi radii, so a
# tolerance is applied rather than demanding zero overlap.
CLASH_OVERLAP_TOLERANCE_ANGSTROM = 0.5

# Two C-alpha atoms of different domains closer than this are in contact: below
# it, backbone atoms cannot both be accommodated. Used only to rank candidate
# placements before the full heavy-atom check.
COARSE_CONTACT_CUTOFF_ANGSTROM = 4.5

# Sequence neighbours of an anchor are excluded from the path clearance test:
# the linker is covalently continuous with them, so they cannot "block" it.
ANCHOR_NEIGHBOUR_WINDOW = 1


def _unit(vector: Point) -> Point:
    length = sqrt(sum(component * component for component in vector))
    if length == 0:
        raise ValueError("Cannot take the direction of a zero-length vector")
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def _angle_degrees(first: Point, second: Point) -> float:
    a, b = _unit(first), _unit(second)
    cosine = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))
    return degrees(acos(cosine))


def _difference(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def exit_vector(chain: Chain, number: int, side: str) -> Point:
    """Direction in which the chain leaves the domain at an attachment point.

    ``side`` is "c_terminal" when the linker continues after this residue, and
    "n_terminal" when the linker arrives before it. The vector is taken from
    the adjacent residue's CA, which must be present.
    """
    position = chain.index_of(number)
    if side == "c_terminal":
        neighbour = position - 1
    elif side == "n_terminal":
        neighbour = position + 1
    else:
        raise ValueError(f"Unknown attachment side {side!r}")
    if not 0 <= neighbour < len(chain.residues):
        raise ValueError(
            f"Residue {number} of chain {chain.identifier} has no {side} neighbour to define "
            "an exit vector"
        )
    return _difference(chain.residues[position].ca, chain.residues[neighbour].ca)


def _domain_atoms(chain: Chain) -> tuple[Atom, ...]:
    return tuple(atom for residue in chain.residues for atom in residue.atoms)


def _atoms_excluding(chain: Chain, number: int, window: int) -> tuple[Atom, ...]:
    position = chain.index_of(number)
    excluded = range(max(0, position - window), min(len(chain.residues), position + window + 1))
    return tuple(
        atom
        for index, residue in enumerate(chain.residues)
        if index not in excluded
        for atom in residue.atoms
    )


def _orientation(
    chain: Chain, anchor: Residue, span_direction: Point
) -> dict[str, object]:
    atoms = _domain_atoms(chain)
    centre = (
        sum(atom.point[0] for atom in atoms) / len(atoms),
        sum(atom.point[1] for atom in atoms) / len(atoms),
        sum(atom.point[2] for atom in atoms) / len(atoms),
    )
    outward = _difference(anchor.ca, centre)
    angle = _angle_degrees(outward, span_direction)
    return {
        "domain_centroid_to_anchor_angstrom": round(dist(centre, anchor.ca), 3),
        "mean_atom_distance_from_centroid_angstrom": round(
            sum(dist(centre, atom.point) for atom in atoms) / len(atoms), 3
        ),
        "anchor_outward_angle_to_span_degrees": round(angle, 2),
        "anchor_faces_partner_domain": angle < 90.0,
    }


def evaluate_junction(
    domain_a: Chain,
    anchor_a: int,
    domain_b: Chain,
    anchor_b: int,
    linker_type: str = "flexible",
    requested_residues: int | None = None,
    composition: str = DEFAULT_GS_COMPOSITION,
    points: int = DEFAULT_SPHERE_POINTS,
) -> dict[str, object]:
    """Geometric report for joining ``anchor_a`` of domain A to ``anchor_b`` of domain B.

    Both chains must already be in one coordinate frame. The linker runs out of
    domain A after ``anchor_a`` and into domain B before ``anchor_b``.
    """
    if linker_type not in LINKER_TYPES:
        raise ValueError(f"Unknown linker type {linker_type!r}; have {list(LINKER_TYPES)}")
    residue_a = domain_a.residue(anchor_a)
    residue_b = domain_b.residue(anchor_b)
    start, end = residue_a.ca, residue_b.ca
    straight = dist(start, end)
    if straight == 0:
        raise ValueError("Attachment points are coincident; check the input frame")
    span_direction = _difference(end, start)

    samples = sphere_points(points)
    # One chain can legitimately be passed as both domains, for a junction
    # between two segments of the same chain. Its atoms must then be counted
    # once, or accessibility and clearance are computed against a doubled copy
    # of the structure.
    same_chain = domain_a is domain_b or domain_a.identifier == domain_b.identifier
    if same_chain:
        context = _domain_atoms(domain_a)
        near_b = set(_atoms_excluding(domain_b, anchor_b, ANCHOR_NEIGHBOUR_WINDOW))
        obstacles = tuple(
            atom
            for atom in _atoms_excluding(domain_a, anchor_a, ANCHOR_NEIGHBOUR_WINDOW)
            if atom in near_b
        )
    else:
        context = _domain_atoms(domain_a) + _domain_atoms(domain_b)
        obstacles = _atoms_excluding(
            domain_a, anchor_a, ANCHOR_NEIGHBOUR_WINDOW
        ) + _atoms_excluding(domain_b, anchor_b, ANCHOR_NEIGHBOUR_WINDOW)
    path = required_path_length(start, end, obstacles, CHAIN_CLEARANCE_ANGSTROM)
    path_length = path["path_length_angstrom"]
    distance_for_length = straight if path_length is None else float(path_length)
    path["distance_used_for_required_length_angstrom"] = round(distance_for_length, 3)
    path["required_length_is_lower_bound_only"] = bool(
        path["passes_through_domain"] and path_length is None
    )

    window = required_length(distance_for_length, linker_type, composition)
    report: dict[str, object] = {
        "record_type": "linker_junction_geometry",
        "schema_version": "1.0.0",
        "linker_type": linker_type,
        "attachment_points": {
            "domain_a": {
                "chain": domain_a.identifier,
                "residue": anchor_a,
                "residue_name": residue_a.name,
                "ca": [round(value, 3) for value in start],
                "side": "c_terminal",
            },
            "domain_b": {
                "chain": domain_b.identifier,
                "residue": anchor_b,
                "residue_name": residue_b.name,
                "ca": [round(value, 3) for value in end],
                "side": "n_terminal",
            },
        },
        "span": {
            "straight_ca_distance_angstrom": round(straight, 3),
            "path_length_used_angstrom": round(distance_for_length, 3),
            "path": path,
        },
        "required_linker_length": window,
        "accessibility": {
            "domain_a_anchor": relative_accessibility(residue_a, context, points=samples),
            "domain_b_anchor": relative_accessibility(residue_b, context, points=samples),
            "context_chains": sorted({domain_a.identifier, domain_b.identifier}),
        },
        "orientation": {
            "domain_a": _orientation(domain_a, residue_a, span_direction),
            "domain_b": _orientation(domain_b, residue_b, (-span_direction[0], -span_direction[1], -span_direction[2])),
        },
        "single_chain_input": same_chain,
        "citations": CITATIONS,
        "out_of_scope": [
            "Expression, folding and activity of the resulting construct.",
            "Whether the two domains disrupt each other's structure or interact at a new interface.",
            "Linker sequence choice beyond the flexible/helical distinction.",
            "Conformational ensembles: only one input conformation is measured.",
        ],
    }

    try:
        report["orientation"]["domain_a"]["chain_exit_angle_to_span_degrees"] = round(
            _angle_degrees(exit_vector(domain_a, anchor_a, "c_terminal"), span_direction), 2
        )
    except ValueError as exc:
        report["orientation"]["domain_a"]["chain_exit_angle_note"] = str(exc)
    try:
        report["orientation"]["domain_b"]["chain_exit_angle_to_span_degrees"] = round(
            _angle_degrees(
                exit_vector(domain_b, anchor_b, "n_terminal"),
                (-span_direction[0], -span_direction[1], -span_direction[2]),
            ),
            2,
        )
    except ValueError as exc:
        report["orientation"]["domain_b"]["chain_exit_angle_note"] = str(exc)

    if requested_residues is not None:
        verdict = verdict_for_requested_length(window, requested_residues)
        if linker_type == "flexible":
            verdict["strain"] = flexible_strain(distance_for_length, requested_residues, composition)
        report["requested_length_verdict"] = verdict
    return report


def _span_window(linker_type: str, residues: int) -> tuple[float, float]:
    """Span window a tether of this type and length can cover.

    A disulfide has no length to choose: its window is fixed and ``residues``
    must be zero, so that a mixed tether set cannot quietly treat it as a
    peptide linker.
    """
    if linker_type == "disulfide":
        if residues != 0:
            raise ValueError("A disulfide tether has no linker residues; pass 0")
        return DISULFIDE_CA_CA_WINDOW_ANGSTROM
    if linker_type == "flexible":
        return 0.0, maximum_span(residues)
    centre = (residues + 1) * HELIX_RISE_DEFAULT_ANGSTROM
    return (
        max(0.0, centre - HELICAL_JUNCTION_TOLERANCE_ANGSTROM),
        centre + HELICAL_JUNCTION_TOLERANCE_ANGSTROM,
    )


def _clashes(
    domain_a: Chain,
    domain_b: Chain,
    rotation,
    translation,
    tolerance: float = CLASH_OVERLAP_TOLERANCE_ANGSTROM,
) -> dict[str, object]:
    """Heavy-atom overlap between domain A and a placed domain B.

    A uniform grid over domain A keeps this cheap enough to run on every
    candidate placement rather than on one. The tolerance is calibrated against
    a real interface: across the native 4E43 protease dimer the largest
    heavy-atom overlap against Bondi radii is 0.39 A, from hydrogen bonds, so
    0.5 A separates real packing from interpenetration.
    """
    largest_radius = max(atom.radius for atom in _domain_atoms(domain_a))
    cell = max(1.0, 2.0 * largest_radius - tolerance)
    grid: dict[tuple[int, int, int], list[Atom]] = {}
    for atom in _domain_atoms(domain_a):
        key = tuple(int(value // cell) for value in atom.point)
        grid.setdefault(key, []).append(atom)  # type: ignore[arg-type]

    worst = 0.0
    count = 0
    for atom in _domain_atoms(domain_b):
        placed = apply(rotation, translation, atom.point)
        base = tuple(int(value // cell) for value in placed)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for other in grid.get((base[0] + dx, base[1] + dy, base[2] + dz), ()):
                        overlap = (atom.radius + other.radius) - dist(placed, other.point)
                        if overlap > tolerance:
                            count += 1
                            worst = max(worst, overlap)
    return {
        "clashing_atom_pairs": count,
        "worst_overlap_angstrom": round(worst, 3),
        "overlap_tolerance_angstrom": tolerance,
        "domains_clash": count > 0,
    }


def evaluate_tether_set(
    domain_a: Chain,
    domain_b: Chain,
    tethers: tuple[tuple[int, int, str, int], ...],
    restarts: int = 32,
    iterations: int = 300,
    tolerance: float = 0.05,
    seed: int = 0,
) -> dict[str, object]:
    """Can several linkers hold these two domains at once, and at what placement?

    Each tether is ``(residue_on_a, residue_on_b, tether_type, residues)``, where
    the type is "flexible", "helical" or "disulfide". Types may be mixed in one
    set: a disulfide contributes a fixed short Ca-Ca window instead of a
    length-dependent reachable range, which is usually the cheapest way to add a
    second tether. Domain B's input coordinates are treated as its internal
    geometry only; the search is free to place it anywhere.
    """
    if not tethers:
        raise ValueError("Need at least one tether")
    constraints = []
    for index, (number_a, number_b, linker_type, residues) in enumerate(tethers):
        if linker_type not in TETHER_TYPES:
            raise ValueError(f"Unknown tether type {linker_type!r}; have {list(TETHER_TYPES)}")
        lower, upper = _span_window(linker_type, residues)
        constraints.append(
            TetherConstraint(
                name=f"{index + 1}:{domain_a.identifier}{number_a}-{domain_b.identifier}{number_b}",
                anchor_a=domain_a.residue(number_a).ca,
                anchor_b=domain_b.residue(number_b).ca,
                minimum_span=lower,
                maximum_span=upper,
            )
        )
    frozen = tuple(constraints)
    necessary = pairwise_consistency(frozen)
    report: dict[str, object] = {
        "record_type": "linker_tether_set_geometry",
        "schema_version": "1.0.0",
        "tethers": [
            {
                "tether": constraint.name,
                "domain_a_residue": number_a,
                "domain_b_residue": number_b,
                "tether_type": linker_type,
                "linker_residues": residues,
                "span_window_angstrom": [
                    round(constraint.minimum_span, 3),
                    round(constraint.maximum_span, 3),
                ],
            }
            for constraint, (number_a, number_b, linker_type, residues) in zip(frozen, tethers)
        ],
        "chain_topology": implied_chain_topology(
            len(frozen),
            peptide_tethers=sum(
                1 for _, _, tether_type, _ in tethers if tether_type != "disulfide"
            ),
        ),
        "pairwise_necessary_condition": necessary,
        "citations": CITATIONS,
        "out_of_scope": [
            "Whether the chain topology the tether set implies can actually be built and folded.",
            "Side-chain geometry of a disulfide tether: only the Ca-Ca window is checked, not "
            "Cb-Cb, chi3 or the redox environment.",
            "Internal flexibility of either domain: both are treated as rigid bodies.",
            "Expression, folding and activity of the resulting construct.",
        ],
    }
    if necessary["certified_infeasible"]:
        report["verdict"] = "certified_infeasible"
        report["verdict_reason"] = (
            "Two attachment-point separations differ by more than the two linkers can absorb, "
            "so no rigid-body placement of domain B can satisfy both tethers. This is a proof, "
            "not a search result."
        )
        return report

    placement = find_placement(frozen, restarts, iterations, tolerance, seed)
    candidates = placement.pop("satisfying_placements")
    report["placement_search"] = placement
    if not placement["placement_found"]:
        report["verdict"] = "undetermined"
        report["verdict_reason"] = (
            "The pairwise bound is satisfied but the search found no placement within "
            f"{tolerance} A. That is not a proof of infeasibility; the best residual violation "
            f"was {placement['maximum_violation_angstrom']} A."
        )
        return report

    # Satisfying the spans leaves spare degrees of freedom (two tethers leave a
    # whole rotation about their axis), so every placement the search found is
    # checked for domain overlap and the most open one is reported.
    screened = [
        (_clashes(domain_a, domain_b, found["rotation"], found["translation"]), found)
        for found in candidates
    ]
    screened.sort(key=lambda pair: (pair[0]["clashing_atom_pairs"], pair[0]["worst_overlap_angstrom"]))
    clash, chosen = screened[0]
    report["placement"] = {
        "rotation": chosen["rotation"],
        "translation": chosen["translation"],
        "tethers": chosen["tethers"],
        "placement_source": chosen.get("placement_source"),
    }
    report["placement_screening"] = {
        "satisfying_placements": len(candidates),
        "clashing_atom_pairs_per_placement": sorted(
            report_["clashing_atom_pairs"] for report_, _ in screened
        ),
        "clash_free_placements": sum(
            1 for report_, _ in screened if not report_["domains_clash"]
        ),
    }
    report["steric_check"] = clash
    report["placement_recheck"] = placement_violation(
        frozen, chosen["rotation"], chosen["translation"]
    )
    if clash["domains_clash"]:
        report["verdict"] = "spans_satisfiable_but_domains_clash"
        report["verdict_reason"] = (
            "Every span can be satisfied at once, but the most open of the "
            f"{len(candidates)} placements found still overlaps the two domains "
            f"({clash['clashing_atom_pairs']} heavy-atom pairs, worst overlap "
            f"{clash['worst_overlap_angstrom']} A). The search optimises spans, not packing, "
            "so this is evidence against this attachment-point set rather than a proof."
        )
        return report
    report["verdict"] = "feasible_with_witness"
    report["verdict_reason"] = (
        "A single rigid-body placement satisfies every tether's span window with no "
        "heavy-atom clash between the domains. The rotation and translation are returned so "
        "the result can be rechecked independently."
    )
    return report
