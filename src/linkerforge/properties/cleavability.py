"""Cleavability calling: a cited motif lookup, not a learned classifier.

This module is intentionally not a model.  A protease recognition site is a
published consensus for a named protease, so deciding whether a linker is
cleavable by a *known* protease is a table lookup over cited motifs.  Deciding
whether an arbitrary novel peptide is cleavable by *some* protease is a
different and much harder problem (predicting protease specificity), and
nothing here attempts it.

Two consequences are built into the return type rather than left to the caller:

* The negative call is ``no_known_motif``, never ``non_cleavable``.  Absence of
  a motif from a table of this size is weak evidence.  The table covers the
  proteases one review happened to discuss; a sequence cleaved by a protease
  outside the table is a false negative this method cannot see.
* Every positive call carries the entry it matched, so the caller can print a
  citation instead of a bare label.

The motif table is derived from the curated library at load time, so there is
exactly one place where a motif and its citation live together, and no motif
exists in code without a source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .library import Library, LibraryEntry, load_library


@dataclass(frozen=True)
class MotifMatch:
    entry_id: str
    motif: str
    protease: str
    start: int  # 1-based inclusive
    end: int  # 1-based inclusive
    citation: str


@dataclass(frozen=True)
class CleavabilityCall:
    label: str  # "cleavable" | "no_known_motif"
    matches: Tuple[MotifMatch, ...] = field(default=())
    coverage_note: str = ""

    @property
    def proteases(self) -> List[str]:
        seen: List[str] = []
        for match in self.matches:
            if match.protease not in seen:
                seen.append(match.protease)
        return seen


def build_motif_table(library: Optional[Library] = None) -> Dict[str, LibraryEntry]:
    """Map each cited cleavable sequence to the library entry it came from."""
    lib = library if library is not None else load_library()
    table: Dict[str, LibraryEntry] = {}
    for entry in lib.entries:
        if entry.cleavability_label != "cleavable":
            continue
        if entry.sequence is None:
            continue
        table[entry.sequence] = entry
    return table


#: Lazily built default table, exposed for inspection and for tests.
MOTIF_TABLE: Dict[str, LibraryEntry] = {}


def _table(library: Optional[Library]) -> Tuple[Dict[str, LibraryEntry], Library]:
    global MOTIF_TABLE
    lib = library if library is not None else load_library()
    table = build_motif_table(lib)
    if library is None:
        MOTIF_TABLE = table
    return table, lib


_COVERAGE_NOTE = (
    "Negative calls mean no motif in this table matched, not that the sequence "
    "resists proteolysis. The table holds {n} cited motifs covering {k} named "
    "protease classes, all from one review's cleavable-linker section, so its "
    "recall against the full protease universe is unknown and certainly low."
)

_MIN_MOTIF_LENGTH = 4
_SHORT_MOTIF_NOTE = (
    "Motifs shorter than {m} residues ({short}) are excluded from substring "
    "matching: a two- or three-residue basic run occurs by chance in ordinary "
    "linkers and would make almost everything look cleavable. They remain in "
    "the library as cited entries."
)


def call_cleavability(
    sequence: str, library: Optional[Library] = None
) -> CleavabilityCall:
    """Call cleavability for ``sequence`` by cited-motif substring search."""
    table, lib = _table(library)
    seq = sequence.strip().upper()
    if not seq:
        raise ValueError("sequence is empty")

    usable = {m: e for m, e in table.items() if len(m) >= _MIN_MOTIF_LENGTH}
    short = sorted(m for m in table if len(m) < _MIN_MOTIF_LENGTH)

    matches: List[MotifMatch] = []
    for motif, entry in sorted(usable.items(), key=lambda kv: -len(kv[0])):
        start = seq.find(motif)
        while start != -1:
            matches.append(
                MotifMatch(
                    entry_id=entry.entry_id,
                    motif=motif,
                    protease=entry.protease or "unspecified",
                    start=start + 1,
                    end=start + len(motif),
                    citation=lib.citation_for(entry),
                )
            )
            start = seq.find(motif, start + 1)

    note = _COVERAGE_NOTE.format(
        n=len(usable),
        k=len({e.protease for e in usable.values()}),
    )
    if short:
        note += " " + _SHORT_MOTIF_NOTE.format(
            m=_MIN_MOTIF_LENGTH, short=", ".join(short)
        )

    return CleavabilityCall(
        label="cleavable" if matches else "no_known_motif",
        matches=tuple(matches),
        coverage_note=note,
    )
