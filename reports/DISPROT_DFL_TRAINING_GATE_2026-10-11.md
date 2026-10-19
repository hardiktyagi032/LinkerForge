# DisProt DFL training eligibility gate — 11 October 2026

Status: **not yet trainable**. This is an audit of the local DisProt 2026_06
release, not a training split or an independent test.

Source: `data/raw/disprot/disprot_2026_06_regions.json` (ignored local API
response); reference: `artifacts/caid3-linker.fasta` (official CAID3 Linker
reference). The extraction contract in
`scripts/extract_disprot_flexible_linkers.py` identifies functional term
`IDPO:0000033` and preserves the original region evidence.
The reproducible per-protein exclusion record is
`reports/disprot_caid3_exclusions_2026-10-11.json`, built by
`scripts/audit_disprot_caid3_exclusions.py` and validated against
`schemas/dfl-training-exclusion-audit.schema.json`.

| Check | Count |
| --- | ---: |
| Local DisProt entries | 3,337 |
| Entries with explicit DFL term | 360 |
| Explicit DFL regions | 460 |
| CAID3 reference entries also in this release | 31/31 |
| DFL regions on those 31 entries | 41 |
| Remaining entries after exact DisProt-ID exclusion | 329 |
| Remaining explicit DFL regions | 419 |
| Additional shared nonempty UniRef50 / UniRef90 IDs among remaining entries and the 31 CAID entries | 0 / 0 |

The UniRef check is a **screen only**: absent or stale cluster IDs and remote
homology can still cause leakage. The 329 proteins and 419 regions are not
certified independent of CAID3. CAID3 is public and is not a fresh blind test.

Most importantly, this response contains *positive functional annotations*,
not a complete residue-level census of verified non-linkers. A residue without
`IDPO:0000033` is **unknown**, not a verified negative. Other DisProt function
terms on the same protein do not automatically establish a negative either:
annotations may overlap, be incomplete, or describe a different ontology.
Using all unannotated residues as zero labels would train an unvalidated
closed-world classifier and inflate apparent accuracy. No no-linker-protein
specificity can be measured from these positives alone.

Next gate: document a source-supported negative/unknown policy; run a
sequence-level homology screen across all sources; freeze nonoverlapping
train/development groups; add adjudicated no-linker proteins. Only then run a
matched residue-head versus span-head DFL experiment. Until then, do not
launch DFL GPU training or score the public CAID3 reference for model
selection.
