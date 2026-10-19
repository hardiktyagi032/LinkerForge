# Additional annotated protein-linker sources — retrieval audit

Date: 12 October 2026. Scope: downloadable **amino-acid** linker annotations, not small-molecule linkers or inferred domain gaps. This is a source survey, not a permission to merge labels or train.

| Source | Direct file / page | Verified annotation | Status and caveat |
|---|---|---|---|
| DisoFLAG | https://github.com/YihePang/DisoFLAG/tree/main/dataset and https://bliulab.net/DisoFLAG/download | Nine-line records; line 9 is a per-residue DFL 0/1 track. GitHub has train, development, DP93, DP94, CAID2 files. | **New obtainable source**, but overwhelmingly overlaps DisProt; audit before ingestion. |
| APOD / TransDFL | https://yanglab.nankai.edu.cn/APOD/benchmark/ and http://bliulab.net/TransDFL/benchmark/ | TR166, TE82, TE64 per-residue DFL benchmarks. | Already present in project; preserve original partitions, do not count as independent new labels. |
| DFLpred | https://pmc.ncbi.nlm.nih.gov/articles/PMC4908364/ | Paper describes 144-train/60-test DFL-labeled proteins and links to old server. | Historical source; current row-level access not verified. Likely earlier DisProt subset. |
| CAID reference | https://github.com/BioComputingUP/caid-reference | DFL reference tracks. | Benchmark-only, protected. CAID3 already cataloged; CAID2 can be acquired as an additional protected comparator, not training. |
| MobiDB | https://mobidb.org/ | Curated DisProt imports plus homology/embedding-propagated function tracks. | Do **not** treat propagated tracks as independent experimental linker labels; separate evidence tier if explored. |
| DLD | https://pcrgwd.ucd.ie/linker/download/ | Structural IDL and DDL residue labels. | Already cataloged; different ontology from DisProt/CAID DFL. |
| SynLinker | https://doi.org/10.1093/bioinformatics/btv447 | Published natural/artificial linker collection. | Row-level file still not obtained; published count cannot be ingested. |
| LinkerDB | https://www.vubioinformatics.com/tools/ | Historical inter-domain linker resource. | Downloadable row-level archive and current accessibility not verified. |

## DisoFLAG file inspection (read-only, no ingestion)

GitHub raw files parsed as nine-line blocks with sequence length equal to DFL-label length. `train_data.txt`: 589 proteins, 138 DFL-positive proteins, 163 positive spans (162 unique sequences), 5,249 positive residues. `dev_data.txt`: 148 proteins, 39 positive proteins, 42 positive spans, 1,212 positive residues. Against the local DisProt 2026_06 region file, **137/589 train** and **39/148 development** protein IDs recur. Against the existing exact linker-sequence catalog, **145/162 unique train spans** and **41/42 development spans** recur. This leaves at most 17 train and one development exact *strings* not already indexed; this is not a claim of 18 independent biological labels. DP93 and DP94 are published test sets and must remain protected.

The fact that many DisoFLAG proteins have no positive DFL span does not make their entire sequence verified negative. Its `0` semantics and relationship to DisProt unknown positions need source-level review. Licensing of dataset files should also be checked before redistribution. No data from DisoFLAG was appended to the catalog in this survey.

## Recommendation

Add a versioned DisoFLAG adapter only after mapping source IDs, exact protein/region coordinates, label semantics, and all overlap with current train/development/blind and CAID sources. Keep source-specific observations; do not simply union its labels into a single training target. Treat MobiDB and published predictor datasets as possible retrieval channels or comparators, not independent label counts without lineage proof.
