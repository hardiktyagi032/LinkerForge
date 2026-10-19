# SAM-inspired DFL batch: historical in-progress checkpoint

This snapshot was superseded when all five trials finished and the three-seed repeats, freeze decision, and locked CAID3 comparison completed. For final results use `reports/DFL_SAM_REPEAT_AND_LOCKED_CAID3_2026-10-17.md`; do not interpret the two-run table below as the final batch outcome.

Status at 2026-10-16 19:32 UTC: round 1 is running. Two of five queued seed-7 trials have finished; `multiscale_features` is running. The sequential launcher is alive, and no second GPU job was started. Round 2 contains the two fixed combination trials and has not started.

All values below are on the CAID3-protected filtered **development** split, not CAID3. Training uses the same frozen dataset, encoder, scoring, and candidate coverage as the matched SAM-like disorder-transfer baseline. These are single-seed exploratory results, not a claim of generalization or state of the art.

| Model (seed 7) | APS | AUROC | Recall at empirical precision >=0.90 | TP / FP | Region recall at IoU 0.5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Matched SAM-like baseline | 0.801196 | 0.909673 | 0.570639 | — | 9/28 |
| Boundary refinement | 0.808401 | 0.911801 | 0.580900 | 736 / 81 | 9/28 |
| Query-local attention | 0.798869 | 0.908807 | 0.564325 | 715 / 78 | 8/28 |

The boundary variant's APS difference from the matched seed-7 baseline is +0.007205 and its recall difference is +0.010261. Region recall is unchanged. The local-attention variant trails the baseline. These differences do not establish a robust improvement; remaining variants, repeat seeds, Fmax, and a frozen model-selection decision are pending. No CAID3 benchmark has been run on this batch.

Round 1 ledger: `artifacts/dfl-sam-ideas-batch-2026-10-17/round1-ledger.json`. The ledger records source/config/data hashes, statuses, times, and raw development metrics. The batch is split into rounds of three and two variants to preserve the per-round architecture cap; it is not five concurrent GPU jobs.
