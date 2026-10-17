# SAM-like DFL segmenter: bounded exploratory round

**Status:** Three trials completed; promising development-set improvement, **no
frontier or generalization claim**. All trials used the original published
TR166 train and TE82 development split, frozen ESM-2 35M backbone, six epochs,
batch size two, and no positive/negative exemplar prompt. CAID3 and TE64 were
not read or used for checkpoint selection in this round. The complete
per-epoch metrics and immutable trial parameters are in each isolated artifact.

| Head / seed | Best TE82 epoch | Masked-residue APS | AUROC | Recall at empirical precision >=0.90 | TP / FP | No-positive-protein specificity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Existing CNN, seed 7 | previously selected | 0.450 | not restated here | not restated here | — | — |
| Existing span head, seed 7 | previously selected | 0.455 | not restated here | not restated here | — | — |
| New query segmenter, seed 7 | 3 | 0.661 | 0.875 | 0.360 | 801 / 88 | 0.955 |
| New query segmenter, seed 17 | 2 | 0.653 | 0.855 | 0.380 | 844 / 91 | 0.886 |
| New query segmenter, seed 31 | 2 | 0.688 | 0.872 | 0.385 | 855 / 92 | 0.977 |

All new-head rows score **13,694 known TE82 residues**, with **2,223
positives** and **11,471 negatives**. Best-epoch APS ranges 0.653–0.688,
mean 0.667. This is a clear *within-TE82* gain over the earlier 0.450 CNN,
but not a controlled equal-compute architecture win: the batch size, model
capacity, loss, and optimization differ. The best epoch was selected on TE82.
Across all three seeds, later epochs fell materially, so training stability
and overfitting require investigation.

The no-positive-protein specificity column is a **proxy** computed from
proteins lacking a `1` in their published masks, not a certified specificity
on exhaustively reviewed linker-absent proteins. The presence and abstention
head lacks true-negative supervision and must not be presented as validated.
The high-precision threshold is selected on the same TE82 development set.
No independent region-level or start/end-boundary result has yet been measured.

## External baseline reality check

The earlier same-target 27-protein CAID3 retrospective comparison found
IPA-AF2-Linker APS **0.482** and LINKER-Pred2 APS **0.386**, while the old
LinkerForge CNN scored **0.089** there. These numbers are on **CAID3**, not
TE82, so they must **not** be numerically compared to the new 0.653–0.688
TE82 values. The old heads' large TE82-to-CAID3/TE64 drop is the concrete
reason to demand contamination-audited transfer evidence before any
"world-class" assertion. CAID3 and TE64 have been viewed; they are
retrospective diagnostic sets, not fresh blind sets.

## Reproducibility and next gates

- Code: `src/linkerforge/models/promptable_linker_segmenter.py`,
  `scripts/train_dfl_promptable_segmenter.py`, unit tests in
  `tests/test_promptable_linker_segmenter.py`.
- Per-trial manifests, epochs, checkpoint, hashes, versions, runtime, and
  peak PyTorch VRAM: `artifacts/samlike-dfl-seed{7,17,31}-001/`.
- Next scientific step is **not** to retune on public CAID3: reproduce the
  same frozen checkpoint evaluation on TE64/CAID3 once for retrospective
  transfer, with all scores and coverage, then conduct a sequence-family and
  annotation overlap audit and acquire untouched independent labeled data.
  A prospective matched comparison against obtainable competitor predictions
  is required for a frontier claim.
- Next model step is to diagnose the epoch-2/3 peak and later decline using
  train-versus-dev curves and ablations. Any new round must be documented
  before GPU work, use isolated outputs, and preserve negative results.
