"""Literature-sourced geometric constants for linker span calculations.

Every number here carries its source in ``CITATIONS``. Nothing in this module
is fitted to LinkerForge data and nothing is a biological pass/fail decision.
Where published values disagree the constant is stored as a range and the
caller is expected to report the range, not only the default.

Scope warning: these constants describe *polypeptide geometry*. They say
nothing about whether a construct folds, expresses or retains activity.
"""

from __future__ import annotations

CITATIONS: dict[str, str] = {
    "ca_virtual_bond": (
        "van Rosmalen, M., Krom, M., & Merkx, M. (2017). Tuning the flexibility of "
        "glycine-serine linkers to allow rational design of multidomain proteins. "
        "Biochemistry, 56(50), 6565-6574. https://doi.org/10.1021/acs.biochem.7b00902 "
        "- contour length per residue b0 = 3.8 A."
    ),
    "extended_rise": (
        "Pauling, L., & Corey, R. B. (1951). The pleated sheet, a new layer configuration "
        "of polypeptide chains. PNAS, 37(5), 251-256. https://doi.org/10.1073/pnas.37.5.251 "
        "- axial translation per residue in the pleated sheet, 3.3-3.5 A, i.e. the realistic "
        "fully extended rise; the 3.8 A virtual bond is the absolute trans-peptide ceiling."
    ),
    "helix_rise": (
        "Pauling, L., Corey, R. B., & Branson, H. R. (1951). The structure of proteins: two "
        "hydrogen-bonded helical configurations of the polypeptide chain. PNAS, 37(4), "
        "205-211. https://doi.org/10.1073/pnas.37.4.205 - alpha-helix translation per "
        "residue 1.47-1.5 A along the helix axis."
    ),
    "helical_linker_design": (
        "Arai, R., Ueda, H., Kitayama, A., Kamiya, N., & Nagamune, T. (2001). Design of the "
        "linkers which effectively separate domains of a bifunctional fusion protein. Protein "
        "Engineering, 14(8), 529-532. https://doi.org/10.1093/protein/14.8.529 - A(EAAAK)nA "
        "linkers form alpha-helices and separate domains by an amount that grows with n; the "
        "paper reports CD/FRET trends, not a per-residue rise, so the rise above is used."
    ),
    "gs_chain_statistics": (
        "van Rosmalen, M., Krom, M., & Merkx, M. (2017), Table 1 and eq 7 - persistence "
        "lengths and characteristic ratios C_inf for GS-rich linkers, and the Gaussian-chain "
        "relation <re^2> = C_inf * n * b0^2."
    ),
    "wlc": (
        "Kratky, O., & Porod, G. (1949). Rontgenuntersuchung geloster Fadenmolekule. Recueil "
        "des Travaux Chimiques des Pays-Bas, 68(12), 1106-1122. "
        "https://doi.org/10.1002/recl.19490681203 - worm-like chain mean square end-to-end "
        "distance used with the persistence lengths above."
    ),
    "sasa_algorithm": (
        "Shrake, A., & Rupley, J. A. (1973). Environment and exposure to solvent of protein "
        "atoms. Lysozyme and insulin. Journal of Molecular Biology, 79(2), 351-371. "
        "https://doi.org/10.1016/0022-2836(73)90011-9 - numerical sphere-point solvent "
        "accessible surface area with a 1.4 A water probe."
    ),
    "sasa_definition": (
        "Lee, B., & Richards, F. M. (1971). The interpretation of protein structures: "
        "estimation of static accessibility. Journal of Molecular Biology, 55(3), 379-400. "
        "https://doi.org/10.1016/0022-2836(71)90324-X - definition of solvent accessible "
        "surface area and the 1.4 A probe radius."
    ),
    "vdw_radii": (
        "Bondi, A. (1964). van der Waals volumes and radii. The Journal of Physical "
        "Chemistry, 68(3), 441-451. https://doi.org/10.1021/j100785a001"
    ),
    "max_asa": (
        "Tien, M. Z., Meyer, A. G., Sydykova, D. K., Spielman, S. J., & Wilke, C. O. (2013). "
        "Maximum allowed solvent accessibilites of residues in proteins. PLoS ONE, 8(11), "
        "e80635. https://doi.org/10.1371/journal.pone.0080635 - theoretical MaxASA values "
        "used to normalise ASA into relative solvent accessibility."
    ),
    "rsa_threshold": (
        "Rost, B., & Sander, C. (1994). Conservation and prediction of solvent accessibility "
        "in protein families. Proteins, 20(3), 216-226. https://doi.org/10.1002/prot.340200303 "
        "- the buried/exposed relative-accessibility convention. Published cutoffs range from "
        "about 5% to 25%; LinkerForge reports the value and all three bands rather than "
        "picking one."
    ),
    "disulfide_criteria": (
        "Sowdhamini, R., Srinivasan, N., Shoichet, B., Santi, D. V., Ramakrishnan, C., & "
        "Balaram, P. (1989). Stereochemical modeling of disulfide bridges: criteria for "
        "introduction into proteins by site-directed mutagenesis. Protein Engineering, 3(2), "
        "95-103. https://doi.org/10.1093/protein/3.2.95 - candidate pairs have Ca-Ca distance "
        "no more than 6.5 A and Cb-Cb no more than 4.5 A. The lower end of the Ca-Ca window "
        "used here is a steric floor set to one virtual Ca-Ca bond, not a published criterion."
    ),
    "interdomain_linker_lengths": (
        "George, R. A., & Heringa, J. (2002). An analysis of protein domain linkers: their "
        "classification and role in protein folding. Protein Engineering, 15(11), 871-879. "
        "https://doi.org/10.1093/protein/15.11.871 - natural interdomain linker length "
        "distribution, used only as context for reporting, never as a threshold."
    ),
}

# Virtual Ca-Ca bond length for a trans peptide unit. This is the hard ceiling on
# how far one residue can carry the chain, and it matches the 3.807 A mean measured
# over consecutive Ca atoms of PDB 4E43 chain A in tests/.
CA_VIRTUAL_BOND_ANGSTROM = 3.8

# Realistic fully extended rise per residue. Low end is the pleated-sheet axial
# translation, high end is the virtual bond itself. Two independent LinkerForge
# literature surveys reported 3.0-3.5 A/residue; 3.0 is below the pleated-sheet
# value and is treated as a conservative *design* figure rather than a geometric
# limit, so it is not used as the lower end of the physical range here.
EXTENDED_RISE_RANGE_ANGSTROM = (3.3, 3.8)
EXTENDED_RISE_DEFAULT_ANGSTROM = 3.5

# Alpha-helix rise along the helix axis, per residue.
HELIX_RISE_RANGE_ANGSTROM = (1.47, 1.5)
HELIX_RISE_DEFAULT_ANGSTROM = 1.5

# Composition-dependent chain statistics for GS-rich flexible linkers.
# persistence length (A), characteristic ratio C_inf.
GS_CHAIN_STATISTICS: dict[str, tuple[float, float]] = {
    "G4S2": (3.7, 1.9),
    "G2S4": (4.5, 2.4),
    "GS5": (4.8, 2.6),
    "S6": (6.2, 3.4),
}
# Default used when the linker composition is unknown: the most flexible measured
# GS repeat, which gives the *shortest* expected end-to-end distance and therefore
# the most conservative "is this length comfortable" answer.
DEFAULT_GS_COMPOSITION = "G4S2"

SOLVENT_PROBE_RADIUS_ANGSTROM = 1.4

# Bondi (1964) van der Waals radii, angstrom, for the elements in protein
# heavy-atom models. Hydrogens are not modelled; structures are treated as
# heavy-atom only and that is stated in every report.
VDW_RADII_ANGSTROM: dict[str, float] = {
    "C": 1.70,
    "N": 1.55,
    "O": 1.52,
    "S": 1.80,
    "P": 1.80,
    "SE": 1.90,
}

# Tien et al. (2013) theoretical MaxASA, angstrom^2, keyed by three-letter code.
MAX_ASA_ANGSTROM2: dict[str, float] = {
    "ALA": 129.0,
    "ARG": 274.0,
    "ASN": 195.0,
    "ASP": 193.0,
    "CYS": 167.0,
    "GLU": 223.0,
    "GLN": 225.0,
    "GLY": 104.0,
    "HIS": 224.0,
    "ILE": 197.0,
    "LEU": 201.0,
    "LYS": 236.0,
    "MET": 224.0,
    "PHE": 240.0,
    "PRO": 159.0,
    "SER": 155.0,
    "THR": 172.0,
    "TRP": 285.0,
    "TYR": 263.0,
    "VAL": 174.0,
}

# Relative solvent accessibility bands. These are reporting bands taken from the
# spread of published cutoffs, not a learned threshold.
RSA_BURIED_BELOW = 0.09
RSA_EXPOSED_AT_OR_ABOVE = 0.25

# An engineered disulfide is a second tether with a completely different span
# constraint: a short fixed Ca-Ca window that does not depend on any residue
# count, because there is no chain to lengthen. Cb-Cb is the criterion the
# literature states; Ca anchors are used here, so the window is the Ca one and
# a passing pair still needs its side-chain geometry checked.
DISULFIDE_CA_CA_WINDOW_ANGSTROM = (3.8, 6.5)
DISULFIDE_CB_CB_MAXIMUM_ANGSTROM = 4.5

LINKER_TYPES = ("flexible", "helical")
TETHER_TYPES = ("flexible", "helical", "disulfide")
