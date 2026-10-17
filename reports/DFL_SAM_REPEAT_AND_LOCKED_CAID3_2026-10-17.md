# Protected SAM repeat and locked CAID3 retrospective

Status: complete on 2026-10-17 IST. This is a **negative external-transfer result**, not a breakthrough. The CAID3 scores below were computed only after checkpoint selection was frozen in `reports/dfl_sam_repeat_frozen_selection_2026-10-17.json`. CAID3 is public and previously inspected in this project, so the comparison is retrospective rather than a fresh independent blind test.

## Three-seed protected-development comparison

All nine best checkpoints were rescored on the same 7,427 known development residues (1,267 positive). Rescored APS matched each training manifest. Seeds were 7, 17, and 31. The two new variants reused the same protected data, frozen ESM-2 encoder, training schedule, and score channel as the SAM-like disorder-transfer baseline. Four repeat jobs completed in two bounded, sequential rounds; the ledgers are in `artifacts/dfl-sam-repeat-2026-10-17`.

| Model | Mean APS | Mean AUROC* | Mean Fmax | Mean no-positive-protein proxy specificity | APS versus baseline | Specificity versus baseline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Matched SAM baseline | 0.7918 | 0.9076 | 0.7022 | 0.7843 | — | — |
| Multiscale features | 0.7986 | 0.9007 | 0.7177 | 0.7451 | +0.0067 | -0.0392 |
| Boundary + query | 0.7955 | 0.9090 | 0.7121 | 0.7059 | +0.0037 | -0.0784 |

*Mean AUROC is computed from the three checkpoint scores in `reports/dfl_sam_repeat_development_scores_2026-10-17.json`; the rounded display is secondary. Both variants exceeded baseline mean APS but failed the preregistered no-positive proxy-specificity loss limit of 0.02 absolute. The selection rule in `literature/DFL_SAM_REPEAT_SELECTION_RULE_2026-10-17.md` therefore froze the baseline seed-7 checkpoint (the seed closest to baseline mean APS), not the highest-scoring new variant. The freeze manifest records its SHA-256 and the score/rule/data hashes.

## One-time locked CAID3 common-27 comparison

All eight score files cover the identical 27 proteins, 15,570 residues, and 1,214 positive residues. Values below are from the official CAID evaluator's dataset-level APS, AUC-ROC, and maximum-F1 (`f1s`) outputs; a separate local scorer cross-checked them to within rounding.

| Predictor | APS | AUROC | Fmax |
| --- | ---: | ---: | ---: |
| IPA-AF2-Linker | 0.482 | 0.898 | 0.491 |
| LINKER-Pred-Lite | 0.429 | 0.872 | 0.473 |
| DisoFLAG-DFL | 0.409 | 0.846 | 0.464 |
| LINKER-Pred | 0.398 | 0.884 | 0.468 |
| LINKER-Pred2 | 0.386 | 0.889 | 0.464 |
| APOD | 0.369 | 0.852 | 0.438 |
| **LinkerForge frozen SAM baseline** | **0.241** | **0.695** | **0.345** |
| DFLpred | 0.097 | 0.491 | 0.148 |

The official output and exact eight prediction files are in `reports/dfl_sam_repeat_locked_caid3_2026-10-17`. The selected checkpoint is not competitive with the strongest released methods here. This result does not establish why transfer fails; differences in label definitions, source composition, family coverage, or representation could contribute and require controlled audits. CAID3 contains no no-linker proteins, so it cannot assess specificity.

## Execution incident and integrity

The first evaluator subprocess received a relative predictions path while its working directory was the evaluator folder. It found zero prediction files and exited with `KeyError: 'f1s'`. The already-frozen checkpoint and eight prediction files were not changed. The same official evaluator was rerun with absolute reference, prediction, and output paths; it processed all eight files successfully. No CAID3 score was used to change the selected checkpoint, threshold, architecture, or training. The failed first invocation and successful replay are retained in the command logs/session and output directory. This public set must not be used for another tuning cycle or a superiority claim.
