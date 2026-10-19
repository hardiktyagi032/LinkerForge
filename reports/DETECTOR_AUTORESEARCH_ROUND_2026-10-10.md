# Natural-protein linker identifier: bounded autoresearch round

Status: **configured; no new architecture trial has been trained in this round**.
User-approved limit: three new architecture trials or six aggregate GPU-hours,
whichever comes first. The existing hourly `linkerforge-bounded-autoresearch`
automation now targets this detector, not the independent-domain fusion-linker
ranker. Do not launch a second competing training loop.

## Task and frozen decision rule

Input: one natural protein amino-acid sequence. Output: predicted linker
presence, 1-based inclusive start/end intervals, peptide sequence, amino-acid
counts/fractions, and confidence scores. The current inference adapter is
`scripts/identify_natural_linker.py`. It does not identify or certify the
flanking domains. An external domain annotation and coordinate mapping are
needed before calling them Domain A and Domain B.

DLD source folds 1–3 are training; fold 4 is development. Fold 5 has been
examined in earlier work and is not a fresh blind model-selection set.
Select maximum residue recall at empirical precision at least 0.90, with at
least 50 true positives and exact score ties. No-linker-protein specificity
may drop by at most 0.02 absolute from the matched reference. Record AUPRC,
region precision/recall at interval IoU >=0.5, matched start/end MAE, raw
TP/FP/FN, runtime, peak VRAM, hashes, and seeds. The code for the region
diagnostic is `src/linkerforge/detector/evaluation.py`.

Training SHA-256: `c43952c4f943f458ba61905c34a59e04fadca5607b95d6afc9bd9d1475252c41`.
Validation SHA-256: `290992af4a93c14ba007197c282367734af8ec878783d5e668ee4960128a3461`.
Frozen ESM-2 35M revision: `6fbf070e65b0b7291e7bbcd451118c216cff79d8`.
The full bounded config is `configs/detector_autoresearch_round_2026-10-10.json`.

## Existing evidence, not new trials

The weighted-BCE reference has fold-4 recall 475/6205 (0.076551) at 0.901328
precision; asymmetric focusing has 525/6205 (0.084609) at 0.900515 precision.
Both are single-seed development results. See
`reports/DETECTOR_RECALL_VALIDATION_2026-10-09.md`; do not call this an
independent improvement.

The newly frozen region evaluator was run on the weighted-BCE fold-4
checkpoint: 477 labelled contiguous linker regions, 101 predicted regions,
55 one-to-one matches at IoU >=0.5 (region precision 0.5446, recall 0.1153)
at its validation-selected residue threshold 0.994590. This is a
post-hoc diagnostic on the development fold, not a fresh held-out result.
The same evaluator on the pre-existing asymmetric checkpoint found 109
predicted regions and 60 matches out of 477 (precision 0.5505, recall
0.1258) at its own validation-selected residue threshold 0.975398. This
is a five-region increase, not a new architecture trial or independent claim.

The CLI was smoke-tested with a DisProt sequence fragment. It produced a
schema-versioned, provenance-bearing `no call` result at the existing
high-precision threshold. That result is a software smoke test, not a
biological true-negative evaluation.

## Gate and trial ledger

| Trial | Mechanism | Status | GPU-hours counted | Decision |
| --- | --- | --- | ---: | --- |
| 0 | Existing weighted-BCE / asymmetric baselines | pre-existing | 0 | reference only |
| 1 | Span-aware boundary supervision/decoding | proposed | 0 | needs frozen implementation and baseline region score |
| 2 | Verified source-code auxiliary classes | gated | 0 | code 0 source semantics not established |
| 3 | Hybrid of independently useful mechanisms | gated | 0 | only if separate ablations help |

DisProt 2026_06 supplies 460 explicit flexible-linker annotations (360
proteins), separate from the 291 weak disorder-gap screen records. An exact
sequence/containment screen found 64 overlaps with DLD. These data are not a
fresh external test until homology, coordinate, and domain-pair audits pass.
The DLD paper itself used an earlier DisProt release, increasing the need for
an overlap audit.

Before training: check no competing GPU job, validate hashes, freeze region
scoring and boundary tolerance, verify source-code semantics for any
source-class head, and create a unique run directory with a manifest.
Repeat promising variants with seeds 7, 17, and 29 within the remaining
budget. Report negative and failed runs; do not auto-promote or push weights.
