# DFL detector comparison: SAM-like, YOLO-style, and released predictors

**Verdict: the SAM-like TE82 score is not a breakthrough.** It transfers very
poorly to public CAID3. The 0.65–0.69 average precision (APS) was obtained by
selecting epochs on TE82 *development* proteins; it cannot be compared with a
score from a different benchmark. The inference-path parity check reproduced
the stored TE82 SAM APS to six decimals, so the low CAID3 scores are not
explained by using the wrong semantic output head.

## Frozen same-target comparison

The CAID3 Linker **common 27-protein subset** contains 15,570 residues and
1,214 positives. Each row below scored every residue on those same sequences.
Published systems are their released CAID3 score submissions; local systems
use TE82-selected frozen checkpoints. No CAID3 score or threshold selected a
checkpoint. APS, AUROC and Fmax were calculated by one evaluator on identical
reference labels. Full per-seed numbers and hashes are in
`reports/dfl_yolo_sam_public_retrospective_2026-10-13.json`.

| Predictor | CAID3 common-27 APS | AUROC | Fmax | Status |
| --- | ---: | ---: | ---: | --- |
| IPA-AF2-Linker | **0.482** | 0.898 | 0.491 | Released submission |
| LINKER-Pred-Lite | 0.429 | 0.872 | 0.473 | Released submission |
| DisoFLAG-DFL | 0.409 | 0.846 | 0.464 | Released submission |
| LINKER-Pred | 0.398 | 0.884 | 0.468 | Released submission |
| LINKER-Pred2 | 0.386 | 0.889 | 0.464 | Released submission |
| APOD | 0.369 | 0.852 | 0.437 | Released submission |
| YOLO-style width 128, 3-seed mean | 0.145 | 0.620 | 0.228 | Local retrospective |
| YOLO-style width 256, 3-seed mean | 0.122 | 0.608 | 0.205 | Local retrospective |
| DFLpred | 0.097 | 0.491 | 0.147 | Released submission |
| Prior LinkerForge CNN, seed 7 | 0.089 | 0.542 | 0.165 | Local retrospective |
| SAM-like query head, 3-seed mean | **0.076** | 0.509 | 0.158 | Local retrospective |

The SAM-like seed APS values are **0.073, 0.074, 0.081** (AUROC
0.495, 0.497, 0.535). Its mean APS is roughly the 7.8% positive-residue
prevalence of this subset and far below LINKER-Pred2 and IPA-AF2-Linker.
YOLO-style seed APS values are 0.166/0.155/0.114 for width 128 and
0.125/0.122/0.121 for width 256. Their best single seeds remain far below
the competitive released models. The seven released submissions were checked
against the earlier archived evaluation before adding local models.

The [CAID3 paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12750029/)
reports different **full-coverage** values (for example IPA-AF2-Linker APS
0.474 at 90.3% coverage and LINKER-Pred2 APS 0.365 at full coverage). They
must not be interchanged with the common-27 values above. A newer model such
as IDPFunNet is **not** in the seven obtained released-score archives; this
table is a matched comparison with available CAID3 submissions, not a census
of every model published through October 2026.

## Secondary published TE64 diagnostic

TE64 contains 64 proteins, 10,256 scored known residues, and 949 positives;
`x` positions are excluded. The SAM-like three-seed mean APS is **0.289**
(0.293/0.296/0.279), above the prior LinkerForge CNN's 0.214. YOLO width 128
averages 0.233, and width 256 averages 0.258. This shows *some* transfer
within the historical TransDFL source family, but there is no reproduced
original TransDFL checkpoint score in this local TE64 comparison. TE64 was
previously viewed and is not a fresh blind test.

## Higher-dimensional YOLO ablation

Only trainable-head width and mask-prototype count changed: **128/16 →
256/32**. Frozen ESM-2 35M embeddings, TR166/TE82 files, loss, optimizer,
windowing and six-epoch limit stayed fixed. Three-seed mean best-epoch TE82
APS rose only from **0.502 to 0.520**; it missed the preregistered +0.03
threshold, and CAID3 mean APS fell from **0.145 to 0.122**. Per-seed wider
TE82 APS was 0.608/0.496/0.455. The larger head is **discarded**, not
promoted. Each isolated run retained seed, source/data/config hashes,
versions, checkpoint, runtime, and failure status.

## What remains unproven

- CAID3 and TE64 are public, previously viewed diagnostics. TR166 remote
  homology/source overlap with them is not certified absent, so neither is a
  prospective independent claim.
- CAID3's positive-only proteins cannot establish no-linker specificity.
- Released models used different training corpora and sometimes different
  input modalities. This is a **same-target deployed-score** comparison, not
  an equal-training-data architecture comparison.
- The present scores evaluate residues, not segmentation boundary quality or
  calibrated abstention. Region IoU, start/end errors, and an adjudicated
  negative-protein set are still required.
- The cause of the severe SAM TE82→CAID3 drop has **not** been isolated. Label
  or source shift is plausible, but is not a proved causal explanation.

Next: audit the source/annotation shift and family overlap; implement a
prospective independent DFL test with negative proteins; and compare the
frozen models and obtainable current baselines on that common set. Do not
retune on CAID3 to rescue the score.
