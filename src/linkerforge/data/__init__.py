"""Auditable, fixture-level natural interdomain-linker extraction.

This package does not fetch or parse PDB/CATH data. Callers must first reconcile
their source numbering against a canonical one-based chain sequence.
"""

from .adjudication import (
    AdjudicationConfig,
    AdjudicationResult,
    ChainSequence,
    DomainAssignment,
    Provenance,
    ResidueMap,
    SourceMetadata,
    extract_natural_example,
)

__all__ = [
    "AdjudicationConfig",
    "AdjudicationResult",
    "ChainSequence",
    "DomainAssignment",
    "Provenance",
    "ResidueMap",
    "SourceMetadata",
    "extract_natural_example",
]
