# LinkerForge prior-art audit (8 October 2026)

## What has and has not been done

This is a **screening pool**, not a claim to have read 2,437 papers. The records in
`openalex_screening_pool.csv` and `.json` were retrieved from OpenAlex using the
14 searches in `build_pool.ps1`, deduplicated by OpenAlex work ID, and retain
the query that matched each record. `search_log.json` gives per-query counts.
The export contains 2,437 unique metadata records, 2,403 with DOIs. Only 130
titles contain "linker"; many broader hits may be irrelevant. Every record is
marked `retrieved_not_screened`. OpenAlex's article type and search ranking are
not substitutes for peer-review or full-text inspection.

## Closest prior work requiring full-text comparison

| Theme | Paper | DOI | Immediate implication |
|---|---|---|---|
| Linker generation | Crasto & Feng, *LINKER: a program to generate linker sequences for fusion proteins* (2000) | 10.1093/protein/13.5.309 | Generating fusion-linker sequences is longstanding. |
| Natural linker characterization | George & Heringa, *An analysis of protein domain linkers* (2002) | 10.1093/protein/15.11.871 | Natural linker classes and folding roles have been studied. |
| HMM identification | *Prediction of protein interdomain linker regions by a hidden Markov model* (2005) | 10.1093/bioinformatics/bti363 | Linker identification is not new. |
| Neural identification | *Identification of putative domain linkers by a neural network* (2006) | 10.1186/1471-2105-7-323 | Neural linker classification predates LinkerForge. |
| SVM/RF identification | *DROP: an SVM domain linker predictor trained with optimal features selected by random forest* (2011) | 10.1093/bioinformatics/btq700 | A hybrid classifier alone is not novel. |
| RF identification | *Protein inter-domain linker prediction using Random Forest and amino acid physiochemical properties* (2014) | 10.1186/1471-2105-15-s16-s8 | Same conclusion. |
| Flexible-linker identification | *DFLpred* (2016) | 10.1093/bioinformatics/btw280 | Disordered flexible linkers are a specialized classification target. |
| Transfer-learning identification | *TransDFL* (2022/2023) | 10.1016/j.gpb.2022.10.004 | Modern sequence-based DFL prediction exists. |
| Database and fusion construction | Liu et al., *SynLinker* (2015) | 10.1093/bioinformatics/btv447 | Natural-linker extraction, linker retrieval, two-domain structural fusion already exist. |
| Circular permutation | Chen et al., *CirPred* (2021) | 10.1186/s12859-021-04403-1 | Linker design plus structural remodeling exists for a different topology. |
| Split-site prediction | Wang et al., *SplitSeek-Pro* (2026) | 10.1038/s41467-026-74059-z | A standalone site-prediction model is not new. |
| Experimental library | *High-throughput optimization of peptide-linker for fusing function protein with GFP* (2025) | 10.1016/j.pep.2025.106718 | GFP fusion linkers have been screened. |
| Multimodal ML design | Li et al., *Functional customization of peptide linkers in fusion proteins through multimodal deep learning approach* (2026) | 10.1016/j.synbio.2026.02.003 | ML customization of a fixed fusion linker has been demonstrated. |
| Structural uncertainty | McBride et al., *Predicting Pose Distribution of Protein Domains Connected by Flexible Linkers Is an Unsolved Problem* (online 2025; issue 2026) | 10.1002/prot.70062 | A single predicted fold is not enough to validate flexible-linker behavior. |

These are **comparison targets**, not all proven exact matches. In particular,
small-molecule/PROTAC linkers must be excluded from the peptide-linker core,
though they may inform methodology. The article *type* and exact methods of
every record require verification before citation in a paper.

## Current finding

The claims "we first identify natural linkers", "we first generate linkers",
"we first use ML for linker classification", and "we first fuse two uploaded
structures using a linker" are contradicted by prior work above. No defensible
novelty claim for LinkerForge has yet been established. A candidate claim about
joint attachment-site and peptide-linker optimization remains a **hypothesis
for a further systematic review**, not a finding. Natural-linker reconstruction
measures recovery of an evolutionary observation, not experimental success.

## Focused joint site-and-linker search (8 October 2026)

The broad joint-design claim is **not new as a problem statement**. Critical
additional precedents:

| Paper | DOI | What it already does |
|---|---|---|
| *Engineering of temperature- and light-switchable Cas9 variants* (2016) | 10.1093/nar/gkw930 | Explicitly sampled insertion site, linker length, and linker sequence simultaneously in a construct library. |
| *A computational method for the design of nested proteins by loop-directed domain insertion* (LooDo, 2018) | 10.1002/prot.25445 | Uses linker fragments to place an inserted domain and jointly optimizes loop conformation and loop/interface residue identities. The insertion-site input is specified. |
| *A sort-seq approach to the development of single fluorescent protein biosensors* (2021) | 10.1021/acschembio.1c00423 | Studies insertion-site and linker-sequence optimization for domain-insertion biosensors, with ML on linker effects. |
| *De novo design of immunoglobulin-like domains* (2022) | 10.1038/s41467-022-33004-6 | Computationally samples multiple insertion sites and linker lengths, designs linker composition, and scores closed designs. |
| *Rational engineering of allosteric protein switches by in silico prediction of domain insertion sites* (ProDomino, 2025) | 10.1038/s41592-025-02741-z | Learns insertion-site permissibility from natural events; linker co-design is not its stated central model task. |
| *Family-level specialization in protein domain insertion architectures* (2026) | 10.1002/pro.70586 | Reports a large natural domain-insertion event dataset that may be relevant to training and leakage control. |

**Go/no-go for novelty:** no-go for claiming that simultaneous choice of a
protein attachment/insertion site and peptide-linker properties is a new
research problem. The narrower statement, "one learned, pair-conditioned
model jointly proposes site and linker sequence across diverse protein pairs,"
was not located in this focused search, but absence in retrieved results is not
proof of novelty. A paper should instead commit to a falsifiable empirical
claim against these precedents, with clear topology and evaluation limits.

## Next screening pass needed before a research-gap statement

1. Exclude non-peptide linkers, chemical cross-linkers, PROTACs, and viral
   fusion-protein papers where "fusion" has a different meaning.
2. Screen titles/abstracts in the pool by two reviewers and record inclusion
   decisions, exclusion reasons, DOI, and full-text availability.
3. Snowball backward and forward from SynLinker, CirPred, DROP, TransDFL,
   Li et al. 2026, and any newly found close systems.
4. For every included design method, extract inputs, task, dataset, topology,
   candidate-generation method, ranking, validation, baselines, and code/data.
5. Draft a gap only after the comparison matrix is complete. Re-run the search
   just before submission; the field is moving quickly.
