"""Model-independent structure measurements for complete fusion predictions."""

from .score import load_ca_pdb, score_fusion

__all__ = ["load_ca_pdb", "score_fusion"]
