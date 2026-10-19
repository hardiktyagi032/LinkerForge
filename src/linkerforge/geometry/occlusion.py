"""Does the linker path have to go through one of the domains?

The straight line between two attachment points is the shortest possible linker
path, so its length is a lower bound on the required span. If that line passes
through domain atoms, the linker has to detour, and the required length rises.
This module measures the clearance along the straight path and, when the path
is blocked, returns a *lower bound* on the detour length.

The detour bound approximates the blocking atoms by their smallest enclosing
sphere and takes the shortest tangent-arc-tangent path around that sphere. It
is a lower bound in the single-obstacle sense only: with several separated
obstacles the true shortest path can be longer than this bound, never shorter
for the obstacle it models. It is never an upper bound, and it is not a
substitute for sampling linker conformations.
"""

from __future__ import annotations

from math import acos, dist, sqrt

from .constants import VDW_RADII_ANGSTROM
from .structure import Atom, Point

# Half-thickness used for the linker chain itself when asking whether it can
# pass: a backbone carbon's van der Waals radius. A path with less clearance
# than this cannot accommodate backbone atoms without overlap.
CHAIN_CLEARANCE_ANGSTROM = VDW_RADII_ANGSTROM["C"]


def _subtract(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a: Point) -> float:
    return sqrt(_dot(a, a))


def point_segment_distance(point: Point, start: Point, end: Point) -> float:
    """Shortest distance from ``point`` to the closed segment ``start``-``end``."""
    span = _subtract(end, start)
    length_squared = _dot(span, span)
    if length_squared == 0:
        return dist(point, start)
    t = _dot(_subtract(point, start), span) / length_squared
    t = max(0.0, min(1.0, t))
    closest = (start[0] + t * span[0], start[1] + t * span[1], start[2] + t * span[2])
    return dist(point, closest)


def path_clearance(
    start: Point,
    end: Point,
    atoms: tuple[Atom, ...],
    chain_clearance: float = CHAIN_CLEARANCE_ANGSTROM,
) -> dict[str, object]:
    """Clearance of the straight attachment-point-to-attachment-point path.

    ``atoms`` should exclude the anchor residues themselves and their immediate
    neighbours; the caller decides that exclusion and records it.
    """
    if chain_clearance < 0:
        raise ValueError("Chain clearance cannot be negative")
    worst = float("inf")
    blocking: list[Atom] = []
    for atom in atoms:
        clearance = point_segment_distance(atom.point, start, end) - atom.radius
        worst = min(worst, clearance)
        if clearance < chain_clearance:
            blocking.append(atom)
    return {
        "straight_distance_angstrom": round(dist(start, end), 3),
        "minimum_clearance_angstrom": None if worst == float("inf") else round(worst, 3),
        "required_clearance_angstrom": chain_clearance,
        "passes_through_domain": bool(blocking),
        "blocking_atom_count": len(blocking),
        "blocking_atoms": tuple(blocking),
    }


def enclosing_sphere(atoms: tuple[Atom, ...]) -> tuple[Point, float]:
    """Centroid-centred sphere containing every atom's van der Waals surface.

    Not the minimal enclosing sphere: a centroid sphere is never smaller than
    the minimal one, so the detour it implies is not an underestimate for this
    obstacle.
    """
    if not atoms:
        raise ValueError("Cannot build an enclosing sphere from no atoms")
    count = len(atoms)
    centre = (
        sum(atom.point[0] for atom in atoms) / count,
        sum(atom.point[1] for atom in atoms) / count,
        sum(atom.point[2] for atom in atoms) / count,
    )
    radius = max(dist(centre, atom.point) + atom.radius for atom in atoms)
    return centre, radius


def detour_length_around_sphere(
    start: Point,
    end: Point,
    centre: Point,
    radius: float,
) -> float:
    """Shortest path from ``start`` to ``end`` that stays outside the sphere.

    Tangent line, great-circle arc, tangent line. If the straight segment misses
    the sphere the straight distance is returned. An endpoint inside the sphere
    has no such path, which is an error rather than a silently clamped number.
    """
    if radius <= 0:
        raise ValueError("Sphere radius must be positive")
    start_range = dist(start, centre)
    end_range = dist(end, centre)
    if start_range <= radius or end_range <= radius:
        raise ValueError(
            "Attachment point lies inside the obstacle sphere; no detour bound is defined"
        )
    if point_segment_distance(centre, start, end) >= radius:
        return dist(start, end)
    first = sqrt(start_range * start_range - radius * radius)
    second = sqrt(end_range * end_range - radius * radius)
    cosine = _dot(_subtract(start, centre), _subtract(end, centre)) / (start_range * end_range)
    separation = acos(max(-1.0, min(1.0, cosine)))
    arc = separation - acos(radius / start_range) - acos(radius / end_range)
    return first + second + radius * max(0.0, arc)


def required_path_length(
    start: Point,
    end: Point,
    atoms: tuple[Atom, ...],
    chain_clearance: float = CHAIN_CLEARANCE_ANGSTROM,
) -> dict[str, object]:
    """Path length the linker must cover, straight or detoured, with the reasoning."""
    clearance = path_clearance(start, end, atoms, chain_clearance)
    straight = float(clearance["straight_distance_angstrom"])  # type: ignore[arg-type]
    blocking: tuple[Atom, ...] = clearance["blocking_atoms"]  # type: ignore[assignment]
    report = {key: value for key, value in clearance.items() if key != "blocking_atoms"}
    if not blocking:
        report.update(
            {
                "path_length_angstrom": straight,
                "path_model": "straight_line",
                "detour_lower_bound": False,
            }
        )
        return report
    centre, radius = enclosing_sphere(blocking)
    try:
        detour = detour_length_around_sphere(start, end, centre, radius + chain_clearance)
    except ValueError as exc:
        report.update(
            {
                "path_length_angstrom": None,
                "path_model": "undefined",
                "detour_lower_bound": False,
                "path_note": (
                    f"{exc}. The path is blocked, so the straight distance is still a valid "
                    "lower bound on the length the linker must cover, and callers fall back "
                    "to it: the required length they report stays a lower bound, but a "
                    "looser one."
                ),
            }
        )
        return report
    report.update(
        {
            "path_length_angstrom": round(detour, 3),
            "path_model": "tangent_arc_tangent_around_blocking_sphere",
            "detour_lower_bound": True,
            "obstacle_sphere_radius_angstrom": round(radius + chain_clearance, 3),
            "path_note": (
                "The straight path is blocked, so the required length is computed around a "
                "sphere enclosing the blocking atoms. This is a lower bound for that single "
                "obstacle, not the true shortest path through a crowded surface."
            ),
        }
    )
    return report
