# LinkerForge scientific task board

This is the two-week computational implementation board. The canonical
scientific scope is in `README.md`; module acceptance criteria are in
`LINKERFORGE_TWO_WEEK_SCIENTIFIC_SPEC.md`. Four workstreams have non-overlapping
ownership. All current code is a fixture-tested skeleton, **not** a trained
end-to-end predictor or a publication result.

| Workstream | Current deliverable | Next reviewable task | Gate |
|---|---|---|---|
| Data and records | Pure-Python natural-linker adjudication with residue-number mapping and rejection codes | Add one live RCSB mmCIF + CATH adapter; manually verify 10 chains | No bulk extraction before 10 correct mappings |
| Splits and baselines | Grouped split, candidate pool, simple scorers | Generate real homology clusters; freeze source/split manifests; train proper hand-feature baseline | No blind-ready claim without clusters |
| Context model | Auditable hand-feature pairwise ranker; ESM/GNN explicitly unconfigured | Pin ESM-2 on college image, cache embeddings, compare with hand features | No neural score before real checkpoint and versioned run |
| Integration and evidence | JSON Schemas and cross-module fixture smoke test | Pin/test backend environment on college image, add schema validator, blind evaluation runner and provenance hashes | No scientific output until schema-valid records and split audit |

Immediate order: source IDs and mapping → independent label audit → cluster
split → candidate pool/baselines → context model → frozen blind evaluation →
optional structure assessment → paper. Preserve example UI labels until real
provenance-bearing outputs exist.

Local fixture verification (requires only Python on `PATH`):

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests -v
```

This checks the skeleton, not cloud installation, ESM-2, GNN, RCSB ingestion,
Rosetta, AlphaFold/ColabFold, or biological efficacy.
