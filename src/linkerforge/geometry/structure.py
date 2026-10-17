"""Minimal heavy-atom PDB reader for linker geometry.

Deliberately narrow: first model, ATOM records, blank or "A" alternate
locations, hydrogens discarded. Anything it cannot interpret unambiguously is
an error rather than a silent approximation, following
``linkerforge.structure.score``. HETATM records (ligands, waters, modified
residues) are never read, so a report produced from this reader describes the
protein heavy atoms only and says so.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .constants import VDW_RADII_ANGSTROM

Point = tuple[float, float, float]

_SKIPPED_ELEMENTS = frozenset({"H", "D"})


@dataclass(frozen=True)
class Atom:
    """One heavy atom with the van der Waals radius used for clearance tests."""

    name: str
    element: str
    point: Point
    radius: float


@dataclass(frozen=True)
class Residue:
    """One residue of one chain, keyed the way the PDB file keys it."""

    chain: str
    number: int
    insertion_code: str
    name: str
    atoms: tuple[Atom, ...]

    @property
    def key(self) -> tuple[str, int, str]:
        return (self.chain, self.number, self.insertion_code)

    @property
    def ca(self) -> Point:
        for atom in self.atoms:
            if atom.name == "CA":
                return atom.point
        raise ValueError(f"Residue {self.chain}{self.number}{self.insertion_code} has no CA atom")


@dataclass(frozen=True)
class Chain:
    """Residues of one chain in file order, with position lookup."""

    identifier: str
    residues: tuple[Residue, ...]

    def index_of(self, number: int, insertion_code: str = " ") -> int:
        for position, residue in enumerate(self.residues):
            if residue.number == number and residue.insertion_code == insertion_code:
                return position
        raise ValueError(f"Chain {self.identifier} has no residue {number}{insertion_code.strip()}")

    def residue(self, number: int, insertion_code: str = " ") -> Residue:
        return self.residues[self.index_of(number, insertion_code)]

    def span(self, first: int, last: int) -> tuple[Residue, ...]:
        """Residues from ``first`` to ``last`` inclusive, by PDB numbering.

        Numbering gaps are allowed and reported by the caller; what is refused
        is a span whose endpoints are absent, because that silently moves an
        attachment point.
        """
        start = self.index_of(first)
        end = self.index_of(last)
        if end < start:
            raise ValueError(f"Chain {self.identifier} span {first}-{last} is reversed")
        return self.residues[start : end + 1]


def _element_of(line: str, atom_name: str) -> str:
    recorded = line[76:78].strip().upper() if len(line) >= 78 else ""
    if recorded:
        return recorded
    for character in atom_name:
        if character.isalpha():
            return character.upper()
    raise ValueError(f"Cannot infer element for atom name {atom_name!r}")


def read_chains(path: str | Path) -> dict[str, Chain]:
    """Read first-model protein heavy atoms, grouped by chain.

    Alternate locations other than blank or "A" are discarded, which is the
    usual convention for a single-conformer geometric measurement; insertion
    codes are preserved rather than dropped.
    """
    ordered: dict[tuple[str, int, str], dict[str, object]] = {}
    saw_model = False
    with Path(path).open(encoding="utf-8") as handle:
        lines = handle.readlines()
    for line in lines:
        if line.startswith("MODEL "):
            if saw_model:
                break
            saw_model = True
            continue
        if line.startswith("ENDMDL"):
            break
        if not line.startswith("ATOM  ") or len(line) < 54:
            continue
        if line[16] not in (" ", "A"):
            continue
        atom_name = line[12:16].strip()
        element = _element_of(line, atom_name)
        if element in _SKIPPED_ELEMENTS:
            continue
        if element not in VDW_RADII_ANGSTROM:
            raise ValueError(f"No van der Waals radius for element {element!r} in {path}")
        try:
            number = int(line[22:26])
            point = (float(line[30:38]), float(line[38:46]), float(line[46:54]))
        except ValueError as exc:
            raise ValueError(f"Malformed ATOM record in {path}: {line.rstrip()}") from exc
        key = (line[21], number, line[26])
        record = ordered.setdefault(key, {"name": line[17:20].strip(), "atoms": []})
        atoms: list[Atom] = record["atoms"]  # type: ignore[assignment]
        if any(existing.name == atom_name for existing in atoms):
            continue
        atoms.append(Atom(atom_name, element, point, VDW_RADII_ANGSTROM[element]))
    if not ordered:
        raise ValueError(f"No usable protein ATOM records in {path}")

    chains: dict[str, list[Residue]] = {}
    for (chain, number, insertion_code), record in ordered.items():
        residue = Residue(
            chain=chain,
            number=number,
            insertion_code=insertion_code,
            name=str(record["name"]),
            atoms=tuple(record["atoms"]),  # type: ignore[arg-type]
        )
        chains.setdefault(chain, []).append(residue)
    return {
        identifier: Chain(identifier, tuple(residues)) for identifier, residues in chains.items()
    }


def read_chain(path: str | Path, chain: str) -> Chain:
    chains = read_chains(path)
    if chain not in chains:
        raise ValueError(f"Chain {chain!r} not found in {path}; present: {sorted(chains)}")
    return chains[chain]
