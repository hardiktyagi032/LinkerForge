# Official CAID3 linker predictor archive: local reproducibility check

On 11 October 2026, the official CAID3 prediction archive was downloaded
from <https://caid.idpcentral.org/assets/sections/challenge/static/predictions/3/predictions.zip>
(76,480,806 bytes, SHA-256
`188868f53646d8395ef46d8d5e022c400e4234b21d38cfcf3ee91d719f19d84a`).
Seven pre-existing `.caid` score files were extracted into ignored
`artifacts/caid3-baselines-selected-001/`, without changing their contents.
The official [CAID evaluator](https://github.com/BioComputingUP/CAID) at
commit `7bab7e8880d7f949e480fdb377c5a5c8546ae336` was run on the exact
CAID3 Linker reference (SHA-256
`4c204ef49ffa12fe166883e6b2cff0012cabee21260b8f32f997081d0e2fa0f8`).
Full evaluator outputs are in ignored `artifacts/caid3-baselines-eval-001/`.

| Released predictor | Proteins with score file entries / 31 | CAID3 APS | AUC-ROC | Fmax |
| --- | ---: | ---: | ---: | ---: |
| IPA-AF2-Linker | 28 | 0.474 | 0.897 | 0.483 |
| DisoFLAG-DFL | 30 | 0.393 | 0.846 | 0.440 |
| LINKER-Pred-Lite | 31 | 0.393 | 0.854 | 0.446 |
| LINKER-Pred | 31 | 0.377 | 0.870 | 0.471 |
| LINKER-Pred2 | 31 | 0.365 | 0.875 | 0.460 |
| APOD | 31 | 0.323 | 0.843 | 0.395 |
| DFLpred | 31 | 0.075 | 0.473 | 0.127 |

These are **released historical CAID3 submissions**, not models trained by
LinkerForge. The coverage counts above are header intersections with the 31
reference IDs; score coverage within a protein also needs checking before
any stricter common-coverage analysis. CAID reports metrics with its own
coverage handling. The 28/30/31-protein rows are not an identical-target
head-to-head ranking. A 28-protein common-coverage rerun is the next fair
reanalysis; do not select a new model on these public labels and then call
this an untouched independent test.

The existing DLD-trained LinkerForge checkpoint yielded exploratory CAID3
APS 0.164 and AUC-ROC 0.756 in a separate official-evaluator run. That
checkpoint was trained for a different ontology and has three known
high-identity CAID3/DLD overlaps, so its number is a cross-task diagnostic,
not a valid claim of inferiority or superiority on a clean prospective test.
IDPFunNet was published after CAID3 and is **not** in this archive; it needs
a separately versioned, matched inference run.
