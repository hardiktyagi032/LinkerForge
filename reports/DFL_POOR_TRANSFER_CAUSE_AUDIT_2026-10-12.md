# LinkerForge DFL transfer failure: causal audit (12 October 2026)

## Finding

The development number and the deployment benchmark were answering different
questions. The published TransDFL-style split masks `x` residues from both
training loss and evaluation; CAID3 Linker scores every reference residue as
linker (`1`) or non-linker (`0`). This **evaluation-policy mismatch is a
measured major cause** of the apparent development-to-CAID3 collapse. It is
not the complete explanation: on the untouched original TE64 proteins,
discrimination deteriorates even among the explicitly labelled residues of
linker-containing proteins. A single, unique biological root cause of that
remaining error is **not identifiable from these annotations**. Claiming one
would turn unlabelled residues into invented ground truth.

## Controlled checks (frozen CNN checkpoint, no refitting or threshold tuning)

| Evaluation population | Residues | Positive prevalence | APS | AUROC |
|---|---:|---:|---:|---:|
| TE82, original `0/1` mask | 13,694 | 16.23% | 0.450 | 0.773 |
| TE82, same scores, `x` counted as `0` | 36,938 | 6.02% | 0.115 | 0.635 |
| TE82 linker-containing proteins only, `x` as `0` | 21,767 | 10.21% | 0.144 | 0.558 |
| TE64, original `0/1` mask | 10,256 | 9.25% | 0.214 | 0.664 |
| TE64 linker-containing proteins only, original mask | 2,221 | 42.73% | 0.374 | **0.365** |
| TE64 linker-containing proteins only, `x` as `0` | 28,096 | 3.38% | 0.038 | 0.469 |
| CAID3 public common set, all `0/1` | 15,570 | 7.80% | 0.089 | 0.542 |

The first TE82 intervention changes only the evaluation mask, not proteins,
scores, weights, or thresholds. Its APS decreases by 0.335 absolute and AUROC
by 0.139. Thus prevalence shift alone is insufficient: ranking against the
newly included residues also worsens. The CNN scores 17.3% of TE82 `x`
residues at or above 0.5. This is not a false-positive count because `x` is
unknown under the source protocol. On TE64, 39.5% of `x` scores are at least
0.5. The span and precision heads exhibit the same direction of collapse;
all three exact score tables are in the JSON result linked below.

The second intervention holds the explicit `0/1` mask but restricts to
linker-containing TE64 proteins. AUROC falls below 0.5, showing an additional
failure to rank the annotated linker spans above *known* negatives in those
proteins. It is not explained by the prevalence of positives, which is high
in that restricted scored subset. This cannot, by itself, distinguish changed
sequence families, span length, annotation criteria, or a learned shortcut.

TE82 contains 63% masked residues and TE64 75%; CAID3 common has no masked
residues. TE82 median linker-span length is 24 versus 18 in TE64 and CAID3.
CAID3 consists only of linker-containing proteins, unlike the 44/82 no-linker
TE82 and 32/64 no-linker TE64 records. These are observed shifts, **not**
separately proven causes.

## Software-error check

Re-scoring TE82 one protein at a time versus the training evaluator's padded
batches changes CNN APS from 0.450139 to 0.449508 (0.000631). A local
padding/edge inconsistency exists (89 of 13,694 scored residues differ by more
than 0.01), but its measured effect on development APS is far too small to
account for the observed 0.361 difference from CAID3 APS. This does not certify
all software correct; it rules out this particular inference-mode difference
as the dominant explanation.

## Comparison boundary

On the same 27 CAID3 proteins and 15,570 residue positions, released
competitor submissions score APS 0.369 (APOD), 0.386 (LINKER-Pred2), 0.409
(DisoFLAG-DFL), and 0.482 (IPA-AF2-Linker); our CNN scores 0.089. This is a
public retrospective comparison, not a fresh blind test. The competitor
weights are not retrained on our source data. Current sequence-homology
screens are not a full contamination audit. None of this supports a frontier
claim.

## What remains genuinely unidentified, and the decisive evidence needed

1. The biological truth of source `x` residues is unknown. A blinded expert
   adjudication of a stratified sample, especially high-scoring `x` spans,
   would show which are true additional linkers and which are errors. Until
   then, the `x`-as-`0` result is only a policy counterfactual.
2. Whether protein-family shift, span length, or annotation practices causes
   the remaining TE64/CAID3 misranking is not identified. It requires
   homology-grouped, annotation-matched evaluation with enough proteins in
   each stratum; retrospective CAID3 stratification is descriptive only.
3. The CAID3 labels are public, and all 31 CAID3 proteins occur in the local
   DisProt 2026_06 extract. That extract cannot be used as training data and
   then called an independent CAID3 test.

**Next research decision:** construct and freeze a CAID-compatible training
and development source with verified `0`, `1`, and `unknown` semantics,
homology-separated proteins, and true no-linker negatives. Then compare the
same frozen model families on masked and full-sequence endpoints without
touching CAID3 for selection. Do not train on the `x`-as-`0` diagnostic labels.

## Reproducible evidence

- `reports/dfl_mask_policy_counterfactual_v2_2026-10-12.json` and
  `scripts/audit_dfl_mask_policy_counterfactual.py`: exact masked/full and
  positive-protein interventions; source and checkpoint SHA-256 values are in
  the JSON.
- `reports/dfl_inference_consistency_2026-10-12.json` and
  `scripts/diagnose_dfl_inference_consistency.py`: one-at-a-time versus padded
  batch check.
- `reports/dfl_source_shift_audit_2026-10-12.json`: source counts and label
  distributions.
- `reports/dfl_caid3_common_retrospective_2026-10-12.json`: equal-position
  public competitor comparison.
- CAID3 reference and assessment:
  <https://pmc.ncbi.nlm.nih.gov/articles/PMC12750029/>; official evaluation
  code: <https://github.com/BioComputingUP/CAID>.
