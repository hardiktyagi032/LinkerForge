"""Versioned, fail-closed per-residue AlphaFold-derived feature registry.

Features (pLDDT, optional per-residue mean predicted aligned error) are keyed by
UniProt accession and bound to the exact sequence they were computed for. Every
lookup refuses missing accessions, sequence mismatches and length mismatches;
there is no imputation, default or fallback. This module never downloads.

File format (JSON), schema ``linkerforge.af_features.v1``::

    {"schema_version": "linkerforge.af_features.v1",
     "provenance": {"source": "...", "generated_independent_of_labels": true},
     "entries": {"P12345": {"sequence": "MKV...", "plddt": [..],
                            "pae_mean": [..]}}}   # pae_mean optional

``generated_independent_of_labels`` must be literally true: the program requires
predicted features to be generated independently of target labels.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SCHEMA_VERSION = "linkerforge.af_features.v1"
_ACCESSION = re.compile(r"^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})$")
_AA = frozenset("ACDEFGHIKLMNPQRSTVWY")


class StructureFeatureError(ValueError):
    """Raised for any malformed, missing or inconsistent structure feature."""


@dataclass(frozen=True)
class ResidueStructureFeatures:
    accession: str
    sequence: str
    plddt: np.ndarray            # float32, 0-100
    pae_mean: np.ndarray | None  # float32, >= 0, or None when not provided


class StructureFeatureRegistry:
    def __init__(self, entries: dict[str, ResidueStructureFeatures], provenance: dict):
        self._entries = entries
        self.provenance = provenance

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, accession: str) -> bool:
        return accession in self._entries

    def accessions(self) -> list[str]:
        return sorted(self._entries)

    def get(self, accession: str, sequence: str) -> ResidueStructureFeatures:
        """Return features for ``accession`` iff they were computed for ``sequence``."""
        sequence = sequence.upper()
        entry = self._entries.get(accession)
        if entry is None:
            raise StructureFeatureError(f"No structure features for accession {accession!r}")
        if len(entry.sequence) != len(sequence):
            raise StructureFeatureError(
                f"Length mismatch for {accession}: features {len(entry.sequence)}, query {len(sequence)}")
        if entry.sequence != sequence:
            raise StructureFeatureError(f"Sequence mismatch for {accession}")
        return entry

    def require_all(self, targets: dict[str, str]) -> None:
        """Fail unless every compared target (accession -> sequence) is covered and consistent."""
        problems = []
        for accession, sequence in targets.items():
            try:
                self.get(accession, sequence)
            except StructureFeatureError as error:
                problems.append(str(error))
        if problems:
            raise StructureFeatureError(
                f"{len(problems)} of {len(targets)} targets lack valid features: " + "; ".join(problems[:5]))


def _vector(value, name: str, length: int, low: float, high: float | None) -> np.ndarray:
    if not isinstance(value, list):
        raise StructureFeatureError(f"{name} must be a list")
    if len(value) != length:
        raise StructureFeatureError(f"{name} length {len(value)} != sequence length {length}")
    try:
        array = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as error:
        raise StructureFeatureError(f"{name} must be numeric") from error
    if array.ndim != 1 or not np.all(np.isfinite(array)):
        raise StructureFeatureError(f"{name} must be a finite 1-D vector")
    if array.min() < low or (high is not None and array.max() > high):
        raise StructureFeatureError(f"{name} outside valid range")
    return array.astype(np.float32)


def parse_registry(document: dict) -> StructureFeatureRegistry:
    if not isinstance(document, dict) or document.get("schema_version") != SCHEMA_VERSION:
        raise StructureFeatureError(f"Unsupported or missing schema_version (need {SCHEMA_VERSION})")
    provenance = document.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("generated_independent_of_labels") is not True:
        raise StructureFeatureError("provenance.generated_independent_of_labels must be true")
    if not provenance.get("source"):
        raise StructureFeatureError("provenance.source is required")
    raw = document.get("entries")
    if not isinstance(raw, dict) or not raw:
        raise StructureFeatureError("entries must be a non-empty object")
    entries = {}
    for accession, item in raw.items():
        if not _ACCESSION.match(accession):
            raise StructureFeatureError(f"Invalid UniProt accession {accession!r}")
        if not isinstance(item, dict):
            raise StructureFeatureError(f"Entry {accession} must be an object")
        extra = set(item) - {"sequence", "plddt", "pae_mean"}
        if extra:
            raise StructureFeatureError(f"Entry {accession} has unknown fields {sorted(extra)}")
        sequence = item.get("sequence")
        if not isinstance(sequence, str) or not sequence or set(sequence) - _AA:
            raise StructureFeatureError(f"Entry {accession} needs a canonical uppercase sequence")
        if "plddt" not in item:
            raise StructureFeatureError(f"Entry {accession} lacks plddt")
        plddt = _vector(item["plddt"], f"{accession}.plddt", len(sequence), 0.0, 100.0)
        pae = (_vector(item["pae_mean"], f"{accession}.pae_mean", len(sequence), 0.0, None)
               if "pae_mean" in item else None)
        entries[accession] = ResidueStructureFeatures(accession, sequence, plddt, pae)
    return StructureFeatureRegistry(entries, provenance)


def load_registry(path: str | Path) -> StructureFeatureRegistry:
    """Load a registry from a local JSON file; never fetches anything."""
    path = Path(path)
    if not path.is_file():
        raise StructureFeatureError(f"Feature file not found: {path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise StructureFeatureError(f"Invalid JSON in {path}") from error
    return parse_registry(document)
