# DLD detector: high-precision recall comparison (development only)

Date: 9 October 2026. These are DLD fold-4 **validation** results, not an
independent blind test or an experimentally validated linker detector. DLD
fold 5 was viewed in earlier project work and must not be used for model
selection here.

The fixed decision rule selects the greatest residue recall at empirical
precision >= 0.90, with at least 50 true-positive residues and exact score
ties. No-linker-protein specificity may not fall by >0.02 absolute relative
to the matching baseline. This is a validation-selected operating point; its
precision on a new dataset is unknown.

| Frozen ESM-2 35M variant | Selected epoch | TP / 6205 | FP | Precision | Recall | No-linker specificity | AUPRC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Weighted-BCE baseline | 6 | 475 | 52 | 0.901328 | 0.076551 | 0.971631 | 0.399801 |
| Focal loss, gamma 2 | 6 | 396 | 44 | 0.900000 | 0.063820 | 0.964539 | 0.399293 |
| Asymmetric negative focusing, gamma 2 | 5 | 525 | 58 | 0.900515 | 0.084609 | 0.964539 | 0.404802 |
| Equal arithmetic mean: baseline + asymmetric | 6 + 5 | 534 | 59 | 0.900506 | 0.086060 | 0.957447 | 0.415986 |

The asymmetric model detects 50 more labelled linker residues than the
baseline at the specified validation precision. Its no-linker specificity
drops by 0.007092 absolute, within the predeclared 0.02 guardrail. A fixed
equal-weight ensemble detects 59 more than baseline but requires two heads
at inference and drops specificity by 0.014184; its nine-residue increment
over asymmetric alone is not enough to justify promotion without replication.

## Provenance

- Training split: DLD source folds 1–3; validation split: fold 4.
- Training shard SHA-256:
  `c43952c4f943f458ba61905c34a59e04fadca5607b95d6afc9bd9d1475252c41`.
- Validation shard SHA-256:
  `290992af4a93c14ba007197c282367734af8ec878783d5e668ee4960128a3461`.
- Backbone: `facebook/esm2_t12_35M_UR50D`, revision
  `6fbf070e65b0b7291e7bbcd451118c216cff79d8`.
- Baseline checkpoint SHA-256:
  `1dac5c4097eb96acdc6de237bae28af7e1f067cfd72857898fc208a551331ec0`.
- Asymmetric checkpoint SHA-256:
  `adc41ba95190df0c55a50e75f80f1042386f6e90ae87c1a1620e53eb09afc42c`.
- Source run directories: `artifacts/esm2-35m-linker-run-001`,
  `artifacts/esm2-35m-focal-gamma2-run-001`, and
  `artifacts/transfer-35m-asymmetric-highprecision-run-001`.
- The fixed ensemble is reproducible with
  `scripts/compare_esm2_validation_ensemble.py`; no weight tuning was done.

## Interpretation and next gate

This is a **promising single-seed validation result**, not a breakthrough or
final model. The gain is only 0.81 percentage points of residue recall for
the single asymmetric head. Repeat with independent seeds and assess
cluster-level variability before promotion. Do not claim that the precision
threshold will transfer to unseen families. The larger opportunity remains
the verified source-label/segment experiment in
`literature/BREAKTHROUGH_STRATEGY.md`; do not collapse undocumented source
code `0` into a new training class without establishing its meaning.
