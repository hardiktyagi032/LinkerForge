# LinkerForge: linker sequence-pattern discovery survey and pilot

Status: scoped literature survey and exploratory computational pilot, 12 October 2026. The active primary project remains **sequence-based DFL span detection**. This side study does not assign biochemical function and is not detector training.

## Bottom line

De novo protein motif discovery is established, and linker sequence composition/pattern analysis is established. The general proposal to find recurring linker fragments is **not novel**. A claim about reusable *functional* linker units would require independent biophysical or biochemical evidence; recurring sequences and simulation alone do not establish it. A potentially testable contribution is whether interpretable motif features improve homology-held-out DFL span detection over matched sequence-only baselines. We found no paper in this scoped survey establishing that exact claim, which is **not** proof that no such paper exists.

## Closest work and what it pre-empts

| Work | Direct relevance | Boundary for our claim |
| --- | --- | --- |
| [SynLinker, Liu et al. 2015](https://doi.org/10.1093/bioinformatics/btv447) | Catalog of 2,150 natural and 110 engineered/empirical linker sequences, with retrieval and fusion modelling. | Cataloguing natural linkers is not novel. Full original row-level collection has not been acquired here. |
| [George and Heringa 2002](https://doi.org/10.1093/protein/15.11.871) | Natural linker classification and amino-acid properties. | Linker composition and structural classes are prior work. |
| [DLD source study, 2026](https://www.sciencedirect.com/science/article/pii/S0022283626003670) | Structural domain-linker-domain annotations and sequence clustering. | Do not relabel DLD's structural IDL/DDL as DisProt DFL. |
| [Prolines in linkers, 2026](https://doi.org/10.1371/journal.pcbi.1014588) | Proteome-wide linker proline organization; composition-preserving shuffle controls and links to neighboring-domain properties. | A shuffle-based enrichment analysis or a proline-cluster finding alone is not novel. |
| [STREME, Bailey 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC8479671/) | Established short sequence-motif discovery in unaligned sequences, including protein support. | Must benchmark against a standard motif finder, not label our k-mer count a new algorithm. |
| [DiMotif, Asgari et al. 2019](https://www.nature.com/articles/s41598-019-38746-w) | Variable-length peptide-pair encoding for protein motif discovery. | Unsupervised learned chunks and BPE-style motif mining already exist. |
| [ELM resource, 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC8728146/) | Curated short linear motifs with function/context. | A sequence-pattern match is not a validated functional motif. |
| [DFLpred, 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC4908364/) | Sequence-based DFL detection and explicit distinction from shorter interdomain linkers. | Pattern enrichment must not conflate these label ontologies. |
| [LinkCraft, 2026](https://www.sciencedirect.com/science/article/pii/S0022283626001877) | Ensemble-based flexible-linker design in structural context. | Simulation-informed linker design is not new in general. |

## Data acquisition decision

The SynLinker paper advertises supplementary data, but the publisher challenges automated access and the historical service is unavailable in this environment. **No row-level SynLinker records are in this repository, and this pilot does not use SynLinker.** Do not manufacture 2,260 records from the paper's aggregate count. Before using any recovered archive, retain original bytes, URL, checksum, terms, row IDs, natural/artificial category, full source protein/PDB identifiers, and linker coordinates when present. If only isolated linker sequences are present, they support sequence-pattern discovery but not full-protein start/end detector supervision. Audit overlap against protected evaluation sets and existing PDB/DLD/DisProt sources before training.

## Implemented exploratory baseline

`scripts/discover_linker_sequence_patterns.py` uses 2026_06 DisProt *curated flexible-linker positive spans* already staged in the workspace, excluding all 52 candidates in strong local-similarity components connected directly or transitively to protected evaluation sets. It finds exact 3–5-residue patterns in distinct proteins, then compares their protein-level occurrence with 2,000 within-span, composition-preserving shuffles. The output is `reports/linker_motif_pilot_2026-10-12.json`, validated by `schemas/linker_motif_pilot_v0.1.0.schema.json`. Config, source, audit and code provenance are recorded. This is descriptive, not a model for cleavage, rigidity, bend angle, linker detection, or biological function.

The strong-hit screen is not full homology clearance. The permutation/BH values are **exploratory** because patterns were selected on observed support before multiple-testing adjustment; they must not be reported as confirmatory discoveries. Low-complexity, shared ancestry, and annotation bias remain alternative explanations. A next proper experiment would freeze family-disjoint data, compare STREME/DiMotif with k-mer controls, and evaluate motif features only as an ablation in the existing detector on a held-out, matched DFL task. Functional labels require a separate evidence source or calibrated ensemble/experimental study.

## Minimal commands

```powershell
.venv-gpu\Scripts\python.exe -m unittest discover -s tests -p test_linker_sequence_patterns.py -v
.venv-gpu\Scripts\python.exe scripts\discover_linker_sequence_patterns.py
```

No GPU training is launched by this pilot. It does not alter the continuous detector autoresearch budget or claim improved detector performance.
