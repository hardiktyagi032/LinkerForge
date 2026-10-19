"""Deterministic linker geometry: required linker length, accessibility, occlusion.

No training, no fitted thresholds and no GPU. Every constant is sourced in
``constants.CITATIONS``. The package answers how long a linker has to be for a
pair of attachment points, how exposed those points are, whether the straight
path crosses a domain, and whether several simultaneous tethers can be
satisfied by one rigid-body placement.
"""

from .junction import evaluate_junction, evaluate_tether_set, exit_vector
from .span import (
    comfortable_residues,
    flexible_strain,
    flexible_window,
    helical_window,
    maximum_span,
    minimum_residues,
    required_length,
    verdict_for_requested_length,
)
from .structure import read_chain, read_chains
from .tether import (
    TetherConstraint,
    find_placement,
    implied_chain_topology,
    pairwise_consistency,
    placement_violation,
)

__all__ = [
    "TetherConstraint",
    "comfortable_residues",
    "evaluate_junction",
    "evaluate_tether_set",
    "exit_vector",
    "find_placement",
    "flexible_strain",
    "flexible_window",
    "helical_window",
    "implied_chain_topology",
    "maximum_span",
    "minimum_residues",
    "pairwise_consistency",
    "placement_violation",
    "read_chain",
    "read_chains",
    "required_length",
    "verdict_for_requested_length",
]
