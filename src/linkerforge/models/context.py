"""M6 scoring contract and a transparent, non-neural training fallback.

The fallback is a pairwise linear ranker fitted only to caller-supplied training
examples. It is not ESM-2 or a geometric GNN. Its score is an uncalibrated
within-query ranking value, never a probability of biological success.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, log2
from typing import Iterable


AMINO_ACIDS = frozenset("ACDEFGHIKLMNPQRSTVWY")
HYDROPHOBIC = frozenset("AVILMFWY")
CHARGED = frozenset("DEKRH")
FEATURE_NAMES = (
    "length_fraction",
    "glycine_fraction",
    "serine_fraction",
    "hydrophobic_fraction",
    "charged_fraction",
    "sequence_entropy",
    "port_a_accessibility",
    "port_b_accessibility",
    "port_a_contact_density",
    "port_b_contact_density",
    "length_by_mean_accessibility",
    "hydrophobic_by_mean_accessibility",
)


def _sequence(value: str, name: str) -> str:
    if not isinstance(value, str) or not value or set(value) - AMINO_ACIDS:
        raise ValueError(f"{name} must be a nonempty uppercase canonical amino-acid sequence")
    return value


def _unit(value: float, name: str) -> None:
    if not isinstance(value, (float, int)) or not isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be finite and between 0 and 1")


@dataclass(frozen=True)
class LocalPort:
    """Dimensionless measurements local to one structure's terminal port.

    Coordinate systems of separately uploaded domains are never compared here.
    Accessibility/contact density are measured independently within each domain.
    """

    accessibility: float
    contact_density: float

    def __post_init__(self) -> None:
        _unit(self.accessibility, "accessibility")
        _unit(self.contact_density, "contact_density")


@dataclass(frozen=True)
class ContextQuery:
    domain_a_sequence: str
    domain_b_sequence: str
    port_a: LocalPort
    port_b: LocalPort

    def __post_init__(self) -> None:
        _sequence(self.domain_a_sequence, "domain_a_sequence")
        _sequence(self.domain_b_sequence, "domain_b_sequence")
        if not isinstance(self.port_a, LocalPort) or not isinstance(self.port_b, LocalPort):
            raise ValueError("port_a and port_b must be LocalPort records")


@dataclass(frozen=True)
class NaturalTrainingPair:
    """One observed native linker versus constructed, unmeasured alternatives."""

    query: ContextQuery
    observed_linker: str
    synthetic_alternatives: tuple[str, ...]

    def __post_init__(self) -> None:
        _linker(self.observed_linker)
        if not self.synthetic_alternatives:
            raise ValueError("at least one synthetic alternative is required")
        for alternative in self.synthetic_alternatives:
            _linker(alternative)
            if alternative == self.observed_linker:
                raise ValueError("synthetic alternative cannot equal observed linker")


def _linker(sequence: str) -> str:
    _sequence(sequence, "linker sequence")
    if not 5 <= len(sequence) <= 30:
        raise ValueError("linker length must be 5 to 30 residues")
    return sequence


def candidate_features(query: ContextQuery, linker_sequence: str) -> dict[str, float]:
    """Extract auditable baseline features, without hidden/native linker input."""
    if not isinstance(query, ContextQuery):
        raise TypeError("query must be ContextQuery")
    linker_sequence = _linker(linker_sequence)
    n = len(linker_sequence)
    counts = {aa: linker_sequence.count(aa) for aa in set(linker_sequence)}
    entropy = -sum((count / n) * log2(count / n) for count in counts.values())
    mean_accessibility = (query.port_a.accessibility + query.port_b.accessibility) / 2
    length_fraction = n / 30
    hydrophobic_fraction = sum(aa in HYDROPHOBIC for aa in linker_sequence) / n
    return {
        "length_fraction": length_fraction,
        "glycine_fraction": linker_sequence.count("G") / n,
        "serine_fraction": linker_sequence.count("S") / n,
        "hydrophobic_fraction": hydrophobic_fraction,
        "charged_fraction": sum(aa in CHARGED for aa in linker_sequence) / n,
        "sequence_entropy": entropy / log2(20),
        "port_a_accessibility": query.port_a.accessibility,
        "port_b_accessibility": query.port_b.accessibility,
        "port_a_contact_density": query.port_a.contact_density,
        "port_b_contact_density": query.port_b.contact_density,
        "length_by_mean_accessibility": length_fraction * mean_accessibility,
        "hydrophobic_by_mean_accessibility": hydrophobic_fraction * mean_accessibility,
    }


class UnconfiguredContextModel:
    """Honest placeholder for the intended frozen-ESM/local-graph architecture."""

    name = "esm2-local-port-gnn-linker-encoder"
    status = "unconfigured"

    def score(self, query: ContextQuery, linker_sequence: str) -> float:
        candidate_features(query, linker_sequence)
        raise RuntimeError("ESM-2/GNN model is unconfigured; no neural score exists")


class PairwiseHandFeatureRanker:
    """Deterministic pairwise hinge-loss ranker, as an explicit baseline only.

    Callers must supply *training-partition-only* records. This class cannot
    infer or enforce homology partitions; that belongs to the split manifest.
    """

    name = "pairwise-hand-feature-linear-baseline"

    def __init__(self) -> None:
        self._weights: tuple[float, ...] | None = None
        self.training_pairs = 0

    @property
    def status(self) -> str:
        return "fitted_baseline" if self._weights is not None else "untrained"

    @property
    def weights(self) -> dict[str, float] | None:
        return None if self._weights is None else dict(zip(FEATURE_NAMES, self._weights))

    def fit(
        self,
        examples: Iterable[NaturalTrainingPair],
        *,
        epochs: int = 50,
        learning_rate: float = 0.05,
        l2: float = 0.001,
    ) -> "PairwiseHandFeatureRanker":
        if epochs < 1 or not isfinite(learning_rate) or learning_rate <= 0 or not isfinite(l2) or l2 < 0:
            raise ValueError("invalid optimizer parameters")
        rows: list[tuple[float, ...]] = []
        for example in examples:
            if not isinstance(example, NaturalTrainingPair):
                raise TypeError("examples must contain NaturalTrainingPair records")
            observed = candidate_features(example.query, example.observed_linker)
            for alternative in example.synthetic_alternatives:
                negative = candidate_features(example.query, alternative)
                difference = tuple(observed[name] - negative[name] for name in FEATURE_NAMES)
                if any(difference):
                    rows.append(difference)
        if not rows:
            raise ValueError("training requires at least one distinct feature pair")
        weights = [0.0] * len(FEATURE_NAMES)
        for _ in range(epochs):
            for difference in rows:
                margin = sum(weight * value for weight, value in zip(weights, difference))
                weights = [weight * (1 - learning_rate * l2) for weight in weights]
                if margin < 1:
                    weights = [weight + learning_rate * value for weight, value in zip(weights, difference)]
        self._weights = tuple(weights)
        self.training_pairs = len(rows)
        return self

    def score(self, query: ContextQuery, linker_sequence: str) -> float:
        if self._weights is None:
            raise RuntimeError("hand-feature baseline is untrained")
        features = candidate_features(query, linker_sequence)
        score = sum(weight * features[name] for weight, name in zip(self._weights, FEATURE_NAMES))
        if not isfinite(score):
            raise ArithmeticError("nonfinite model score")
        return score
