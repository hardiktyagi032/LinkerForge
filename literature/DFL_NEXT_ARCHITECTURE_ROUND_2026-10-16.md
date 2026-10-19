# Next DFL architecture round — preregistration draft

Status: executed as the bounded-span round documented in `reports/DFL_BOUNDED_SPAN_ROUND_2026-10-16.md`; three development variants were negative. This file preserves the preregistration, not a result or novelty claim. The next candidate round is `literature/DFL_CONTEXT_SPAN_ROUND_2026-10-17.md`.

## Hypothesis

The current heads score residues and derive intervals afterward. A bounded semi-Markov segment scorer could improve recovery of whole flexible-linker spans by scoring candidate start, end, and interior jointly. The mechanism follows segmental sequence modelling (e.g. [Segmental Recurrent Neural Networks](https://arxiv.org/abs/1511.06018)); applying it here is an experimental adaptation, not an original invention. Expected failure modes are overlong predicted spans, poor calibration at high precision, and computational cost proportional to sequence length times maximum span length.

## Frozen comparison

- Primary task: DisProt-style disordered flexible linker (DFL), not DLD IDL/DDL.
- Train/development: use `data/processed/caid3_protected_dfl_v1/`, not the unfiltered TR166/TE82 files used by the earlier exploratory suite. Run `scripts/preflight_caid3_protected_training.py` immediately before every job. The filtered development set is not an untouched benchmark; TE64 and CAID3 remain protected from iterative selection.
- Baselines: rerun the strongest completed direct and disorder-transfer SAM-like/YOLO-1D arms on identical inputs. Preserve the frozen ESM-2 35M encoder, windowing, optimizer schedule, seeds, training examples, evaluation code, and output coverage where feasible. If a different compute budget is required, rerun all arms at that budget and label the comparison separately.
- Candidate architecture: bounded span scores from endpoint representations, pooled interior representation, span length embedding, and a no-span option. Use one globally decoded non-overlapping interval set, plus residue marginals or calibrated residue scores for the CAID-style measures. No gold domain boundary, full-protein structure, or target-derived feature may enter inference.
- Primary development selection: masked-residue APS on the filtered development set. Also record AUROC/Fmax, recall at empirical precision >=0.90 with at least 50 true-positive residues and exact score ties, IoU-0.5 region precision/recall, start/end error, protein false-positive rate on verified no-linker examples (if available), coverage, runtime, and peak VRAM. Compare only to baselines retrained on these same filtered files.
- First screen: one implementation smoke test and one seed against the matched strongest baseline. If feasible, repeat a promising or ambiguous result at seeds 7, 17, and 31. Never infer a reproducible gain from one seed.
- Round limit: at most three architecture variants and six local GPU-hours, one GPU job at a time. Isolate outputs and record config, source/data hashes, model revision, seeds, software versions, checkpoints, logs, failures, and raw counts.

## Decision and external gate

Mark each mechanism promising, negative, inconclusive, or invalid. A development improvement merely prioritizes a later frozen test. After model selection is frozen, perform one locked CAID3 common-27 retrospective comparison of APS, AUC-ROC, and Fmax against released predictions on the same residues; never use that result to choose the next architecture. Do not compare development numbers with published CAID scores. A genuinely independent frontier claim still requires an untouched common-target test with uncertainty, interval recovery, and no-linker specificity; see the active detector research charter and `literature/CAID3_PROTECTED_BENCHMARK_CONTRACT_2026-10-16.md`.
