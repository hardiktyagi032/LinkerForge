# PU-loss preregistration — 2026-10-17

Status: preregistration only. No training has been run, no prior has been estimated, and no result exists. Developmental, not an independent-superiority claim.

## Hypothesis

In the DFL labels, `1` is a curated linker residue and `0` is merely not annotated, so treating `0` as a verified negative biases the residue head against unannotated true linkers and caps recall at high precision. A non-negative PU risk (nnPU, Kiryo et al. 2017; uPU, du Plessis et al. 2015) that treats `0` as *unlabeled* with an explicit positive prior should raise development masked-residue APS and recall at fixed high precision relative to the BCE baseline, without losing specificity. Null: no gain, or a gain bought with specificity loss. Both outcomes are reported.

## Design

- **Change (one thing):** replace only the DFL-stage semantic residue BCE of the SAM-like head with the PU risk in `src/linkerforge/models/pu_loss.py` (logistic loss; `nnpu` default, `upu` allowed as an ablation only if budget remains). Auxiliary-IDR stage, presence/query/boundary terms, encoder, optimizer, windows and scoring are unchanged. Launcher: `scripts/run_caid3_protected_sam_pu_trial.py`; config `configs/dfl_pu_loss_2026-10-17.json`.
- **Label handling:** `1` positive; `0` unlabeled drawn from a mixture with prior pi; `x` masked everywhere (never negative, never unlabeled). Padding is `x`.
- **Class prior:** required explicit config value, no default; the shipped config holds `null` and the launcher fails closed until it is set. pi is estimated once from protected *training-split* labels (positive-residue fraction over non-`x` residues, with its uncertainty) and recorded with the split hash before any GPU job. pi may not come from development scores, CAID3, DP94 or any benchmark label. Because `0` residues contain unannotated true linkers the raw fraction may understate pi; sensitivity at 0.5x and 2x is a documented ablation only if budget remains and is selected on development only.
- **Known confound:** the instance-mask term in `segmenter_loss` still treats `0` as negative for query-matched instances. It is left unchanged to keep the arm a single-term change; the report must name it.
- **Matched baseline:** the existing SAM-like disorder-transfer baseline retrained/available on identical protected train/development/auxiliary files, frozen ESM2-35M encoder, 3 auxiliary + 12 DFL epochs, AdamW lr 3e-4, 510-residue windows, masked-APS checkpoint selection, same evaluator and residue coverage, at seeds 7, 17, 31.
- **Seeds:** 3 (7, 17, 31), same as the baseline. One local GPU job at a time; each trial bounded to 1800 s; round capped at six GPU-hours; stop on first failure.
- **Gate:** the protected-data preflight (`protected.preflight()`) and the full benchmark sequence-registry check must pass before every job. It currently fails closed for `caid3_protected_dfl_v1` (see the untouched-comparison contract); this preregistration does not authorize bypassing it. No job may launch until a new versioned family-disjoint split exists.

## Metrics (development split only, pooled over non-`x` residues)

1. Residue APS (selection metric).
2. Fmax (after checkpoint rescoring).
3. Recall at empirical precision >= 0.90 and at >= 0.99, with TP floor (>= 50 TP at 0.90; report TP count at 0.99 and mark the figure unreliable if TP < 50) and exact tie handling.
4. No-positive proxy specificity: 17-protein partial-label proxy, raw counts reported; not verified no-linker specificity.
5. Also reported: AUROC, region recall at IoU >= 0.5 and threshold 0.5, runtime, peak VRAM, fraction of nnPU steps clamped, count of skipped (empty-class) batches.

## Decision rule

- Guardrail: the arm is not promoted if proxy specificity falls by more than 0.02 absolute versus the matched baseline (mean over seeds and in any single seed).
- Promising only if mean APS and recall at precision >= 0.90 both exceed the baseline mean and the sign agrees in all 3 seeds. Otherwise report as negative. Any gain is developmental and does not establish superiority; the CAID3 retrospective is spent and no CAID3 label, score or per-protein result is used for the prior, selection or thresholds. A superiority claim still requires the untouched, family-audited, one-time protocol in `literature/DFL_UNTOUCHED_COMPARISON_CONTRACT_2026-10-17.md`.

## Evidence at preregistration

Unit tests (`tests/test_pu_loss.py`) cover config fail-closed behavior, `x` masking, padding, uPU/nnPU values and clamping, and empty-class policy. The torch implementation's parity tests exist but had not been executed at the time of writing (torch absent in the authoring environment).
