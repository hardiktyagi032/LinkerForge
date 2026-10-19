# CAID3-sequence-screened DFL development baselines (2026-10-16)

Status: completed development round, **not** a CAID3 benchmark result or a superiority claim.

The 12 planned trials completed with exit code 0. Each recorded `blacklist_status=passed_before_training`, 12 DFL epochs, the same screened train/development/auxiliary hashes, and the same ESM-2 model ID (`facebook/esm2_t12_35M_UR50D`). The run ledger charged 1,591.39 seconds (0.442 GPU-hours). Source commit in the trial manifests: `4519cab377c531e0dc3131a8136654b2a98844c3`. Runner, data, and configuration hashes are recorded in the ledger and individual manifests under `artifacts/dfl-caid3-protected-baselines-2026-10-16/`.

The sequence-only CAID3 blacklist retained 79 TR166 train, 42 TE82 development, and 72 DisoFLAG auxiliary proteins. It excludes exact IDs/sequences/containment and declared local-alignment matches, not all possible distant homologs. The TE82 development set is not CAID3 and is not an independent blind test.

| Architecture and training | Seed 7 APS / AUROC / recall@90% precision | Seed 17 | Seed 31 | Mean APS | Mean AUROC | Mean recall@90% precision |
|---|---:|---:|---:|---:|---:|---:|
| SAM-like, direct | .791 / .919 / .538 | .764 / .894 / .497 | .743 / .898 / .478 | .766 | .903 | .504 |
| SAM-like, disorder transfer | .801 / .910 / .571 | .804 / .914 / .593 | .770 / .899 / .514 | .792 | .908 | .559 |
| YOLO-1D, direct | .598 / .878 / .083 | .690 / .840 / .405 | .571 / .849 / .136 | .619 | .856 | .208 |
| YOLO-1D, disorder transfer | .547 / .811 / .093 | .618 / .840 / .000 | .621 / .889 / .133 | .595 | .846 | .075 |

Numbers in the seed cells and means above are rounded for display. The authoritative unrounded values are in each trial's `manifest.json`; the high-precision operating point requires at least 50 true-positive residues. The IoU≥0.5 region recall at fixed threshold 0.5 was low or variable (three-seed means: SAM direct .048, SAM transfer .321, YOLO direct .179, YOLO transfer .429), so residue-level APS should not be presented as good span-boundary identification. Region thresholds were not tuned here.

The APS-selected checkpoints were subsequently rescored on the **same filtered development residues** using `scripts/score_protected_dfl_development.py`. It checks the protected-data hashes and labelled-residue counts and maximizes F1 over exact score ties; it does not reselect checkpoints. Mean Fmax over seeds was SAM direct .667, SAM disorder transfer .702, YOLO direct .608, and YOLO disorder transfer .578. Per-seed Fmax, thresholds, counts, and checkpoint SHA-256 values are in `reports/dfl_caid3_protected_dev_fmax_2026-10-16.json`. These are development numbers, not CAID3 scores.

This is a comparison **within** the screened condition only. Earlier full-TR166/TE82 results used different data and cannot establish an architecture-only improvement or degradation. The next architecture must use these exact screened data, encoder, scoring, and development-selection rules. Do not inspect CAID3 scores until checkpoint selection has been frozen in a selection manifest; its one-time common-27 evaluation remains retrospective because CAID3 is public and previously viewed. A separate untouched, homology-audited test and no-linker negatives remain necessary for a publishable superiority claim.
