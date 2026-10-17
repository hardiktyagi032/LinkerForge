"""Several linkers between the same two domains, satisfied at once.

One tether asks whether a span is bridgeable. Two or three simultaneous tethers
ask something harder: is there a single rigid-body placement of domain B
relative to domain A for which *every* tether's span is within its own length
window at the same time. That is a constraint-satisfaction problem over SE(3),
and it has no closed-form solution in general.

What this module does provide is a two-sided answer whose halves are honest
about what they prove:

* ``pairwise_consistency`` is a closed-form **necessary** condition from
  distance geometry. Because domain B is rigid, the separation of two of its
  own attachment points cannot change, so for any two tethers i and j
  ``|d_A(i,j) - d_B(i,j)| <= max_span(i) + max_span(j)``. A violation is a
  *certificate of infeasibility*: no placement whatsoever can satisfy both
  tethers. It uses only the upper span bounds, which makes it a relaxation of
  the real problem, so it can never reject a placement that is actually
  possible.
* ``find_placement`` searches for an explicit placement. A returned placement is
  a *witness*: the caller can recompute every distance and confirm it. Failure
  to find one proves nothing, and the report says so rather than calling it
  infeasible.

Between those two outcomes there is a genuine "undetermined" verdict, and this
module returns it instead of guessing.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from math import dist, pi

from .rigid import IDENTITY, Matrix3, Point, apply, centroid, optimal_superposition, quaternion_from_axis_angle, rotation_from_quaternion


@dataclass(frozen=True)
class TetherConstraint:
    """One linker: an anchor on each domain and the span window it allows.

    ``anchor_b`` is in domain B's own input coordinate frame; the placement
    search moves it. ``minimum_span`` is 0 for a flexible linker, which can be
    slack, and positive for a rigid helical one, which cannot.
    """

    name: str
    anchor_a: Point
    anchor_b: Point
    minimum_span: float
    maximum_span: float

    def __post_init__(self) -> None:
        if self.minimum_span < 0:
            raise ValueError(f"Tether {self.name}: minimum span cannot be negative")
        if self.maximum_span < self.minimum_span:
            raise ValueError(f"Tether {self.name}: maximum span is below the minimum")


def pairwise_consistency(constraints: tuple[TetherConstraint, ...]) -> dict[str, object]:
    """Closed-form distance-geometry test over every pair of tethers."""
    if len(constraints) < 2:
        return {
            "pairs": [],
            "certified_infeasible": False,
            "note": "A single tether has no pairwise condition to violate.",
        }
    pairs = []
    infeasible = False
    for i in range(len(constraints)):
        for j in range(i + 1, len(constraints)):
            first, second = constraints[i], constraints[j]
            on_a = dist(first.anchor_a, second.anchor_a)
            on_b = dist(first.anchor_b, second.anchor_b)
            allowance = first.maximum_span + second.maximum_span
            mismatch = abs(on_a - on_b)
            violated = mismatch > allowance
            infeasible = infeasible or violated
            pairs.append(
                {
                    "tethers": [first.name, second.name],
                    "anchor_separation_on_domain_a_angstrom": round(on_a, 3),
                    "anchor_separation_on_domain_b_angstrom": round(on_b, 3),
                    "separation_mismatch_angstrom": round(mismatch, 3),
                    "combined_span_allowance_angstrom": round(allowance, 3),
                    "pair_satisfiable": not violated,
                }
            )
    return {
        "pairs": pairs,
        "certified_infeasible": infeasible,
        "note": (
            "Necessary condition only, using upper span bounds. A violated pair proves no "
            "rigid-body placement exists. All pairs passing proves nothing on its own."
        ),
    }


def _project_to_shell(point: Point, centre: Point, lower: float, upper: float) -> Point:
    offset = (point[0] - centre[0], point[1] - centre[1], point[2] - centre[2])
    length = dist(point, centre)
    if length == 0:
        if lower == 0:
            return point
        return (centre[0] + lower, centre[1], centre[2])
    if length < lower:
        scale = lower / length
    elif length > upper:
        scale = upper / length
    else:
        return point
    return (
        centre[0] + offset[0] * scale,
        centre[1] + offset[1] * scale,
        centre[2] + offset[2] * scale,
    )


def placement_violation(
    constraints: tuple[TetherConstraint, ...],
    rotation: Matrix3,
    translation: Point,
) -> dict[str, object]:
    """Per-tether spans and the worst window violation for one placement."""
    tethers = []
    worst = 0.0
    for constraint in constraints:
        placed = apply(rotation, translation, constraint.anchor_b)
        span = dist(constraint.anchor_a, placed)
        shortfall = max(0.0, constraint.minimum_span - span, span - constraint.maximum_span)
        worst = max(worst, shortfall)
        tethers.append(
            {
                "tether": constraint.name,
                "span_angstrom": round(span, 3),
                "window_angstrom": [constraint.minimum_span, constraint.maximum_span],
                "within_window": shortfall == 0.0,
                "violation_angstrom": round(shortfall, 3),
            }
        )
    return {"tethers": tethers, "maximum_violation_angstrom": round(worst, 4)}


def find_placement(
    constraints: tuple[TetherConstraint, ...],
    restarts: int = 32,
    iterations: int = 300,
    tolerance: float = 0.05,
    seed: int = 0,
) -> dict[str, object]:
    """Search for a rigid-body placement of domain B satisfying every tether.

    Alternating projection: each anchor of B is projected onto the spherical
    shell its own tether allows, then the rigid motion that best fits those
    targets is recomputed in closed form. Random restarts cover different
    initial orientations. This is a search with no global guarantee, which is
    why only success is reported as a result.
    """
    if not constraints:
        raise ValueError("Need at least one tether constraint")
    if restarts < 1 or iterations < 1:
        raise ValueError("Restarts and iterations must be positive")
    rng = random.Random(seed)
    moving = tuple(constraint.anchor_b for constraint in constraints)
    anchors = tuple(constraint.anchor_a for constraint in constraints)
    best: dict[str, object] | None = None
    best_rotation, best_translation = IDENTITY, (0.0, 0.0, 0.0)
    solutions: list[dict[str, object]] = []
    for restart in range(restarts):
        if restart == 0:
            # Restart zero is the input frame itself, untouched. When the two
            # domains are already placed relative to each other (two chains of
            # one structure), this asks the cheap question first: do the tethers
            # already fit as the input stands?
            rotation: Matrix3 = IDENTITY
            translation: Point = (0.0, 0.0, 0.0)
            report = placement_violation(constraints, rotation, translation)
            violation = float(report["maximum_violation_angstrom"])  # type: ignore[arg-type]
            best, best_rotation, best_translation = report, rotation, translation
            if violation <= tolerance:
                solutions.append(
                    {
                        "rotation": rotation,
                        "translation": translation,
                        "maximum_violation_angstrom": report["maximum_violation_angstrom"],
                        "tethers": report["tethers"],
                        "placement_source": "input_frame",
                    }
                )
                continue
            rotation = IDENTITY
        else:
            axis = (rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))
            if axis == (0.0, 0.0, 0.0):
                axis = (1.0, 0.0, 0.0)
            rotation = rotation_from_quaternion(
                quaternion_from_axis_angle(axis, rng.uniform(0, 2 * pi))
            )
        moving_centre = centroid(moving)
        target_centre = centroid(anchors)
        rotated_centre = apply(rotation, (0.0, 0.0, 0.0), moving_centre)
        translation: Point = (
            target_centre[0] - rotated_centre[0],
            target_centre[1] - rotated_centre[1],
            target_centre[2] - rotated_centre[2],
        )
        for _ in range(iterations):
            placed = tuple(apply(rotation, translation, point) for point in moving)
            targets = tuple(
                _project_to_shell(
                    point, constraint.anchor_a, constraint.minimum_span, constraint.maximum_span
                )
                for point, constraint in zip(placed, constraints)
            )
            if len(moving) == 1:
                # One tether leaves rotation unconstrained; translate only.
                offset = (
                    targets[0][0] - placed[0][0],
                    targets[0][1] - placed[0][1],
                    targets[0][2] - placed[0][2],
                )
                translation = (
                    translation[0] + offset[0],
                    translation[1] + offset[1],
                    translation[2] + offset[2],
                )
            else:
                rotation, translation = optimal_superposition(moving, targets)
            report = placement_violation(constraints, rotation, translation)
            violation = float(report["maximum_violation_angstrom"])  # type: ignore[arg-type]
            if best is None or violation < float(best["maximum_violation_angstrom"]):  # type: ignore[arg-type]
                best, best_rotation, best_translation = report, rotation, translation
            if violation <= tolerance:
                solutions.append(
                    {
                        "rotation": rotation,
                        "translation": translation,
                        "maximum_violation_angstrom": report["maximum_violation_angstrom"],
                        "tethers": report["tethers"],
                        "placement_source": "search",
                    }
                )
                break
    assert best is not None
    satisfied = float(best["maximum_violation_angstrom"]) <= tolerance  # type: ignore[arg-type]
    return {
        "placement_found": satisfied,
        "tolerance_angstrom": tolerance,
        "rotation": best_rotation,
        "translation": best_translation,
        "tethers": best["tethers"],
        "maximum_violation_angstrom": best["maximum_violation_angstrom"],
        "satisfying_placements": tuple(solutions),
        "search": {
            "method": "alternating projection onto span shells with closed-form rigid refit",
            "restarts": restarts,
            "iterations_per_restart": iterations,
            "seed": seed,
            "satisfying_placements_found": len(solutions),
        },
        "interpretation": (
            "A placement found here is a witness and can be rechecked from the returned "
            "rotation and translation. No placement found is not a proof of infeasibility; "
            "only a violated pairwise bound proves that. Two tethers leave one rotational "
            "degree of freedom about the axis through their anchors, so several satisfying "
            "placements usually exist and they are all returned for steric screening."
        ),
    }


# Chain topology implied by the number of simultaneous peptide tethers between
# two domains, with the engineering requirement each one carries. Based on what
# a single polypeptide can do: every tether is one chain crossing between the
# domains, so k tethers need k crossings.
CHAIN_TOPOLOGIES: dict[int, dict[str, str]] = {
    1: {
        "topology": "tandem",
        "requirement": "One chain: domain A, linker, domain B. Both anchors are chain termini.",
        "frequency": "The standard fusion format.",
    },
    2: {
        "topology": "insertional",
        "requirement": (
            "One chain crossing twice: domain B sits inside a surface loop of domain A, so "
            "the anchors on A are the two flanks of one loop and the anchors on B are its "
            "two termini. Both loop flanks must tolerate interruption."
        ),
        "frequency": "Established as domain insertion; common in engineered switches.",
    },
}

SPLIT_TOPOLOGY = {
    "topology": "split_or_non_peptide",
    "requirement": (
        "Three or more peptide tethers force at least one domain to be built from two "
        "non-contiguous chain segments (a split domain or circular permutation), or move the "
        "construct off a single polypeptide entirely: two co-expressed chains, a circularised "
        "chain, or chemical crosslinks in place of peptide linkers."
    ),
    "frequency": (
        "Not a routine fusion format. Treat a three-tether geometric solution as a "
        "hypothesis about what would be needed, not as a construct design."
    ),
}


CROSSLINK_ONLY_TOPOLOGY = {
    "topology": "crosslink_only",
    "requirement": (
        "No peptide tether, so the two domains are separate chains held together only by "
        "crosslinks. They must be co-expressed or mixed and then oxidised; there is no single "
        "polypeptide and no linker length to choose."
    ),
    "frequency": "Routine for chemical conjugates, not a fusion protein.",
}


def implied_chain_topology(
    tether_count: int,
    peptide_tethers: int | None = None,
) -> dict[str, object]:
    """What a single expressed polypeptide would have to do to carry these tethers.

    Only peptide tethers force the chain to cross between the domains; a
    disulfide costs two cysteine substitutions and no chain crossing, which is
    why it is the cheap way to add a second tether.
    """
    if tether_count < 1:
        raise ValueError("Tether count must be at least one")
    peptide = tether_count if peptide_tethers is None else peptide_tethers
    if not 0 <= peptide <= tether_count:
        raise ValueError("Peptide tether count must be between zero and the tether count")
    if peptide == 0:
        base = CROSSLINK_ONLY_TOPOLOGY
    else:
        base = CHAIN_TOPOLOGIES.get(peptide, SPLIT_TOPOLOGY)
    return {
        "tether_count": tether_count,
        "peptide_tethers": peptide,
        "non_peptide_tethers": tether_count - peptide,
        "chain_crossings_required": peptide,
        **base,
        "note": (
            "Topology is reported because a geometrically satisfiable tether set with no "
            "realisable chain topology is not a usable design."
        ),
    }
