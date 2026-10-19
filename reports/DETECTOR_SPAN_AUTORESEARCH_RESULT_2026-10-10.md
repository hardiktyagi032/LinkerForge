# Bounded DLD span-supervision autoresearch: completed round

Status: **three trials complete; no model promoted**. Scope is the natural-protein
linker residue identifier, not the fusion-linker ranker. All results below use
DLD folds 1–3 for training and fold 4 for development. Fold 5 was previously
viewed and was not used for model choice. There is no independent blind result.

## Frozen decision

Primary: maximum fold-4 residue recall at empirical precision at least 0.90,
with at least 50 true-positive residues and exact score ties. Guardrail:
no-linker-protein specificity may decline at most 0.02 absolute from the
weighted-BCE reference. Secondary: AUPRC, region matching at IoU >=0.5,
boundary errors, runtime, memory, and raw counts.

All three new trials used the same frozen ESM-2 35M revision, DLD data hashes,
seed 7, train/validation split, optimizer, 10 epochs, and CNN width. The one
changed variable was the weight of auxiliary start/end boundary supervision.
The start/end head supplies training supervision; current inference still
thresholds the residue head and does **not** use a CRF or constrained decoder.
This is an adaptation motivated by [structured sequence labeling](https://aclanthology.org/P16-1101/)
and [segment-level modeling](https://papers.nips.cc/paper_files/paper/2004/hash/eb06b9db06012a7a4179b8f3cb5384d3-Abstract.html),
not a reproduction of either paper.

| Model | Boundary weight | TP / 6,205 | Precision | Recall | No-linker specificity | IoU-0.5 matched / 477 | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Prior weighted-BCE reference | 0 | 475 | 0.9013 | 0.07655 | 0.97163 | 55 | Frozen reference |
| Prior asymmetric focusing | n/a | 525 | 0.9005 | 0.08461 | 0.96454 | 60 | Prior single-seed comparator |
| Trial 1 | 0.25 | 532 | 0.9032 | 0.08574 | 0.93617 | 60 | Reject: guardrail loss 0.03546 |
| Trial 2 | 0.05 | 472 | 0.9042 | 0.07607 | 0.96454 | 57 | Reject: recall below reference |
| Trial 3 | 0.10 | 479 | 0.9004 | 0.07720 | 0.97163 | 56 | Inconclusive: four-TP gain, below prior asymmetric |

The three run manifests and `epochs.jsonl` files are in the isolated
`artifacts/span-boundary-*-35m-seed7-00*` directories; the exact run IDs,
checkpoint hashes, and cumulative wall-clock GPU time are in
`reports/detector_autoresearch_ledger_2026-10-10.json`. Cumulative time was
0.695 GPU-hours by wall clock, within the six-hour cap. Peak allocated PyTorch
VRAM in each manifest is about 241 MB; this excludes the frozen backbone and
other allocations, so it is not total device usage.

The third trial's apparent gain is too small for a single-seed, single-fold
claim. No three-seed confirmation was justified under the prespecified
promotion rule. The source-code subtype head remains gated on verifying the
meaning of DLD code 0, and rigid/flexible/cleavable labels were not trained.
The present binary identifier and FASTA-to-interval/composition adapter remain
available, but predicted intervals are not experimentally verified linkers.

## Next scientific decision, outside this bounded round

Review raw DLD label semantics and high-scoring loop/terminus false positives,
then design a *new*, separately approved experiment that uses verified source
classes or a true constrained span decoder. Repeatedly tuning boundary-loss
weights on fold 4 is unlikely to produce a defensible result. A new
homology-audited evaluation source is needed before any generalization claim.
