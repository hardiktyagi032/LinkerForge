"""Compositional features for linker sequences.

Feature choice is deliberately tiny and is traceable to published composition
rules rather than tuned on this project's data.  Chen, Zaro and Shen (2013)
state that flexible linkers are "generally composed of small, non-polar (e.g.
Gly) or polar (e.g. Ser or Thr) amino acids" and that rigid linkers "exhibit
relatively stiff structures by adopting alpha-helical structures or by
containing multiple Pro residues".  Those two sentences name exactly five
residue groups, and those five groups are the features.

Adding more features would make the model look stronger on a library of this
size without making it more trustworthy, so do not add any without a new
labelled source to justify them.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"

# Residue groups named by the published composition rules.
_GROUPS: Dict[str, str] = {
    "frac_G": "G",       # small non-polar, flexible per Chen 2013
    "frac_ST": "ST",     # small polar, flexible per Chen 2013
    "frac_P": "P",       # multiple Pro -> rigid per Chen 2013
    "frac_A": "A",       # alanine, the bulk of the EAAAK helical repeat
    "frac_EK": "EK",     # the charged pair of the EAAAK helical repeat
}

FEATURE_NAMES: List[str] = list(_GROUPS) + ["length_scaled"]

# Length is divided by this so the feature sits on roughly the same scale as the
# fractions.  Chosen as the upper bound of the project's frozen linker length
# range (README section 1: 5-30 residues), not fitted.
_LENGTH_SCALE = 30.0


def feature_names() -> List[str]:
    """Return the feature order used by :func:`featurise`."""
    return list(FEATURE_NAMES)


def _validate(sequence: str) -> str:
    if not sequence:
        raise ValueError("sequence is empty")
    seq = sequence.strip().upper()
    bad = sorted(set(seq) - set(AMINO_ACIDS))
    if bad:
        raise ValueError(
            "sequence contains non-standard residue(s) %s; this module takes "
            "one-letter standard amino acids only" % ", ".join(bad)
        )
    return seq


def composition_features(sequence: str) -> Dict[str, float]:
    """Return the named compositional features of ``sequence``."""
    seq = _validate(sequence)
    n = float(len(seq))
    out: Dict[str, float] = {}
    for name, residues in _GROUPS.items():
        out[name] = sum(seq.count(r) for r in residues) / n
    out["length_scaled"] = n / _LENGTH_SCALE
    return out


def featurise(sequence: str) -> List[float]:
    """Return ``sequence`` as a feature vector in :func:`feature_names` order."""
    feats = composition_features(sequence)
    return [feats[name] for name in FEATURE_NAMES]


def featurise_many(sequences: Sequence[str]) -> List[List[float]]:
    return [featurise(s) for s in sequences]
