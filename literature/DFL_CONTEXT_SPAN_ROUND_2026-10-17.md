# Next DFL context-and-span round — preregistration

Status: proposed, **no training launched**. The preceding bounded-span round is complete and negative; see `reports/DFL_BOUNDED_SPAN_ROUND_2026-10-16.md`.

## Evidence and hypothesis

On the CAID3-sequence-screened TR166/TE82 data, the best seed-7 192-residue coupled span head reached development APS .496, while matched seed-7 SAM-like direct reached .791. The longer span limit recovered representational capacity for all observed full-label positive spans, but not the performance gap. The bounded head has only local width-5 convolutions and segment pooling; the SAM-like head has global self-attention. Hypothesis: global contextualization before interval scoring may improve ranking of linker residues and whole intervals. This is an inference from architectural differences, **not** a proven explanation or novelty claim. Expected failure modes: overfitting 79 screened training proteins, weak span calibration, compute inflation, and continuing domain shift.

## Frozen comparison contract

- Use only `data/processed/caid3_protected_dfl_v1` for train/development/auxiliary; run `scripts/preflight_caid3_protected_training.py` immediately before each job and fail on any hash or blacklist mismatch. Never use CAID3 labels to filter or tune.
- Match frozen ESM-2 35M embeddings, windows, optimizer, data, and APS-based development selection. Compare against the completed screened SAM-like direct and disorder-transfer baselines, and report unequal compute explicitly. If compute matching is not achieved, do not attribute a difference solely to architecture.
- First trial: one global-context-plus-span head at seed 7, with unknown labels masked and max span at least 192. Keep the local span head and SAM baseline as separate controls; no arbitrary loss sweeps.
- Record masked development APS as primary, plus AUROC, Fmax over exact ties, recall at empirical precision at least .90 with at least 50 TP, interval IoU-0.5 precision/recall and boundary error, coverage, runtime, VRAM, hashes, and failures. Repeat at seeds 17 and 31 only if the first result is promising or genuinely ambiguous.
- One local 6GB GPU job at a time; at most three architecture variants and six GPU-hours in this documented round. Use isolated bounded jobs, no automatic promotion or overwrites.

CAID3 common-27 APS/AUC-ROC/Fmax is a **one-time, locked retrospective comparison only after checkpoint selection is frozen**, not a development loop. A genuinely untouched homology-audited test with no-linker negatives remains required for a publishable superiority claim.
