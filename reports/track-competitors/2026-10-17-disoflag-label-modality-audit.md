# DisoFLAG label/modality audit — 2026-10-17

Primary source: [Pang and Liu, DisoFLAG, *BMC Biology* 2024](https://bmcbiol.biomedcentral.com/articles/10.1186/s12915-023-01803-y), DOI 10.1186/s12915-023-01803-y. The [authors' released repository](https://github.com/YihePang/DisoFLAG) is linked by the project, but its live README was not successfully fetched during this wake; repository-dependent claims below are withheld.

## Documented mechanism and data

The paper says inference takes amino-acid sequence only and predicts intrinsic disorder plus six IDR functions: protein, DNA, RNA, ion and lipid binding, and flexible linker. Internally it uses ProtT5 embeddings, Bi-GRU sequence context, an attention GRU, six function embeddings and a function-interaction graph whose edges use a precomputed information-gain matrix; a GCN aggregates function information. This is **not** a graph of physical protein residues or 3D contacts.

The authors derived function labels from DisProt 9.3 ontology terms and subterms, retained 925 proteins, clustered at 25% sequence similarity using CD-HIT, and report 589 train, 148 validation and 188 DP93 test proteins; a separate 98-protein DP94 test came from newer DisProt entries. These are the authors' partitions, not proof that our differently sourced protected split has equivalent labels or independence.

## Local implementation gate

Our protected auxiliary file contains 72 records with a **binary disorder task**; it does not provide the six aligned function tracks needed to estimate DisoFLAG's function co-occurrence/information-gain graph. Our DFL train/development labels include unknown `x` residues and cannot fill missing binding-function labels. Therefore a true DisoFLAG-like function graph is presently **data-gated**. Inventing all-zero missing functions, treating unknown as negative, or deriving a function adjacency from CAID3 labels would invalidate the experiment.

A fair preparatory artifact is an ontology-mapping table for each function, with source release, evidence IDs, residue coordinates and unknown masks, followed by train-only estimation of the interaction matrix after homology-family splitting. The same ProtT5/feature coverage, data, compute and scoring must be available to a matched no-graph comparator. On the local 6 GB GPU, embedding generation may need offline/cloud preprocessing; no capacity claim has been verified. A single DFL head on ESM2 is not a reproduction of this paper.

The ML track's three-seed global-context variant was not promoted because two seeds failed its preregistered proxy-specificity guardrail. That result does not test the DisoFLAG function graph.

Local provenance: protected data manifest SHA-256 `a8f5348c6b6d2845e51bc12fdba0b1dcf02c33b22039baa04cab91069b792d24`; label coverage audit `reports/track-transfer/2026-10-17-protected-label-coverage.json`; ML reconciliation `reports/track-ml/2026-10-17-global-context-three-seed-reconciliation.md`. No GPU job or CAID3 comparison was run.
