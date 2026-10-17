# LinkerForge sequence-discovery index: 100k milestone

Date: 2026-10-12. This is a **discovery index**, not a validated training set or a
claim that 113,285 linker functions have been measured.

**Superseding data-use decision:** do not use this broad index as an annotated
linker database. The separately exported annotated-only catalog is documented
in `reports/ANNOTATED_ONLY_LINKER_CATALOG_2026-10-12.md`; it excludes all
88,522 inferred-only domain gaps. Retain this broad index solely for candidate
discovery and negative/unknown-label audits.

## Frozen output

- Exact-unique amino-acid sequences: **113,285** (the 50k and 100k discovery
  thresholds are met).
- Readable table: `data/processed/linker_catalog/expanded_wheat_v2/unique_discovery_sequences.v1.tsv`
  (113,285 data rows; SHA-256
  `44540476c43a4bc47628ea13122d3f10ab5f512bae64acf7182bfd66ac8e1980`).
- Full source metadata: `data/processed/linker_catalog/expanded_wheat_v2/unique_discovery_sequences.v1.jsonl.gz`
  (113,285 JSONL records; SHA-256
  `03f5afd1a5e5d777269190e111b269e7f54fce016fcbd10e8d170ab5e46797d5`).
- Last-stage manifest: `data/processed/linker_catalog/expanded_wheat_v2/manifest.v1.json`.
  Each earlier-stage directory also contains the source URL, raw response hash,
  code hash, prior-index hash, candidate observations, and count.
- Raw source downloads were temporary TSV files and were removed after parsing.

## Evidence tiers and counts

| Source or tier | Distinct sequences bearing that source | Interpretation |
|---|---:|---|
| Existing LinkerForge catalog (DLD, DisProt, protected CAID3) | 2,621 | Mixed annotations; 455 protected benchmark sequences and 404 further quarantined sequences must not be used for model training. |
| Published NRPS inter-modular CSV | 8,133 | Parsed natural NRPS-module linker sequences; many are putative genomic modules, not individually function-tested. |
| UniProt `Region` feature whose note contains `linker` | 14,011 | Explicit linker-region annotations; 57 observations (56 distinct sequences) have a PubMed-linked ECO evidence string. This is not automatically proof of a measured linker function. |
| UniProt reviewed, inferred gaps between annotated domains | 32,949 | Lower-confidence linker candidates, not explicit linker annotations. |
| Additional organism-specific unreviewed domain-gap sources | See stage manifests | Still lower confidence; exact duplicate strings may occur in several sources. |

The **union** with an existing, NRPS, or explicit-UniProt-region source is
24,763 sequences; 88,522 sequences have only inferred domain-gap support.
These groups are disjoint and sum to 113,285. The per-source row counts above
overlap and therefore must not be summed.

## Extraction and quality controls

The domain-gap extractor takes a standard-amino-acid segment of 5–150 residues
between adjacent annotated UniProt `DOMAIN` intervals, discards gaps overlapping
annotated `REPEAT` or `TRANSMEM` intervals, and rejects apparently adjacent
domains if a third domain covers their gap. The explicit-region extractor takes
the supplied UniProt interval only when that `REGION` note contains `linker`,
retaining its ECO evidence text. The NRPS file is pinned to source commit
`199d3284f76a2a8aa2fc0c5205b9240571ea8115`. Exact sequences are
deduplicated, but **homologous** sequences are not collapsed and the index is
not an independent evaluation set.

The complete table was checked against the manifest: 113,285 rows, 113,285
distinct sequence strings, sorted in the same order as JSONL. Parsing tests
passed for adjacent domains, nested-domain exclusion, repeat exclusion,
explicit-region note scoping, and out-of-bounds intervals. The TSV marks
protected and quarantined existing-catalog records; its status column marks
**every** row `discovery_only_not_training_labels`.

## Required next gate before detector training or a paper claim

Audit a stratified sample of each source tier for true interdomain linker
boundaries and false positives; retain unknown/negative semantics separately.
Cluster by homology before splitting, exclude all protected CAID3 members and
homologs from training, and select a held-out benchmark with matched baselines.
No reported count here is a model result or evidence of improved detection.

## Source references

- UniProt REST API: https://rest.uniprot.org/uniprotkb/search
- UniProt knowledgebase paper: https://academic.oup.com/nar/article/53/W1/W547/8126256
- Farag et al. NRPS linker dataset and method: https://doi.org/10.1093/bioinformatics/btz127 ; https://github.com/SWFarag/nrps-linker
- SynLinker (comparison of linker-source conventions): https://doi.org/10.1093/bioinformatics/btv447
