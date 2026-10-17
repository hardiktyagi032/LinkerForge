# APOD feature and ablation audit — 2026-10-17

Primary source: [APOD paper, Bioinformatics 2020](https://academic.oup.com/bioinformatics/article/36/Supplement_2/i754/6055918), DOI 10.1093/bioinformatics/btaa808. This is a method audit, not a reproduction or a comparison on CAID3.

## Documented method

APOD uses a parametrized support-vector machine over 170 features, combining local sliding-window amino-acid composition, predicted secondary structure and relative solvent accessibility, sequence conservation, local predicted disorder, and a whole-protein predicted-disorder fraction (`DisCon`). Its paper explicitly contrasts this with a local-only DFLpred feature profile. In its TR166 five-fold ablation, the authors report that conservation alone is the strongest single group (AUC .74, MCC .29), whereas local disorder alone yields AUC .56 and MCC .04; local plus protein-level disorder yields AUC .69 and MCC .11. These are the authors' within-paper ablations, not numbers transferable to our protected split.

## Local gap and limits

Our protected baseline uses frozen ESM2-35M and a SAM-like head on non-overlapping 510-residue chunks. It does **not** explicitly compute APOD's conservation, predicted secondary structure, solvent accessibility, or whole-protein predicted-disorder fraction. The completed single-seed `global_context` arm improved protected-development APS over its matched baseline (.8269 versus .8012), but its context is pooled over a **chunk**, not APOD's full protein, and it does not prove APOD's feature mechanism explains external transfer. Seeds 17 and 31 and Fmax are pending in the ML track.

The transfer track quantified substantial unknown masking: known DFL labels cover 28.9% of training and 32.3% of development residues, while the auxiliary disorder source is fully labelled. Therefore a naive `DisCon` computed from DFL label `1` values would be scientifically invalid and would leak supervision. Any APOD-like global disorder feature must be a prediction generated from sequence alone at inference and applied to whole proteins under the same feature pipeline for both comparison arms.

## Actionable handoff to ML track

1. Complete the two repeat seeds and Fmax for chunk-global context before another architecture claim.
2. If a whole-protein disorder-fraction feature is trialled, produce it with an independently trained sequence-only disorder predictor, record predictor revision and full-sequence input hash, and ablate it against the same protected split and equal-coverage baseline. Do not derive it from DFL labels or CAID3.
3. A conservation/secondary-structure/accessibility trial requires versioned sequence-aligned predictions for **all** proteins in both arms, matched coverage and a computation-cost report. If inputs are absent, fail closed; do not substitute native structures or missing-value zeros.

Source anchors: paper §§2.2–2.3 and 3.3, Figure 4; local config `configs/dfl_caid3_protected_baselines_2026-10-16.json` SHA-256 `e49780fa6917a446a73d8fb93ae9303151268617fe482cd357c0fa1db69035a1`; transfer audit `reports/track-transfer/2026-10-17-protected-label-coverage.json`; ML result `reports/track-ml/2026-10-17-competitor-gap-seed7-results.md`. No GPU job or CAID3 comparison was run.
