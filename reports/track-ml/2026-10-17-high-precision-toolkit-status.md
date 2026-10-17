# High-precision toolkit status for hand-off (2026-10-17)

Status: code and CPU tests only. No model was trained, no real score was evaluated, and no result is claimed. Everything here is on `claude/dfl-high-precision-toolkit` (PR #1).

## Verified (CPU, numpy only)

`PYTHONPATH=src python3 -m unittest tests.test_pu_loss tests.test_ensemble_scoring tests.test_selective_prediction tests.test_structure_span_decoding` ran 43 tests, OK, 2 skipped. Metrics were checked against brute-force references and two hand-computed Clopper-Pearson values.

## NOT verified

- torch: `pu_semantic_loss`, its gradients, and the launcher wiring in `scripts/run_caid3_protected_sam_pu_trial.py` (py_compile only). The two torch parity tests are skipped because torch was not installed.
- `scripts/score_ensemble_development.py` was never run. No checkpoint-to-member `.npz` adapter exists.
- Nothing was run on real development scores or real AlphaFold data. The AF fixture in tests is invented.
- Full repo test suite not run (`unittest discover` fails on import because `tests/` is not a package; not investigated).
- sklearn-based evaluators were not compared against the numpy reimplementations.

## Known limits that must not be dropped

- PU `class_prior` is null in `configs/dfl_pu_loss_2026-10-17.json`, so the launcher refuses to run. The instance-mask term still treats `0` as negative (a confound).
- The Clopper-Pearson bound is residue-level and ignores within-protein correlation, so it is optimistic. A threshold chosen on the split it is reported on is not a guarantee. Splits are by protein id, not family cluster.
- Measured precision is a lower bound on true precision because labels are incomplete.
- The data preflight still fails closed (DP94 overlap). GPU training needs a new family-disjoint split first. CAID3 is spent and must not select anything.

## Next steps, in priority order

1. Family-disjoint split with hash-checked preflight.
2. Reproducible mask-policy comparison on frozen scores.
3. Conformal thresholds on development scores with a calibration/evaluation split by family cluster.
4. Only then PU loss and ensembles, each against a matched baseline with three seeds.
