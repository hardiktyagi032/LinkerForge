# Selective prediction with a precision-targeted threshold — preregistration, 2026-10-17

Status: method and code preregistration. No score has been computed on real data; tests use synthetic scores only. Code: `src/linkerforge/detector/selective.py`; tests: `tests/test_selective_prediction.py`.

## Binding constraints

- Input is **family-disjoint development data only** (protected development proteins and their per-residue development scores). No CAID3 labels, scores, per-protein errors or thresholds are used, and nothing here may be rerun against the spent CAID3 common-27 set. A future untouched benchmark may receive the *frozen* threshold only after the selection manifest is sealed, per the untouched-comparison contract.
- Labels are 1 (linker), 0 (negative), -1 (unknown, 'x'). Unknown residues are **masked**: never counted as negative, never in any count, threshold search or temperature fit.

## Procedure

1. Split development proteins **by protein** (never by residue) into calibration and evaluation halves (seeded, default 50/50, disjoint). Because the development set is itself family-disjoint from benchmarks, any homologous proteins inside development should be grouped upstream by cluster; this module splits only by the ids given, so pass cluster ids as the "protein" key if clusters are available.
2. Optional temperature scaling: fit a single T>0 on the calibration split by minimising binary cross-entropy of sigmoid(logit(score)/T). It is monotone, so it changes calibrated probabilities but not residue rankings; evaluation uses the same T. Off by default.
3. For each precision target (0.99 and 0.90): among distinct calibration scores, choose the **lowest** threshold whose calibration precision has a one-sided exact **Clopper-Pearson lower confidence bound** >= target (alpha = 0.05, residue level; at least `min_tp` calibration true positives, default 1). Residues with score >= threshold are predicted; others abstain. If no threshold qualifies, the model abstains everywhere (threshold = None) and this is reported as infeasible, not relaxed.
4. Apply the threshold once to the evaluation half. Report raw TP/FP/FN/TN, precision, recall, predicted fraction (coverage), and **bootstrap-over-proteins** percentile 95% intervals (1000 resamples of evaluation proteins; resamples with no predictions are excluded from the precision interval and counted).

## Caveats stated up front

- **Labels are incomplete.** A residue scored positive but lacking an annotation counts as a false positive even if it is a real linker. Measured evaluation precision is therefore a **lower bound on true precision**, and the calibration bound is conservative in the same direction for that reason. Recall is relative to annotated positives only.
- Clopper-Pearson treats residues as independent; residues within a protein and homologous proteins are correlated, so the lower bound is optimistic. Scanning many thresholds adds a mild selection effect. The protein-level split and protein bootstrap are the honest check; the bound guarantees nothing at 0.99 with few calibration positives. A 0.99 target requires about >=300 calibration true positives with no false positives (0.05^(1/n) >= 0.99).
- The achieved evaluation precision may fall below target; that is a reportable negative result, not a reason to retune on evaluation data.
- Single split results are developmental. Repeat over several split seeds and model seeds before any statement.

## Verification status

Unit tests on synthetic data cover the Clopper-Pearson values, protein-disjoint splitting, lowest-threshold selection, abstention when infeasible, unknown masking, count consistency, temperature fitting and bootstrap determinism. Not run: any real-score evaluation.
