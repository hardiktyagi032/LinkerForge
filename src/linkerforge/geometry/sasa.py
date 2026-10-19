"""Solvent accessible surface area at candidate attachment points.

Numerical Shrake-Rupley sphere-point sampling with a 1.4 A water probe and
Bondi van der Waals radii, normalised into relative solvent accessibility with
the Tien et al. (2013) theoretical MaxASA table. See
``linkerforge.geometry.constants.CITATIONS``.

The model is heavy-atom only: no hydrogens, no waters, no ligands. Burial by a
cofactor or by a crystallographic partner chain is therefore invisible unless
that chain is passed in as context, and every report says which chains were in
the context.
"""

from __future__ import annotations

from math import cos, dist, pi, sin, sqrt

from .constants import (
    MAX_ASA_ANGSTROM2,
    RSA_BURIED_BELOW,
    RSA_EXPOSED_AT_OR_ABOVE,
    SOLVENT_PROBE_RADIUS_ANGSTROM,
)
from .structure import Atom, Point, Residue

DEFAULT_SPHERE_POINTS = 256


def sphere_points(count: int = DEFAULT_SPHERE_POINTS) -> tuple[Point, ...]:
    """Near-uniform unit-sphere points on a golden-angle spiral."""
    if count < 4:
        raise ValueError("Need at least four sphere points")
    golden_angle = pi * (3.0 - sqrt(5.0))
    points = []
    for index in range(count):
        z = 1.0 - 2.0 * (index + 0.5) / count
        radius = sqrt(max(0.0, 1.0 - z * z))
        theta = golden_angle * index
        points.append((radius * cos(theta), radius * sin(theta), z))
    return tuple(points)


def atom_sasa(
    atom: Atom,
    context: tuple[Atom, ...],
    probe: float = SOLVENT_PROBE_RADIUS_ANGSTROM,
    points: tuple[Point, ...] | None = None,
) -> float:
    """Accessible area of one atom inside ``context`` (which may include it)."""
    samples = points if points is not None else sphere_points()
    expanded = atom.radius + probe
    neighbours = [
        other
        for other in context
        if other is not atom
        and other.point != atom.point
        and dist(other.point, atom.point) < expanded + other.radius + probe
    ]
    accessible = 0
    for unit in samples:
        probe_point = (
            atom.point[0] + expanded * unit[0],
            atom.point[1] + expanded * unit[1],
            atom.point[2] + expanded * unit[2],
        )
        if all(
            dist(probe_point, other.point) >= other.radius + probe for other in neighbours
        ):
            accessible += 1
    return 4.0 * pi * expanded * expanded * accessible / len(samples)


def residue_sasa(
    residue: Residue,
    context: tuple[Atom, ...],
    probe: float = SOLVENT_PROBE_RADIUS_ANGSTROM,
    points: tuple[Point, ...] | None = None,
) -> float:
    samples = points if points is not None else sphere_points()
    return sum(atom_sasa(atom, context, probe, samples) for atom in residue.atoms)


def relative_accessibility(
    residue: Residue,
    context: tuple[Atom, ...],
    probe: float = SOLVENT_PROBE_RADIUS_ANGSTROM,
    points: tuple[Point, ...] | None = None,
) -> dict[str, object]:
    """ASA, relative accessibility and the published reporting band.

    Residues outside the twenty standard types have no MaxASA entry, so the
    relative value is ``None`` rather than a guess.
    """
    area = residue_sasa(residue, context, probe, points)
    maximum = MAX_ASA_ANGSTROM2.get(residue.name)
    relative = area / maximum if maximum else None
    if relative is None:
        band = "unknown_residue_type"
    elif relative < RSA_BURIED_BELOW:
        band = "buried"
    elif relative < RSA_EXPOSED_AT_OR_ABOVE:
        band = "partially_exposed"
    else:
        band = "exposed"
    return {
        "residue": f"{residue.chain}{residue.number}{residue.insertion_code.strip()}",
        "residue_name": residue.name,
        "sasa_angstrom2": round(area, 2),
        "max_asa_angstrom2": maximum,
        "relative_solvent_accessibility": None if relative is None else round(relative, 4),
        "band": band,
        "bands_used": {
            "buried_below": RSA_BURIED_BELOW,
            "exposed_at_or_above": RSA_EXPOSED_AT_OR_ABOVE,
        },
        "heavy_atoms_only": True,
    }
