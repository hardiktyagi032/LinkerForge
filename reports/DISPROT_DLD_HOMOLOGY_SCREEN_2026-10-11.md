# DisProt–DLD overlap screen: candidate homologs, not an independent test

The 2026_06 DisProt extraction contains 460 explicit flexible-linker regions
in 360 proteins. The accession screen identified 68 regions with the same
UniProt accession as at least one DLD record. A separate local-alignment
screen compared all 360 proteins against the 2,620 DLD records across train,
validation, and previously viewed fold 5. It flags **106 regions in 79
DisProt proteins**, including **38 regions beyond** the accession screen.
Twenty-four different-accession DisProt proteins have at least one flagged
candidate match in DLD training. This is a potential contamination warning,
not a verified family assignment. The 354 unflagged regions are **not
certified independent**.

The screen used 5-mer sharing to select up to 20 DLD candidates per protein,
then local sequence alignment. A hit required at least 40 aligned residues,
at least 30% identity, and at least 30% coverage of the shorter sequence.
Full parameters, source/config/script hashes, software version, source IDs,
split assignments, and individual matches are in
`reports/disprot_dld_homology_screen_2026-10-11.json`. Same-accession and
direct-sequence coordinate status are in
`reports/disprot_dld_accession_overlap_2026-10-11.json`.

This two-stage heuristic can miss remote homology, low-complexity matches,
isoforms, or domains not selected by the top-20 k-mer prescreen. Conversely,
some local matches may be false homology flags. Neither the curated flexible-
linker term nor an alignment confirms the region connects two independently
folding domains. Residue-coordinate mapping, domain context, manual
adjudication, and a stronger all-against-all homology-clustering audit are
still needed. No DisProt record is used as an independent benchmark or for
training in this round.
