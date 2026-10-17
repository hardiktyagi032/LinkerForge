# Annotated linker catalog: cleaning and training-readiness audit

Date: 13 October 2026. The 24,763 inputs are exact-unique **linker
subsequences**, not 24,763 annotated full protein chains. This audit does not
convert an unobserved residue into a negative label.

## Completed checks

The source JSONL SHA-256 was checked against its original manifest before
processing. Each record was checked for a standard amino-acid alphabet,
nonempty sequence, declared length, recomputed sequence SHA-256, unique
sequence hash, known source keys, matching source objects, valid usage status,
UniProt coordinate-to-segment length, and required UniProt/NRPS/catalog source
identifiers. All **24,763/24,763 passed** these structural checks; zero were
rejected. The output was also validated against the new Draft 2020-12 JSON
Schema (24,763/24,763). Four focused contract tests passed using the bundled
Python environment; `pytest` itself was not installed, so the functions were
executed directly.

| Mutually exclusive review tier | Sequences |
| --- | ---: |
| Protected benchmark, do not train | 455 |
| Quarantined pending overlap audit | 404 |
| Explicit UniProt linker region, evidence/homology review pending | 14,009 |
| Other existing linker annotation, ontology/homology review pending | 1,762 |
| NRPS intermodular annotation, parent-protein mapping pending | 8,133 |
| **Total validated** | **24,763** |

Source-key counts overlap because one exact linker string may occur in more
than one source: existing catalog 2,621; NRPS 8,133; UniProt 14,011.

## What this export does and does not certify

The clean export retains the positive sequence, source IDs, coordinate/evidence
objects where available, original provenance, and an explicit review tier.
It is useful for provenance review, positive-linker-sequence analysis, and
future auxiliary pretraining *after* overlap and family gates.

It does **not** provide full parent-protein sequences, verified nonlinker
residues, or a homology-separated train/development/test split. Therefore
**zero records are currently certified as ready for supervised CAID-style DFL
segmentation training**. Passing syntax and coordinate-length checks is not
biological adjudication. The earlier catalog collapsed some repeated source
observations by exact linker string; the first retained accession is not an
exhaustive map of every protein containing that string. Restore observation
lineage from the underlying sources before group splitting.

## Artifacts and next data gate

- Reproducible audit: `scripts/audit_annotated_linker_training_readiness.py`
- Formal schema: `schemas/validated_linker_subsequence.v1.schema.json`
- Tests: `tests/test_annotated_linker_training_readiness.py`
- Ignored derived records:
  `data/processed/linker_catalog/training_readiness_v1/validated_linker_subsequences.v1.jsonl`
- Machine-readable counts, source/output hashes, script hash and commit:
  `data/processed/linker_catalog/training_readiness_v1/manifest.v1.json`

Next: rebuild a lossless source-observation table, map each labelled linker to
its full parent protein, preserve other residues as `unknown` unless an
independent source explicitly supports `0`, then cluster full proteins and
hold out entire families. Only after that should the CNN, SAM-like, and
YOLO-style heads be trained on a common expanded DFL split. No training job
was active or launched during this audit.
