"""How many linker residues a given attachment-point separation needs.

The primary quantity is the *minimum required linker length in residues* for a
pair of attachment points, with the feasible window at both ends:

* a flexible linker has a hard lower bound (it cannot stretch past full
  extension) and no geometric upper bound, only a growing entropic cost, so the
  upper end of its window is reported as ``None`` with a strain figure;
* a helical linker is a stiff rod, so it has a lower *and* an upper bound: one
  that is too long holds the domains apart at a fixed separation just as surely
  as one that is too short fails to reach.

A linker of ``n`` residues inserted between two anchor Ca atoms makes a chain of
``n + 1`` virtual Ca-Ca bonds, so span limits are computed over ``n + 1`` bonds,
not ``n``.

Nothing here predicts whether a construct folds, expresses or works.
"""

from __future__ import annotations

from math import ceil, exp, floor, sqrt

from .constants import (
    CA_VIRTUAL_BOND_ANGSTROM,
    DEFAULT_GS_COMPOSITION,
    EXTENDED_RISE_DEFAULT_ANGSTROM,
    EXTENDED_RISE_RANGE_ANGSTROM,
    GS_CHAIN_STATISTICS,
    HELIX_RISE_DEFAULT_ANGSTROM,
    HELIX_RISE_RANGE_ANGSTROM,
    LINKER_TYPES,
)

# A helical linker's two junction bonds to the flanking domains need not be
# helical, so a rod-length mismatch of up to one virtual Ca-Ca bond at each end
# can be absorbed. This is a stated modelling choice, not a measured constant.
HELICAL_JUNCTION_TOLERANCE_ANGSTROM = 2.0 * CA_VIRTUAL_BOND_ANGSTROM

# Fraction of contour length beyond which a flexible linker must be close to
# fully extended to reach. Reported as a strain flag, not a feasibility cutoff.
NEAR_FULL_EXTENSION_FRACTION = 0.8


def _check_distance(distance: float) -> None:
    if distance < 0:
        raise ValueError("Attachment-point distance cannot be negative")


def _check_count(residues: int) -> None:
    if residues < 0:
        raise ValueError("Linker residue count cannot be negative")


def maximum_span(residues: int, rise: float = CA_VIRTUAL_BOND_ANGSTROM) -> float:
    """Longest anchor-to-anchor distance an ``residues``-long linker can cover.

    Uses the physical ceiling by default, so this is the widest span the linker
    could possibly reach, not a comfortable one.
    """
    _check_count(residues)
    if rise <= 0:
        raise ValueError("Per-residue rise must be positive")
    return (residues + 1) * rise


def minimum_residues(distance: float, rise: float = CA_VIRTUAL_BOND_ANGSTROM) -> int:
    """Fewest linker residues whose full extension reaches ``distance``.

    The default rise is the 3.8 A virtual Ca-Ca bond, which is the *physical
    ceiling*, so the answer is a true lower bound: no shorter linker can reach,
    and the calculator never calls a length impossible when it is merely tight.
    Measured over every window of consecutive residues in the two committed
    real structures, no real segment exceeds this rise, while a 3.5 A rise is
    exceeded by short extended segments - which is why 3.5 is reported as a
    design figure and not used for the bound.

    Zero is a valid answer: it means the two anchors are close enough to be
    joined directly, with no linker residue at all.
    """
    _check_distance(distance)
    if rise <= 0:
        raise ValueError("Per-residue rise must be positive")
    return max(0, ceil(distance / rise) - 1)


def gaussian_rms_end_to_end(
    residues: int,
    characteristic_ratio: float,
    bond: float = CA_VIRTUAL_BOND_ANGSTROM,
) -> float:
    """Gaussian-chain RMS end-to-end distance, sqrt(C_inf * n) * b0."""
    _check_count(residues)
    if characteristic_ratio <= 0:
        raise ValueError("Characteristic ratio must be positive")
    return sqrt(characteristic_ratio * residues) * bond


def wormlike_rms_end_to_end(
    residues: int,
    persistence_length: float,
    bond: float = CA_VIRTUAL_BOND_ANGSTROM,
) -> float:
    """Kratky-Porod RMS end-to-end distance for a chain of ``residues`` residues."""
    _check_count(residues)
    if persistence_length <= 0:
        raise ValueError("Persistence length must be positive")
    contour = residues * bond
    if contour == 0:
        return 0.0
    ratio = persistence_length / contour
    mean_square = 2 * persistence_length * contour * (1 - ratio * (1 - exp(-1 / ratio)))
    return sqrt(mean_square)


def comfortable_residues(
    distance: float,
    composition: str = DEFAULT_GS_COMPOSITION,
    bond: float = CA_VIRTUAL_BOND_ANGSTROM,
    limit: int = 500,
) -> int | None:
    """Fewest residues whose *unstretched* RMS end-to-end distance reaches ``distance``.

    This is the length at which the linker no longer has to be extended to span
    the junction. It is always at least ``minimum_residues`` and is the number a
    designer who wants an unstrained tether should read.
    """
    _check_distance(distance)
    if composition not in GS_CHAIN_STATISTICS:
        raise ValueError(f"Unknown GS composition {composition!r}; have {sorted(GS_CHAIN_STATISTICS)}")
    _, characteristic_ratio = GS_CHAIN_STATISTICS[composition]
    for residues in range(0, limit + 1):
        if gaussian_rms_end_to_end(residues, characteristic_ratio, bond) >= distance:
            return residues
    return None


def flexible_window(
    distance: float,
    composition: str = DEFAULT_GS_COMPOSITION,
    bond: float = CA_VIRTUAL_BOND_ANGSTROM,
) -> dict[str, object]:
    """Required-length report for a flexible (GS-rich) linker."""
    _check_distance(distance)
    low_rise, high_rise = EXTENDED_RISE_RANGE_ANGSTROM
    persistence, characteristic_ratio = GS_CHAIN_STATISTICS[composition]
    comfortable = comfortable_residues(distance, composition, bond)
    return {
        "linker_type": "flexible",
        "attachment_distance_angstrom": round(distance, 3),
        # Three numbers, because they answer three different questions.
        "minimum_residues": minimum_residues(distance, CA_VIRTUAL_BOND_ANGSTROM),
        "minimum_residues_basis": (
            "Physical lower bound at the 3.8 A virtual Ca-Ca bond: nothing shorter can reach."
        ),
        "minimum_residues_design": minimum_residues(distance, EXTENDED_RISE_DEFAULT_ANGSTROM),
        "minimum_residues_design_basis": (
            "At the 3.5 A per-residue rise commonly quoted for extended linkers. One or two "
            "residues longer than the physical bound for short spans; use it to avoid "
            "designing a linker that only just reaches."
        ),
        # Conservative first: the smaller rise needs more residues.
        "minimum_residues_range": [
            minimum_residues(distance, high_rise),
            minimum_residues(distance, low_rise),
        ],
        "per_residue_rise_angstrom": CA_VIRTUAL_BOND_ANGSTROM,
        "per_residue_rise_range_angstrom": [low_rise, high_rise],
        "maximum_residues": None,
        "maximum_residues_reason": (
            "A flexible linker has no geometric upper bound; extra length costs "
            "configurational entropy and loosens relative domain orientation, which this "
            "calculator does not score."
        ),
        "unstrained_residues": comfortable,
        "chain_model": {
            "composition": composition,
            "persistence_length_angstrom": persistence,
            "characteristic_ratio": characteristic_ratio,
            "contour_per_residue_angstrom": bond,
        },
    }


def flexible_strain(
    distance: float,
    residues: int,
    composition: str = DEFAULT_GS_COMPOSITION,
    bond: float = CA_VIRTUAL_BOND_ANGSTROM,
) -> dict[str, object]:
    """How extended a flexible linker of ``residues`` residues must be to span ``distance``."""
    _check_distance(distance)
    _check_count(residues)
    persistence, characteristic_ratio = GS_CHAIN_STATISTICS[composition]
    contour = (residues + 1) * bond
    fraction = distance / contour if contour else float("inf")
    rms_gaussian = gaussian_rms_end_to_end(residues, characteristic_ratio, bond)
    rms_wormlike = wormlike_rms_end_to_end(residues, persistence, bond)
    return {
        "fraction_of_contour_required": round(fraction, 4),
        "near_full_extension": fraction >= NEAR_FULL_EXTENSION_FRACTION,
        "near_full_extension_fraction": NEAR_FULL_EXTENSION_FRACTION,
        "rms_end_to_end_gaussian_angstrom": round(rms_gaussian, 2),
        "rms_end_to_end_wormlike_angstrom": round(rms_wormlike, 2),
        "requires_stretching_beyond_rms": distance > rms_gaussian,
    }


def helical_span(residues: int, rise: float = HELIX_RISE_DEFAULT_ANGSTROM) -> float:
    """Axial anchor-to-anchor distance of an ``residues``-long helical linker."""
    return maximum_span(residues, rise)


def helical_window(
    distance: float,
    rise: float = HELIX_RISE_DEFAULT_ANGSTROM,
    tolerance: float = HELICAL_JUNCTION_TOLERANCE_ANGSTROM,
) -> dict[str, object]:
    """Required-length report for a rigid alpha-helical linker.

    Both ends of the window are real: the rod has to be long enough to reach and
    short enough not to push the domains apart.
    """
    _check_distance(distance)
    if tolerance < 0:
        raise ValueError("Tolerance cannot be negative")
    low_rise, high_rise = HELIX_RISE_RANGE_ANGSTROM
    shortest = max(0, ceil((distance - tolerance) / rise) - 1)
    longest = floor((distance + tolerance) / rise) - 1
    feasible = longest >= shortest and longest >= 0
    return {
        "linker_type": "helical",
        "attachment_distance_angstrom": round(distance, 3),
        "minimum_residues": shortest,
        "maximum_residues": longest if feasible else None,
        "minimum_residues_range": [
            max(0, ceil((distance - tolerance) / high_rise) - 1),
            max(0, ceil((distance - tolerance) / low_rise) - 1),
        ],
        "per_residue_rise_angstrom": rise,
        "per_residue_rise_range_angstrom": [low_rise, high_rise],
        "junction_tolerance_angstrom": tolerance,
        "window_exists": feasible,
        "maximum_residues_reason": (
            "A helical linker is modelled as a stiff rod: a rod longer than the window "
            "holds the two domains further apart than the chosen attachment points allow, "
            "which is a geometric failure in its own right."
        ),
    }


def required_length(
    distance: float,
    linker_type: str = "flexible",
    composition: str = DEFAULT_GS_COMPOSITION,
) -> dict[str, object]:
    """Minimum (and where it exists maximum) linker length for one anchor distance."""
    if linker_type not in LINKER_TYPES:
        raise ValueError(f"Unknown linker type {linker_type!r}; have {list(LINKER_TYPES)}")
    if linker_type == "flexible":
        return flexible_window(distance, composition)
    return helical_window(distance)


def verdict_for_requested_length(
    window: dict[str, object],
    requested_residues: int,
) -> dict[str, object]:
    """Turn a required-length window into a verdict for one requested length."""
    _check_count(requested_residues)
    minimum = int(window["minimum_residues"])  # type: ignore[arg-type]
    maximum = window["maximum_residues"]
    if requested_residues < minimum:
        verdict = "too_short"
        reason = (
            f"{requested_residues} residues cannot span "
            f"{window['attachment_distance_angstrom']} A; at least {minimum} are needed at "
            f"{window['per_residue_rise_angstrom']} A per residue."
        )
    elif maximum is not None and requested_residues > int(maximum):
        verdict = "too_long"
        reason = (
            f"{requested_residues} residues of rigid helix span more than the "
            f"{window['attachment_distance_angstrom']} A between the attachment points; "
            f"the window closes at {maximum} residues."
        )
    else:
        verdict = "bridgeable"
        reason = (
            f"{requested_residues} residues are within the required-length window "
            f"[{minimum}, {'unbounded' if maximum is None else maximum}] for "
            f"{window['attachment_distance_angstrom']} A."
        )
    return {"verdict": verdict, "reason": reason, "requested_residues": requested_residues}
