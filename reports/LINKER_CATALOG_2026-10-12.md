# LinkerForge annotated linker catalog — initial build

Run: `.venv-gpu\Scripts\python.exe scripts\build_linker_catalog.py`

The builder writes `data/processed/linker_catalog/observations.v1.jsonl`,
`unique_sequences.v1.jsonl`, and `manifest.v1.json`. Outputs are generated and
ignored by Git; the manifest includes SHA-256 hashes for reproduction. Formal
schemas are in `schemas/linker_catalog_observation.v1.schema.json` and
`schemas/linker_catalog_unique.v1.schema.json`. Tests:
`.venv-gpu\Scripts\python.exe -m unittest tests.test_linker_catalog -v`.

| Source | Positive span observations | Ontology | Catalog use |
|---|---:|---|---|
| DisProt 2026_06 | 460 | Explicit curated flexible-linker term | Quarantine pending overlap/domain-pair audit |
| DLD | 2,265 | 1,626 IDL and 639 DDL spans | Preserve train/validation vs blind split |
| CAID3 Linkers | 37 | Disordered flexible linker | Protected benchmark only |

Total: **2,762 observations**, **2,621 exact unique sequences**. Thirty-nine
unique sequences occur in multiple sources; 48 carry multiple label types.
Four hundred fifty-five unique sequences touch a protected blind/benchmark
source. A unique sequence is an index entry, not an independent training
example: identical strings can occur in unrelated contexts, while homologous
proteins can carry different strings. Source observations are never discarded.

SynLinker's published 2,260-linker count is **not** ingested: the row-level
dataset is not locally retrievable. A source count is not a substitute for
records. The config records this absence so an adapter can be added later if
the original file is obtained. This initial catalog is not an exhaustive survey
of all public databases and is **not train-ready**. Next gates: review licenses,
normalize coordinate/reference versions, audit cross-source protein/homology
overlap, adjudicate different linker ontologies, and create split-safe training
records. DLD label 0 must not be treated as a verified non-linker negative.
