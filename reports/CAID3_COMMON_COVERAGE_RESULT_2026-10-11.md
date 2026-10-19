# CAID3 Linker: seven archived predictors on identical targets

The exact official CAID3 Linker reference and seven released predictor files
were screened for **complete per-residue scores and matching sequence**. The
intersection is 27 proteins, 1,214 positive residues, and 15,570 total
residues. This is smaller than the 28 protein headers in IPA-AF2-Linker's
original submission: only 27 satisfy the stricter full-residue condition.
DisoFLAG-DFL misses DP04198; IPA-AF2-Linker misses or incompletely scores
DP04066, DP04156, DP04166, and DP04198. The other five methods fully score
all 31 reference proteins. Exact IDs, source hashes, and software version are
in `caid3_common_coverage_2026-10-11.json`. Filtered files are under ignored
`artifacts/caid3-common-coverage-001/`.

The official [CAID evaluator](https://github.com/BioComputingUP/CAID) was
rerun on the unchanged prediction rows for **the same 27 proteins**. Full
outputs are under ignored `artifacts/caid3-common-eval-001/`.

| Released predictor | APS | AUC-ROC | Fmax |
| --- | ---: | ---: | ---: |
| IPA-AF2-Linker | 0.482 | 0.898 | 0.491 |
| LINKER-Pred-Lite | 0.429 | 0.872 | 0.473 |
| DisoFLAG-DFL | 0.410 | 0.846 | 0.464 |
| LINKER-Pred | 0.398 | 0.884 | 0.467 |
| LINKER-Pred2 | 0.386 | 0.889 | 0.464 |
| APOD | 0.369 | 0.852 | 0.438 |
| DFLpred | 0.097 | 0.491 | 0.148 |

This is a **post hoc common-coverage reanalysis**, not a new blind challenge
or a significance test. It fixes a basic comparison problem in the published
full-reference table—methods have different coverage—but the small public
reference still cannot establish no-linker specificity or a future model's
independent superiority. IDPFunNet was published later and is absent from
the archived submissions. Do not tune LinkerForge on these public labels.
