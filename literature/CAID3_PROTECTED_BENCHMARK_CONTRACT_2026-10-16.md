# CAID3-protected DFL comparison contract

Status: prospective **training-data contract** and public retrospective benchmark protocol; not an independent-result claim. CAID3 is already public and its labels were inspected earlier in this project.

## Data gate before every new training run

Run `scripts/preflight_caid3_protected_training.py` on the exact planned train, development, and auxiliary files. It must validate their hashes against `data/processed/caid3_protected_dfl_v1/manifest.json` and repeat the CAID3 ID/sequence/local-alignment blacklist. If any match is found or a hash changes, training stops. The blacklist uses CAID3 protein IDs and amino-acid sequences **only**, never its linker labels. The immutable source snapshots are retained separately; excluded records are listed in `blacklist.json` with match evidence. The first screened version retains 79/166 TR166 train, 42/82 TE82 development, and 72/110 auxiliary DisoFLAG proteins. These reduced sets define a new experimental condition and cannot be pooled numerically with earlier TR166/TE82 runs as if only the architecture changed.

The exclusion rule is exact ID/sequence/containment or local BLOSUM62 alignment with at least 25% identity, 50 aligned residues, and 50% coverage of the shorter sequence. This **does not prove** absence of remote homology, shared families, or ESM-2 pretraining exposure. Those remain separate audits.

## Frozen benchmark metrics

After development selection and checkpoint freeze, infer every model on the exact 27-protein, complete-residue intersection of the seven released CAID3 Linker submissions. Report the official CAID evaluator's **APS, AUC-ROC, and Fmax**, each to at least three decimals, plus target/residue coverage and raw counts. Preserve a separate full-31 result for methods that score all 31; never mix different coverage sets in a head-to-head table. Use the same reference, released prediction files, evaluator revision, and score orientation. The common 27 have 15,570 residues and 1,214 labelled linker residues in the existing archive.

No CAID3 label, metric, per-protein score, or rank may feed training, early stopping, threshold choice, architecture selection, or the next autoresearch proposal. Repeated public-set probing cannot produce an independent benchmark, even with a sequence blacklist. Treat CAID3 as a locked external retrospective report and pursue a genuinely untouched adjudicated test for a publishable superiority claim. CAID3 contains linker-positive proteins only; it does not evaluate no-linker specificity.

Sources: the [CAID3 reference and evaluator](https://github.com/BioComputingUP/CAID) and the project's saved official prediction archive and common-coverage audit.
