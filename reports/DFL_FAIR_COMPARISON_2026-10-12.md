# LinkerForge DFL: same-target retrospective comparison

**Conclusion: the current LinkerForge heads do not outperform the original linker-detection systems.** The apparent TE82 gain is mainly a within-development-set result, not evidence of frontier performance. This report uses frozen checkpoints; no checkpoint, epoch, threshold, or architecture was selected after opening CAID3 or TE64 here.

## Public CAID3: identical 27-protein reference

The 27-protein CAID3 Linker subset is the exact full-residue intersection of seven original released `.caid` score submissions. It contains 15,570 residues, 1,214 labelled positives. LinkerForge's three frozen TE82-selected checkpoints were inferred on these same 27 input sequences. The local evaluator produced the same published-submission APS/AUC/Fmax values (to three decimals) as the previous official common-coverage analysis. All three models and all seven released submissions therefore have 100% residue coverage on precisely the same reference here.

| Predictor on the common 27 | APS | AUROC | Fmax | Provenance |
| --- | ---: | ---: | ---: | --- |
| IPA-AF2-Linker | **0.482** | **0.898** | **0.491** | Released CAID3 submission |
| LINKER-Pred-Lite | 0.429 | 0.872 | 0.473 | Released CAID3 submission |
| DisoFLAG-DFL | 0.409 | 0.846 | 0.464 | Released CAID3 submission |
| LINKER-Pred | 0.398 | 0.884 | 0.468 | Released CAID3 submission |
| LINKER-Pred2 | 0.386 | 0.889 | 0.464 | Released CAID3 submission |
| APOD | 0.369 | 0.852 | 0.437 | Released CAID3 submission |
| DFLpred | 0.097 | 0.491 | 0.147 | Released CAID3 submission |
| LinkerForge CNN | 0.089 | 0.542 | 0.165 | Frozen seed-7 TE82-selected checkpoint |
| LinkerForge span | 0.085 | 0.507 | 0.154 | Frozen seed-7 TE82-selected checkpoint |
| LinkerForge precision loss | 0.087 | 0.520 | 0.159 | Frozen seed-7 TE82-selected checkpoint |

On this common public reference, **even the historical APOD and LINKER-Pred2 submissions are far ahead of LinkerForge**. We do not claim inferiority to every current system in every setting; this is a specific same-target retrospective benchmark. The CAID3 reference includes only linker-positive proteins, so it cannot test no-linker-protein specificity. It is public and has been viewed in this project; it is not a fresh prospective blind test. Remote homology between original TR166 training and CAID3 is not certified absent. The original submissions may have used different training data and input modalities; this comparison measures deployed-score performance on common targets, not equal-training-data algorithm efficiency.

## Original TransDFL TE64: frozen-checkpoint transfer check

The three LinkerForge models were also scored once on the original published TE64 set, using its `0`/`1` residue labels and excluding every `x` residue exactly as in training/development. This has 64 proteins, 10,256 scored residues and 949 positives. The original TransDFL checkpoint is **not** included in this numeric table; its released implementation is TensorFlow 1.13/Python 3.5 and was not executed in the current environment. Calling this table a reproduced TransDFL-vs-LinkerForge head-to-head would be incorrect.

| Frozen LinkerForge head | TE82 development APS | TE64 retrospective APS | TE64 AUROC |
| --- | ---: | ---: | ---: |
| CNN | 0.450 | 0.214 | 0.664 |
| Span | 0.455 | 0.214 | 0.669 |
| Precision loss | **0.497** | **0.223** | 0.669 |

The precision-loss method's development gain over CNN was +0.0469 APS, but on TE64 it was only +0.0084. The marked TE82-to-TE64 drop for all three is evidence of poor transfer and/or substantial distribution differences. It does not alone prove statistical overfitting, because the original sets may differ in composition and annotation, but it decisively rules out the claimed broad improvement from TE82 alone.

## Reproducibility and next decision

The machine-readable output is `reports/dfl_caid3_common_retrospective_2026-10-12.json` and `reports/dfl_te64_frozen_retrospective_2026-10-12.json`. Scripts are `scripts/compare_dfl_caid3_common.py` and `scripts/evaluate_dfl_te64_frozen.py`; each refuses to overwrite its one-time result. Checkpoint and input hashes, exact method names, common coverage, software, and limitations are recorded there. The CAID3 released-score files remain unchanged under `artifacts/caid3-common-coverage-001/predictions/`. The original TransDFL source archive includes a checkpoint but requires a separately pinned legacy runtime and feature pipeline before exact inference can be responsibly claimed.

**Do not promote the precision-loss head.** The next research unit must investigate annotation/source shift and train/test family structure, then reproduce a competitive published model on the same inputs (or keep using verified archived submissions for CAID3). Any new loss/architecture needs a predeclared, contamination-audited evaluation; retuning on CAID3 or TE64 would destroy their value as diagnostic tests.
