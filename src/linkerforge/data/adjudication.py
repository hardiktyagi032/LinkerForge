"""Conservative extraction of candidate linkers between annotated domains.

Coordinates in this module are *canonical sequence* coordinates, one-based and
inclusive. PDB author/label numbering must be mapped explicitly by an upstream
adapter; this module deliberately never assumes those systems are equivalent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


_AMINO_ACIDS = frozenset("ACDEFGHIKLMNPQRSTVWY")


@dataclass(frozen=True)
class ResidueMap:
    sequence_position: int
    author_number: int | None
    author_insertion_code: str = ""
    label_seq_id: int | None = None
    resolved: bool = True


@dataclass(frozen=True)
class ChainSequence:
    sequence: str
    residues: tuple[ResidueMap, ...]
    # Explicitly set by a source adapter after checking chain continuity.
    continuous: bool = True
    engineered: bool = False
    proteolytically_cleaved: bool = False


@dataclass(frozen=True)
class DomainAssignment:
    start: int
    end: int
    family_ids: tuple[str, ...] = ()
    annotation_source: str = "CATH"
    continuous: bool = True


@dataclass(frozen=True)
class SourceMetadata:
    pdb_id: str
    chain_id: str
    uniprot_id: str | None
    retrieved_at: str
    structure_tier: str = "experimental"


@dataclass(frozen=True)
class Provenance:
    pipeline_commit: str
    config_hash: str
    software: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AdjudicationConfig:
    minimum_length: int = 5
    maximum_length: int = 30
    require_resolved_junctions: bool = True
    # An annotation gap is not automatically a verified linker. A separate
    # human/structural adjudication is needed for high-quality evidence.
    evidence_quality: str = "uncertain"


@dataclass(frozen=True)
class AdjudicationResult:
    accepted: bool
    record: dict[str, Any] | None
    reason_codes: tuple[str, ...]
    source: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "record": self.record,
            "reason_codes": list(self.reason_codes),
            "source": self.source,
        }


def _source_record(source: SourceMetadata) -> dict[str, Any]:
    return {
        "pdb_id": source.pdb_id,
        "chain_id": source.chain_id,
        "uniprot_id": source.uniprot_id,
        "retrieved_at": source.retrieved_at,
        "structure_tier": source.structure_tier,
    }


def _domain_record(domain: DomainAssignment, sequence: str) -> dict[str, Any]:
    return {
        "start": domain.start,
        "end": domain.end,
        "sequence": sequence[domain.start - 1 : domain.end],
        "family_ids": list(domain.family_ids),
        "annotation_source": domain.annotation_source,
    }


def extract_natural_example(
    chain: ChainSequence,
    domains: tuple[DomainAssignment, DomainAssignment],
    source: SourceMetadata,
    provenance: Provenance,
    config: AdjudicationConfig | None = None,
) -> AdjudicationResult:
    """Adjudicate a *candidate* linker; never infer experimental function.

    Returns a rejection log for invalid/ambiguous inputs, rather than raising
    for source-data defects. Programmer errors (wrong number of domains) raise.
    """
    if len(domains) != 2:
        raise ValueError("Exactly two ordered domain assignments are required")
    config = config or AdjudicationConfig()
    domain_a, domain_b = domains
    reasons: list[str] = []
    sequence = chain.sequence.upper()
    if not sequence or any(aa not in _AMINO_ACIDS for aa in sequence):
        reasons.append("INVALID_SEQUENCE")
    if len(chain.residues) != len(sequence):
        reasons.append("INCOMPLETE_RESIDUE_MAP")
    elif tuple(r.sequence_position for r in chain.residues) != tuple(
        range(1, len(sequence) + 1)
    ):
        reasons.append("NONCANONICAL_RESIDUE_MAP")
    if len(set((r.author_number, r.author_insertion_code) for r in chain.residues if r.author_number is not None)) != sum(r.author_number is not None for r in chain.residues):
        reasons.append("AMBIGUOUS_AUTHOR_NUMBERING")
    if not chain.continuous:
        reasons.append("CHAIN_BREAK")
    if chain.engineered:
        reasons.append("ENGINEERED_CONSTRUCT")
    if chain.proteolytically_cleaved:
        reasons.append("PROTEOLYTIC_CLEAVAGE")
    if source.structure_tier != "experimental":
        reasons.append("NONEXPERIMENTAL_STRUCTURE")
    if not (source.pdb_id and source.chain_id and source.retrieved_at):
        reasons.append("MISSING_SOURCE_ID")
    if not provenance.pipeline_commit or not provenance.config_hash:
        reasons.append("MISSING_PROVENANCE")
    if not (1 <= domain_a.start <= domain_a.end <= len(sequence)) or not (
        1 <= domain_b.start <= domain_b.end <= len(sequence)
    ):
        reasons.append("DOMAIN_OUT_OF_RANGE")
    if not domain_a.continuous or not domain_b.continuous:
        reasons.append("NONCONTIGUOUS_DOMAIN")
    if domain_a.end >= domain_b.start:
        reasons.append("OVERLAPPING_OR_REVERSED_DOMAINS")
    linker_start = domain_a.end + 1
    linker_end = domain_b.start - 1
    linker_length = linker_end - linker_start + 1
    if not (config.minimum_length <= linker_length <= config.maximum_length):
        reasons.append("LINKER_LENGTH_OUT_OF_RANGE")
    if len(chain.residues) == len(sequence) and 1 <= domain_a.end < domain_b.start <= len(sequence):
        junction = chain.residues[domain_a.end - 1 : domain_b.start]
        if config.require_resolved_junctions and not all(r.resolved for r in junction):
            reasons.append("UNRESOLVED_JUNCTION")
        if any(r.author_number is None or r.label_seq_id is None for r in junction):
            reasons.append("UNMAPPED_JUNCTION_NUMBERING")
    if config.evidence_quality not in {"high", "medium", "uncertain"}:
        reasons.append("INVALID_EVIDENCE_QUALITY")
    if reasons:
        return AdjudicationResult(False, None, tuple(dict.fromkeys(reasons)), _source_record(source))

    linker_sequence = sequence[linker_start - 1 : linker_end]
    junction_mapping = [
        {
            "sequence_position": r.sequence_position,
            "author_number": r.author_number,
            "author_insertion_code": r.author_insertion_code,
            "label_seq_id": r.label_seq_id,
            "resolved": r.resolved,
        }
        for r in chain.residues[domain_a.end - 1 : domain_b.start]
    ]
    record = {
        "schema_version": "0.1.0",
        "example_id": f"{source.pdb_id.lower()}_{source.chain_id}_{domain_a.start}-{domain_a.end}_{domain_b.start}-{domain_b.end}",
        "source": _source_record(source),
        "source_record_type": "natural_observation",
        "domain_a": _domain_record(domain_a, sequence),
        "linker": {
            "start": linker_start,
            "end": linker_end,
            "sequence": linker_sequence,
            "length": linker_length,
            "class": "unknown",
            "evidence_quality": config.evidence_quality,
        },
        "domain_b": _domain_record(domain_b, sequence),
        "connection_features": {},
        "residue_mapping": junction_mapping,
        "provenance": {
            "pipeline_commit": provenance.pipeline_commit,
            "config_hash": provenance.config_hash,
            "software": provenance.software.copy(),
        },
    }
    return AdjudicationResult(True, record, (), _source_record(source))
