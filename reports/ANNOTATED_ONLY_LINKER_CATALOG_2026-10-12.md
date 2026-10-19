# Annotated-only linker catalog

Date: 2026-10-12. This is a **separate** export. The original 113,285-sequence
discovery index remains unchanged, but inferred domain gaps alone do not
qualify as linker labels here.

## Exact contents

| Category | Exact-unique sequences |
|---|---:|
| Input discovery index | 113,285 |
| Retained with at least one explicitly linker-labeled source | **24,763** |
| Inferred-domain-gap-only records excluded | **88,522** |

Qualifying sources are: (1) the existing LinkerForge catalog with DLD/DisProt/
protected CAID3 linker labels, (2) the published NRPS CSV `Linker` field, and
(3) UniProt `REGION` features whose own note contains `linker`. Their distinct
per-source counts are 2,621, 8,133, and 14,011; overlap means these numbers do
not sum to 24,763. Any inferred-domain-gap source on a retained sequence is
**not** used to qualify it, and is omitted from its qualifying-source record.

The export also preserves data-use status: 455 sequences are protected
benchmark members, 404 are quarantined pending overlap audit, and 23,904 need
boundary and homology review. **None are marked training-ready.** Even an
explicit annotation is not the same as an experimentally established linker
function. Only 57 UniProt linker-region observations (56 distinct sequences)
in the source feed carried PubMed-linked ECO evidence, which must be checked
against the cited study before claiming a functional assay.

## Files and verification

- Table: `data/processed/linker_catalog/annotated_only_v1/annotated_linker_sequences.v1.tsv`
- Full qualifying-source records: `data/processed/linker_catalog/annotated_only_v1/annotated_linker_sequences.v1.jsonl.gz`
- Provenance/count manifest: `data/processed/linker_catalog/annotated_only_v1/manifest.v1.json`
- Frozen filter: `configs/annotated_only_linker_catalog_v1.json`
- Formal record schema: `schemas/annotated_linker_catalog.v1.schema.json`
- Rebuild: `python scripts/build_annotated_only_linker_catalog.py`

The JSONL and TSV each contain 24,763 rows and 24,763 distinct sequence
strings. Every JSONL record has at least one qualifying source identifier;
none has a domain-gap-only source in `qualifying_sources`. Eight parsing and
filter tests passed. The source-file SHA-256, config SHA-256, pipeline SHA-256,
Git commit, and output hashes are in the manifest.

## Deterministic coordinates versus linker evidence

Given a full protein sequence `S` and trusted consecutive domain boundaries
`A=[a_start,a_end]` and `B=[b_start,b_end]`, the intervening segment is exactly
`S[a_end+1 : b_start-1]` in one-based inclusive coordinates. That calculation
does **not** establish that the segment is a functional linker. This export
requires a source to explicitly label that segment as a linker.

Given **two independent domain sequences**, no coordinate subtraction can
recover a unique natural linker sequence: there is no observed intervening
sequence. If structures and attachment points are supplied, geometry can rule
out too-short connections and help rank feasible candidates, but many
sequences and conformations can satisfy the same endpoints. This is a
constraint/design problem, not deterministic sequence identification.

Relevant sources: UniProt feature records at https://rest.uniprot.org ;
Farag et al. NRPS linker dataset at
https://doi.org/10.1093/bioinformatics/btz127 ; and the discussion of
linker-length estimation from terminal geometry in CirPred at
https://pmc.ncbi.nlm.nih.gov/articles/PMC8513176/ .
