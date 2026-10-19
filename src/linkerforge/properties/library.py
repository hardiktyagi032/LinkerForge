"""Loader for the curated linker property library.

The library file is hand-curated with a citation per entry.  This module only
reads it and applies the file's own exclusion flags; it never fills in a label
or a sequence the source did not give.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_LIBRARY_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "curated"
    / "linker_property_library_sources.v1.json"
)


@dataclass(frozen=True)
class LibraryEntry:
    entry_id: str
    sequence: Optional[str]
    sequence_as_printed: str
    notation: str
    rigidity_label: str
    rigidity_basis: str
    rigidity_mechanism: Optional[str]
    cleavability_label: str
    cleavability_basis: str
    protease: Optional[str]
    source_key: str
    source_locator: str
    attributed_origin: str
    attributed_doi: Optional[str]
    fusion_context: Optional[str]
    excluded_from_model: bool
    exclusion_reason: Optional[str]
    cleavage_after_index: Optional[int]
    notes: Optional[str]

    @property
    def length(self) -> Optional[int]:
        return None if self.sequence is None else len(self.sequence)


@dataclass(frozen=True)
class Library:
    library_id: str
    curated_on: str
    sources: Dict[str, Any]
    entries: List[LibraryEntry]
    composite_templates: List[Dict[str, Any]]
    acquisition_status: Dict[str, str]
    raw: Dict[str, Any]

    def by_id(self, entry_id: str) -> LibraryEntry:
        for entry in self.entries:
            if entry.entry_id == entry_id:
                return entry
        raise KeyError(entry_id)

    def citation_for(self, entry: LibraryEntry) -> str:
        """Return a citation string that is honest about attribution depth."""
        source = self.sources[entry.source_key]
        base = "%s (%s)" % (source["citation"], entry.source_locator)
        if entry.attributed_doi:
            return "%s, attributing to %s [%s]" % (
                base,
                entry.attributed_origin,
                entry.attributed_doi,
            )
        return "%s, attributing to %s (primary DOI not verified)" % (
            base,
            entry.attributed_origin,
        )


def _entry_from_dict(raw: Dict[str, Any]) -> LibraryEntry:
    rigidity = raw["rigidity"]
    cleavability = raw["cleavability"]
    return LibraryEntry(
        entry_id=raw["entry_id"],
        sequence=raw["sequence"],
        sequence_as_printed=raw["sequence_as_printed"],
        notation=raw["notation"],
        rigidity_label=rigidity["label"],
        rigidity_basis=rigidity["basis"],
        rigidity_mechanism=rigidity.get("mechanism"),
        cleavability_label=cleavability["label"],
        cleavability_basis=cleavability["basis"],
        protease=cleavability.get("protease"),
        source_key=raw["source_key"],
        source_locator=raw["source_locator"],
        attributed_origin=raw["attributed_origin"],
        attributed_doi=raw["attributed_doi"],
        fusion_context=raw.get("fusion_context"),
        excluded_from_model=bool(raw.get("excluded_from_model", False)),
        exclusion_reason=raw.get("exclusion_reason"),
        cleavage_after_index=raw.get("cleavage_after_index"),
        notes=raw.get("notes"),
    )


def load_library(path: Optional[Path] = None) -> Library:
    """Load and lightly check the curated library."""
    path = Path(path) if path is not None else DEFAULT_LIBRARY_PATH
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)

    entries = [_entry_from_dict(item) for item in raw["entries"]]

    seen = set()
    for entry in entries:
        if entry.entry_id in seen:
            raise ValueError("duplicate entry_id %r" % entry.entry_id)
        seen.add(entry.entry_id)
        if entry.sequence is None and not entry.excluded_from_model:
            raise ValueError(
                "entry %r has no sequence but is not excluded from modelling"
                % entry.entry_id
            )
        if entry.source_key not in raw["sources"]:
            raise ValueError(
                "entry %r cites unknown source_key %r"
                % (entry.entry_id, entry.source_key)
            )

    return Library(
        library_id=raw["library_id"],
        curated_on=raw["curated_on"],
        sources=raw["sources"],
        entries=entries,
        composite_templates=raw.get("composite_templates", []),
        acquisition_status=raw.get("acquisition_status", {}),
        raw=raw,
    )


def modelling_subset(library: Library, axis: str) -> List[LibraryEntry]:
    """Entries usable for modelling one axis.

    An entry qualifies only if it has an exact sequence, is not flagged as
    excluded, and carries a real label on that axis.  ``unassigned`` is never
    treated as a class: an entry the source did not place on the axis is simply
    not available for that axis.
    """
    if axis not in {"rigidity", "cleavability"}:
        raise ValueError("axis must be 'rigidity' or 'cleavability'")
    out = []
    for entry in library.entries:
        if entry.sequence is None or entry.excluded_from_model:
            continue
        label = entry.rigidity_label if axis == "rigidity" else entry.cleavability_label
        if label == "unassigned":
            continue
        out.append(entry)
    return out
