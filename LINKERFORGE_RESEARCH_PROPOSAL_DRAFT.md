# LinkerForge Research Proposal — Draft

## Explainable, structure-conditioned ranking of peptide linkers for computational fusion-protein design

**Project duration:** 12 weeks  
**Team size:** Four researchers  
**Project type:** Computational research only  
**Demonstration system:** sfGFP–linker–mCherry  
**Document status:** Draft for supervisor and team review  

The sfGFP–mCherry pair is **only a final worked example** used to demonstrate the completed workflow. It is not the core research target, the training target, or a restriction of the proposed system. The core project is a general, structure-conditioned method for ranking linker candidates for two supplied fusion partners and their selected attachment points, trained and evaluated using diverse natural same-chain two-domain proteins.

## 1. Abstract

Fusion proteins combine independently folding protein domains in one polypeptide chain. Their connecting peptide linker can influence folding, steric separation, domain orientation, stability, expression, and retention of domain function. Linkers are nevertheless often selected from a small set of familiar sequences, such as glycine/serine-rich repeats, followed by empirical testing. Existing linker databases and design tools provide useful sequences, and modern structure predictors can evaluate a completed fusion sequence, but neither alone provides an explainable, leakage-resistant method for ranking linkers from the sequence and three-dimensional context of a particular pair of attachment sites.

This project proposes **LinkerForge**, a computational system that ranks constrained peptide-linker candidates for two supplied fusion partners and specified attachment points. A fusion partner may be a single domain, a complete single-domain protein, or a larger soluble protein for which a valid attachment site is defined. The system will learn compatibility patterns from natural same-chain multidomain proteins represented as `Domain A — natural linker — Domain B`. Each example will combine frozen protein-language-model embeddings, attachment-point geometry, linker sequence features, and evidence-quality metadata. The primary learning task will be pairwise or contrastive ranking of an observed natural linker above corrupted or transplanted alternatives; the output will not be interpreted as an experimentally calibrated probability of success. Homology- and domain-family-aware partitions will be frozen before model development, and held-out natural linkers will be masked for blind reconstruction. The proposed model will be compared with direct fusion, a fixed `(GGGGS)3` linker, random length-matched GS-rich linkers, geometry-only selection, nearest-neighbour retrieval, and a feature-based non-neural ranker.

After the general method has been trained, frozen, and evaluated, a final computational example will connect the C-terminus of superfolder GFP to the N-terminus of mCherry using flexible, non-cleavable, primarily GS-rich linkers of 5–30 residues. This pair is used to demonstrate the complete workflow, not to define or train the core model. Shortlisted complete fusion sequences will pass through Rosetta-based construction and closure checks, ColabFold/AlphaFold structure prediction, predefined hard structural rejection rules, and OpenMM minimisation. Results will be displayed with full provenance in the LinkerForge web interface. The project will report the highest-ranked computational candidate and alternatives, not experimental proof of expression, fluorescence, stability, or biological function.

## 2. Background and rationale

Fusion proteins are used in imaging, therapeutics, biosensing, purification, synthetic biology, and molecular engineering. A peptide linker does more than join two sequences: its length, flexibility, composition, charge, and structure can alter the relative motion and steric accessibility of the connected domains [1]. Flexible GS-rich linkers are common because glycine supports conformational freedom and serine improves solubility, but a standard linker is not necessarily suitable for every domain pair or attachment geometry [1,2]. Natural multidomain proteins provide experimentally observed examples of domains connected by evolutionarily retained intervening sequences, and their linker properties have long been proposed as a basis for rational design [1].

Previous resources such as LinkerDB and SynLinker retrieve or recommend linker sequences from natural and engineered proteins [2,3]. These systems establish the value of reusable linker knowledge but do not resolve the complete problem addressed here: selecting among candidates using the local three-dimensional geometry and sequence context of both proposed fusion ports, while preserving evidence provenance and evaluating leakage-resistant generalisation to unseen protein families.

Modern protein representations and structure predictors make a more integrated approach practical. Protein language models learn information about sequence, structure, and evolution from large protein corpora [4]. Rotation-aware geometric neural networks can represent local three-dimensional environments without depending on a structure's arbitrary global coordinate frame [5]. AlphaFold and ColabFold enable high-quality prediction and confidence estimation for complete protein sequences [6,7]. These methods can be combined into a staged design-and-evaluation pipeline, but structure prediction must not be confused with experimental validation, and confidence values must be interpreted separately for domains, linkers, and interdomain arrangement.

## 3. Research problem

The project addresses the following problem:

> Given two soluble fusion partners supplied as experimental structures or as sequences with separately labelled predicted structures, specified attachment points, and a constrained linker design space, can an explainable multimodal model rank peptide linkers that are more compatible with the partner sequences and attachment geometry than standard, random, geometry-only, or retrieval-based alternatives?

The project does **not** attempt unrestricted protein generation, prediction of laboratory success, or replacement of experimental validation.

## 4. Research gap

The defensible research gap is a synthesis of limitations reported across the literature:

1. Linker choice remains dependent on context and is frequently empirical [1].
2. Earlier linker tools primarily retrieve or assemble sequences according to user-specified properties and databases rather than learn a generalisable structural compatibility function [2,3].
3. Protein language models encode rich sequence information but do not, by themselves, choose a linker for two explicit attachment environments [4].
4. Geometric learning methods can represent protein structure, but their application to explainable interdomain-linker compatibility ranking remains underexplored [5].
5. AlphaFold/ColabFold predicts a complete supplied sequence; it does not define the design objective, generate a defensible comparison set, prevent data leakage, or establish experimental function [6,7].
6. Natural linker data are complicated by inconsistent domain boundaries, residue numbering, missing coordinates, engineered constructs, repeated PDB entries, and homologous leakage. A provenance-first dataset and blind family-level evaluation are therefore required.

The proposed novelty is not the isolated invention of protein embeddings, geometric GNNs, linker retrieval, or structure prediction. It is the construction and evaluation of a reproducible, structure-conditioned ranking framework that integrates these components under one explicit evidence and validation contract.

## 5. Aim, objectives, and hypotheses

### 5.1 Aim

To develop and evaluate an explainable computational model that ranks flexible peptide linkers for two specified fusion partners using natural multidomain proteins as compatibility evidence.

### 5.2 Objectives

1. Construct a versioned natural-linker dataset from experimentally resolved, same-chain multidomain proteins.
2. Define an operational and reproducible rule for identifying domains, linkers, attachment points, and evidence quality.
3. Create homology- and domain-family-aware training, validation, and blind-test partitions.
4. Implement deterministic, retrieval, geometry-only, and feature-based baselines.
5. Train a multimodal compatibility ranker using frozen domain embeddings, attachment-point geometry, and linker sequence representations.
6. Evaluate blind masked-linker reconstruction without tuning on blind examples.
7. Apply the frozen workflow to an sfGFP–mCherry demonstration and compare it with all baselines.
8. Publish schema-valid records, configurations, model versions, failure reasons, metrics, and limitations through a provenance-aware interface.

### 5.3 Hypotheses

**H1:** A structure-conditioned multimodal ranker will place the held-out natural linker higher than geometry-only, nearest-neighbour, and feature-based baselines on unseen domain-family groups.

**H2:** Among unseen domain pairs, the proportion for which at least one top-five candidate passes every predefined structural requirement will be higher for LinkerForge than for fixed or random GS-rich linker selection.

**H3:** Combining sequence context with attachment-point geometry will outperform either information source alone.

These hypotheses concern computational ranking and structural plausibility only.

## 6. Methodology

### 6.1 Study design

The study will use a retrospective computational benchmark followed by one prospective computational demonstration. Natural same-chain multidomain proteins will supply observed compatibility examples. Synthetic alternatives will be generated only as explicitly labelled ranking negatives and will never be described as experimentally failed proteins.

### 6.2 Data sources

Data will be obtained through official bulk downloads or APIs rather than HTML scraping:

- **Protein Data Bank (PDB/RCSB or PDBe):** experimental coordinates, polymer chains, experimental method, resolution, residue observation, and structure metadata [8].
- **SIFTS:** residue-level mapping between PDB coordinates, UniProt sequences, CATH, Pfam, and InterPro [9].
- **UniProtKB:** canonical sequences, taxonomy, protein identity, and curated annotations [10].
- **CATH:** structural-domain boundaries, domain superfamilies, and nonredundant domain sets; the release will be pinned in the manifest [11].
- **InterPro:** integrated sequence-domain and functional-site annotations [12].
- **AlphaFold Protein Structure Database:** supplementary predicted structures only; these will never be mixed with the experimental gold tier [13].

### 6.3 Operational definition of a natural linker

For two adjacent, non-overlapping domains in one continuous polypeptide chain:

```text
Domain A = residues A_start ... A_end
Domain B = residues B_start ... B_end
A_end < B_start
Linker = residues A_end + 1 ... B_start - 1
```

A record will be admitted to the first dataset only when:

1. both domains occur in the same covalently continuous protein chain;
2. PDB and UniProt residue numbering can be reconciled through SIFTS;
3. the domains are adjacent and non-overlapping;
4. no third assigned domain lies between them;
5. each domain contains at least 40 residues;
6. the intervening sequence contains 1–60 residues in the raw collection;
7. attachment-region coordinates and boundary evidence meet the configured quality rule; and
8. the chain is not an obvious artificial fusion, affinity tag, cleavage product, or chimeric mapping to multiple unrelated UniProt proteins.

The design task will later restrict candidates to 5–30 residues. Discontinuous or interleaved domains, membrane-spanning connections, ambiguous boundaries, and unresolved chain identity will be excluded from the MVP rather than resolved by unrecorded judgement.

### 6.4 Evidence tiers

Records will be assigned to distinct tiers:

- **Gold:** experimental structure, confident domain boundaries, observed attachment regions, reliable SIFTS mapping, and no disqualifying engineering.
- **Silver:** experimental structure with partial linker coordinates or lower-confidence boundary agreement; usable only for the tasks supported by its evidence.
- **Predicted supplementary:** sequence-domain evidence plus a predicted structure with adequate local confidence; never used as experimental ground truth.
- **Rejected:** a retained audit record explaining which rule failed.

Unresolved flexible linkers will not automatically be discarded. If the sequence is known but coordinates are absent, the record may be used for sequence analysis while `geometry_usable` is set to false. This prevents systematic bias toward rigid, crystallographically ordered linkers.

### 6.5 Dataset records and provenance

Every derived example will use a formal JSON Schema and contain:

- PDB ID, chain/entity ID, UniProt accession, taxonomy, and retrieval date;
- source-database releases and source-file checksums;
- domain and linker residue ranges in both source and canonical numbering;
- sequences for Domain A, linker, Domain B, and the full chain;
- domain-family identifiers and annotation sources;
- observed/unobserved residue masks and structure-quality fields;
- derived sequence, secondary-structure, exposure, contact, and geometry features;
- evidence tier, exclusion warnings, and manual-review status;
- pipeline Git commit, configuration hash, dependency versions, and transformation log.

Raw records will be immutable. Corrections will produce a new dataset version.

### 6.6 Deduplication and leakage-resistant splitting

Repeated PDB entries and chains mapping to the same UniProt protein will first be grouped. Sequences will then be clustered using MMseqs2 [14]. Entire groups—not individual rows—will be assigned to train, validation, or blind partitions using:

- full-sequence similarity;
- CATH superfamily identity for both domains;
- ordered domain-family pair;
- linker-sequence similarity; and
- shared UniProt identity.

An approximate 70/15/15 division will be targeted, but cluster integrity will take priority over exact percentages. The split manifest will be frozen before final model selection. No threshold, feature, or architecture will be tuned after blind references are revealed.

### 6.7 Candidate and negative construction

For each natural positive, synthetic alternatives will be generated by controlled transformations:

- length-matched residue shuffling;
- shortening or lengthening;
- reversal;
- transplantation from another domain-family pair;
- GS-rich controls of matched length;
- addition of prohibited hydrophobic stretches or configured cleavage motifs; and
- structure-derived closure or clash failures where reliably computable.

Each alternative will retain its generation rule and seed. Synthetic negatives mean “less compatible under the training construction,” not “experimentally non-functional.”

### 6.8 Input representation

Each candidate will be encoded as three coordinated views.

#### Domain sequence representation

Frozen ESM-2 residue embeddings will represent Domains A and B [4]. Frozen embeddings reduce the data and compute needed for the 12-week project and prevent accidental fine-tuning on the blind set.

#### Attachment-point geometric graph

A local graph will contain residues around the C-terminal port of Domain A and N-terminal port of Domain B. Nodes will encode amino-acid identity, frozen sequence embedding, secondary structure, solvent accessibility, observation/confidence state, backbone orientation, and domain role. Edges will represent covalent neighbours and spatial neighbours inside a frozen distance cutoff, with distance, direction, sequence separation, and edge type. A rotation-aware geometric GNN, initially a GVP-style network, will encode the graph [5].

#### Linker representation

A small Transformer, bidirectional recurrent network, or one-dimensional CNN will encode linker sequence and length. Deterministic descriptors will include composition, net charge proxy, hydropathy, predicted flexibility, low-complexity fraction, and motif flags.

### 6.9 Model and learning objective

The domain, geometric, and linker representations will be fused into a small multilayer network with heads for:

- compatibility rank;
- suitable linker class/length;
- clash risk;
- domain-deformation risk;
- protected-site obstruction risk; and
- confidence or abstention.

The primary objective will be pairwise ranking:

```text
score(observed natural linker | domain pair, ports)
>
score(corrupted or transplanted linker | same context)
```

Pairwise logistic loss or a margin-ranking loss will be compared on validation data. Training batches will group candidates belonging to the same domain pair so the task cannot be solved solely from protein identity.

### 6.10 Required baselines and ablations

All methods will use the same candidate sets, scoring records, and hard-rejection rules.

1. Direct fusion without a linker.
2. Fixed `(GGGGS)3` linker.
3. Random length-matched GS-rich linker.
4. Linker length selected only from terminal distance/geometry.
5. Nearest-neighbour natural-linker retrieval.
6. Feature-based XGBoost or equivalent non-neural ranker.
7. Sequence-only neural model.
8. Geometry-only neural model.
9. Full LinkerForge model.

The sequence-only and geometry-only ablations test H3.

### 6.11 Blind masked-linker evaluation

For every blind example, the natural linker sequence will be hidden. The frozen methods will receive only the permitted domain sequences, structures, attachment points, and design constraints. Top-1, top-5, and top-10 predictions will be saved before the natural reference is revealed.

Primary endpoint:

> Percentage of unseen domain pairs for which at least one top-five LinkerForge candidate passes every frozen hard structural requirement.

Secondary endpoints will include:

- natural-linker rank, mean reciprocal rank, and pairwise ranking accuracy;
- linker-class accuracy;
- length mean/median absolute error and percentage within ±2 and ±5 residues;
- sequence identity and edit distance, treated as secondary because multiple linkers may be valid;
- physicochemical-property similarity;
- chain-closure rate and severe-clash count;
- preservation of Domain A and Domain B structures;
- protected-site clearance;
- domain-specific pLDDT and interdomain PAE; and
- runtime, abstention rate, and pipeline failure rate.

Bootstrap confidence intervals will be calculated over held-out domain-pair groups. Paired comparisons will be made on the same blind examples. Raw numerator and denominator counts will accompany percentages.

### 6.12 sfGFP–mCherry computational demonstration

Only after general blind evaluation is complete, the frozen model will be applied to the following predetermined example. This case demonstrates transfer of the workflow to an engineered fusion and is not the core learning problem:

- Fusion partner A: superfolder GFP, with its C-terminus as the initial port.
- Fusion partner B: mCherry, with its N-terminus as the initial port.
- Linker: flexible, non-cleavable, primarily GS-rich, 5–30 residues.
- Permitted auxiliary residues: A, T, N, Q, E, and K.
- Fixed comparison: `GGGGSGGGGSGGGGS`, equivalent to `(GGGGS)3`.

Candidate generation will use constrained enumeration, mutation, and retrieval; learned diffusion or unrestricted generation is outside the MVP. The model will rank candidates and retain approximately 10–20 for structural evaluation.

### 6.13 Structural evaluation funnel

1. **Rosetta/PyRosetta:** construct connection geometry, sample linker conformations, verify chain closure, and remove severe clashes. Kinematic closure is an established approach for loop/linker reconstruction [15].
2. **ColabFold/AlphaFold 2:** predict each complete fused sequence and retain PDB/mmCIF, pLDDT, PAE, pTM, settings, seed, and software version [6,7].
3. **Hard rejection:** reject chain-closure failure, severe residual clashes, substantial domain deformation, protected-site obstruction, invalid output, deterministic sequence-rule violations, or excessive uncertainty under frozen thresholds.
4. **OpenMM:** minimise passing finalists and perform short, explicitly limited simulations where resources permit [16]. Optional GROMACS simulations may be used only for one to three finalists.
5. **Mol*/PyMOL:** use Mol* for browser inspection and PyMOL for measurements and figures. Neither is treated as a simulation engine.

Low linker pLDDT will not be used as an automatic failure condition because flexible linkers may legitimately have low local confidence. Domain confidence, interdomain PAE, geometry, clashes, and domain preservation will be evaluated separately.

### 6.14 Reproducibility and software engineering

Long-running jobs will execute on the college cloud, not GitHub Pages or routine CI. Each run will receive an immutable configuration, input-manifest hash, Git commit, random seeds, environment identifier, requested resources, and output directory. Each stage will write machine-readable status, versions, checksums, warnings, and failure reasons.

The frontend will display only schema-valid results or values explicitly labelled as demonstrations. The system will distinguish natural observations, synthetic negatives, model predictions, structure-prediction outputs, and any future experimental measurements.

## 7. Twelve-week work plan

| Week | Main activity | Exit evidence |
|---|---|---|
| 1 | Freeze schemas, environment, sources, inclusion rules, and development proteins | Reproducible setup and reviewed data contract |
| 2 | Implement PDB/SIFTS/UniProt/CATH extraction for a small verified set | Schema-valid natural-linker records |
| 3 | Reconstruct at least one known linker with Rosetta and inspect it | Closure and reconstruction report |
| 4 | Scale collection, evidence grading, deduplication, and manual spot checks | Dataset manifest and quality report |
| 5 | Calculate sequence, structural, and attachment-geometry features | Reproducible feature records |
| 6 | Freeze grouped splits; generate labelled negatives; implement baselines | Leakage audit and baseline report |
| 7 | Implement frozen ESM-2, geometric encoder, and linker encoder | Training smoke test and unit tests |
| 8 | Train, select using validation only, freeze thresholds and checkpoint | Frozen model package and validation report |
| 9 | Run masked-linker blind evaluation once | Immutable blind predictions and metrics |
| 10 | Run Rosetta and ColabFold structural scorecards on blind shortlists | Structural comparison and rejection report |
| 11 | Run sfGFP–mCherry comparison and minimise finalists | Final computational demonstration |
| 12 | Reproduce from a clean environment; finish interface, paper figures, and proposal/report | Reproduction log and evidence package |

## 8. Team workstreams

1. **Data and provenance:** ingestion, residue mapping, linker extraction, evidence grading, deduplication, and split manifests.
2. **Baselines and machine learning:** feature baselines, embeddings, model training, ablations, and statistical evaluation.
3. **Structure and scoring:** Rosetta construction, ColabFold runs, structural metrics, hard rejection, and OpenMM.
4. **Interface and reproducibility:** JSON Schemas, run registry, provenance display, Mol* visualisation, CI, documentation, and final evidence packaging.

Outputs will be defined through versioned contracts so one workstream can be reviewed or replaced without silently changing another.

## 9. Expected outcomes

The project is expected to deliver:

- a provenance-bearing natural-linker dataset and extraction pipeline;
- frozen, homology-aware train/validation/blind manifests;
- deterministic and machine-learning baselines;
- a trained compatibility-ranking prototype;
- blind masked-linker evaluation with raw counts and uncertainty;
- ranked sfGFP–mCherry candidates and structural scorecards;
- a browser interface for structures, comparisons, warnings, and provenance; and
- a reproducible computational evidence package suitable for a research manuscript draft.

The strongest permitted conclusion is:

> LinkerForge identified the highest-ranked computational linker candidate under the predefined data, ranking, and structural-screening criteria.

## 10. Risks and limitations

- A natural linker is evidence of occurrence, not proof of optimality for an engineered fusion.
- Synthetic negatives may be biologically viable and therefore cannot be described as experimental failures.
- Missing linker coordinates can bias structural datasets toward rigid examples.
- Domain boundaries differ across annotation systems and require recorded reconciliation.
- PDB redundancy and homologous proteins can cause severe leakage without grouped splitting.
- AlphaFold/ColabFold confidence does not prove expression, solubility, fluorescence, stability, or function.
- Interdomain orientation may be flexible or underdetermined even when both domains are predicted accurately.
- The sfGFP–mCherry example is one demonstration and cannot establish universal generalisation.
- The 12-week schedule permits a rigorous prototype, not a production platform or new folding foundation model.

## 11. Ethical, licensing, and safety considerations

The work uses public protein sequences, annotations, and structures and does not involve human participants, patient data, animals, or wet-lab experiments. Database and model licences will be recorded by version. AlphaFold 2 code and parameters, ColabFold, ESM, Rosetta/PyRosetta, and other dependencies have distinct terms that must be checked before redistribution or commercial use. No credentials, restricted model weights, or large licensed databases will be committed to Git. Computational predictions will be labelled as theoretical and will not be presented as clinical, environmental, or biological proof.

## 12. Core references

1. Chen, X., Zaro, J. L., & Shen, W.-C. (2013). Fusion protein linkers: Property, design and functionality. *Advanced Drug Delivery Reviews, 65*(10), 1357–1369. [https://doi.org/10.1016/j.addr.2012.09.039](https://doi.org/10.1016/j.addr.2012.09.039)
2. George, R. A., & Heringa, J. (2002). An analysis of protein domain linkers: Their classification and role in protein folding. *Protein Engineering, 15*(11), 871–879. [https://doi.org/10.1093/protein/15.11.871](https://doi.org/10.1093/protein/15.11.871)
3. Liu, C., Chin, J. X., & Lee, D.-Y. (2015). SynLinker: An integrated system for designing linkers and synthetic fusion proteins. *Bioinformatics, 31*(22), 3700–3702. [https://doi.org/10.1093/bioinformatics/btv447](https://doi.org/10.1093/bioinformatics/btv447)
4. Lin, Z., Akin, H., Rao, R., et al. (2023). Evolutionary-scale prediction of atomic-level protein structure with a language model. *Science, 379*(6637), 1123–1130. [https://doi.org/10.1126/science.ade2574](https://doi.org/10.1126/science.ade2574)
5. Jing, B., Eismann, S., Suriana, P., Townshend, R. J. L., & Dror, R. O. (2021). Learning from protein structure with geometric vector perceptrons. *International Conference on Learning Representations*. [https://openreview.net/forum?id=1YLJDvSx6J4](https://openreview.net/forum?id=1YLJDvSx6J4)
6. Jumper, J., Evans, R., Pritzel, A., et al. (2021). Highly accurate protein structure prediction with AlphaFold. *Nature, 596*, 583–589. [https://doi.org/10.1038/s41586-021-03819-2](https://doi.org/10.1038/s41586-021-03819-2)
7. Mirdita, M., Schütze, K., Moriwaki, Y., et al. (2022). ColabFold: Making protein folding accessible to all. *Nature Methods, 19*, 679–682. [https://doi.org/10.1038/s41592-022-01488-1](https://doi.org/10.1038/s41592-022-01488-1)
8. Burley, S. K., Bhikadiya, C., Bi, C., et al. (2022). RCSB Protein Data Bank: Celebrating 50 years of the PDB with new tools for understanding and visualizing biological macromolecules in 3D. *Protein Science, 31*(1), 187–208. [https://doi.org/10.1002/pro.4213](https://doi.org/10.1002/pro.4213)
9. Dana, J. M., Gutmanas, A., Tyagi, N., et al. (2019). SIFTS: Updated Structure Integration with Function, Taxonomy and Sequences resource allows 40-fold increase in coverage of structure-based annotations for proteins. *Nucleic Acids Research, 47*(D1), D482–D489. [https://doi.org/10.1093/nar/gky1114](https://doi.org/10.1093/nar/gky1114)
10. The UniProt Consortium. (2025). UniProt: The Universal Protein Knowledgebase in 2025. *Nucleic Acids Research, 53*(D1), D609–D617. [https://doi.org/10.1093/nar/gkae1010](https://doi.org/10.1093/nar/gkae1010)
11. Waman, V. P., Bordin, N., Lau, A., et al. (2025). CATH v4.4: Major expansion of CATH by experimental and predicted structural data. *Nucleic Acids Research, 53*(D1), D348–D355. [https://doi.org/10.1093/nar/gkae1087](https://doi.org/10.1093/nar/gkae1087)
12. Blum, M., Andreeva, A., Florentino, L. C., et al. (2025). InterPro: The protein sequence classification resource in 2025. *Nucleic Acids Research, 53*(D1), D444–D456. [https://doi.org/10.1093/nar/gkae1082](https://doi.org/10.1093/nar/gkae1082)
13. Varadi, M., Anyango, S., Deshpande, M., et al. (2022). AlphaFold Protein Structure Database: Massively expanding the structural coverage of protein-sequence space with high-accuracy models. *Nucleic Acids Research, 50*(D1), D439–D444. [https://doi.org/10.1093/nar/gkab1061](https://doi.org/10.1093/nar/gkab1061)
14. Steinegger, M., & Söding, J. (2017). MMseqs2 enables sensitive protein sequence searching for the analysis of massive data sets. *Nature Biotechnology, 35*, 1026–1028. [https://doi.org/10.1038/nbt.3988](https://doi.org/10.1038/nbt.3988)
15. Stein, A., & Kortemme, T. (2013). Improvements to robotics-inspired conformational sampling in Rosetta. *PLoS ONE, 8*(5), e63090. [https://doi.org/10.1371/journal.pone.0063090](https://doi.org/10.1371/journal.pone.0063090)
16. Eastman, P., Galvelis, R., Peláez, R. P., et al. (2024). OpenMM 8: Molecular dynamics simulation with machine learning potentials. *The Journal of Physical Chemistry B, 128*(1), 109–116. [https://doi.org/10.1021/acs.jpcb.3c06662](https://doi.org/10.1021/acs.jpcb.3c06662)

## 13. Citation requirements for resulting reports

At minimum, any proposal, manuscript, poster, or final report derived from this project should cite:

- Chen et al. for fusion-linker rationale and properties [1];
- George and Heringa and/or SynLinker for natural-linker analysis and prior design resources [2,3];
- the exact database publications/releases used for PDB, SIFTS, UniProt, CATH, InterPro, and AlphaFold DB [8–13];
- Lin et al. when using ESM-2/ESMFold representations [4];
- Jing et al. when using a GVP-style geometric encoder [5];
- Jumper et al. and Mirdita et al. for AlphaFold 2 and ColabFold [6,7];
- Steinegger and Söding for MMseqs2 clustering/search [14];
- Stein and Kortemme for Rosetta next-generation KIC if used [15]; and
- Eastman et al. for OpenMM [16].

Software versions, database releases, access dates, model weights, configuration files, and licence terms must additionally be recorded in the reproducibility supplement. References should be updated to the exact releases actually used before submission.
