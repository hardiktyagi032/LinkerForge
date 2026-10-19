"""Linker property labelling: the two design axes a conditional linker generator
would be conditioned on.

Axis 1 (cleavability) is motif-driven and is answered by a curated motif table,
not by a learned model.  Axis 2 (rigidity) is compositional and is answered by a
small calibrated linear model.  The split is deliberate and is the central
finding of reports/LINKER_PROPERTY_LIBRARY_2026-10-17.md: only one of the two
axes is a learning problem at all.
"""

from .features import (
    AMINO_ACIDS,
    composition_features,
    feature_names,
    featurise,
)
from .cleavability import (
    CleavabilityCall,
    MOTIF_TABLE,
    call_cleavability,
)
from .rigidity import (
    RigidityModel,
    fit_rigidity_model,
    leave_one_out_report,
)
from .library import (
    LibraryEntry,
    load_library,
    modelling_subset,
)

__all__ = [
    "AMINO_ACIDS",
    "composition_features",
    "feature_names",
    "featurise",
    "CleavabilityCall",
    "MOTIF_TABLE",
    "call_cleavability",
    "RigidityModel",
    "fit_rigidity_model",
    "leave_one_out_report",
    "LibraryEntry",
    "load_library",
    "modelling_subset",
]
