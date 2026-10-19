# LinkerForge autoresearch program — detector track

This is the project-specific application of the locally installed
`linkerforge-autoresearch` Codex skill, adapted from
[Karpathy's autoresearch](https://github.com/karpathy/autoresearch). It is not
Karpathy's GPT-training program and does not use `val_bpb`.

## Frozen comparison contract

- Task: identify DLD interdomain-linker residues, not predict experimental
  success or rank engineered fusion linkers.
- Development data: DLD folds 1–3 for training, fold 4 for validation. Fold 5
  is not an untouched model-selection set in this project.
- Reference: frozen ESM-2 35M + residue CNN with weighted BCE. The 8M model
  is a cheap screening reference, never evidence that a strategy beats 35M.
- Primary decision: maximize recall at empirical precision >= 0.90, with at
  least 50 true-positive residues and exact score ties; reject a change if
  no-linker-protein specificity falls >0.02 absolute.
- Secondary evidence: validation AUPRC, region metrics once implemented,
  runtime, VRAM, and multi-seed variation. Do not equate the highest
  validation AUPRC with a validated scientific winner.
- All runs require source and validation hashes, model revision, seed,
  software versions, config, logs, and checkpoint. No tuning on fold 5.

## Active bounded round

Three 8M loss variants completed: asymmetric focusing, weighted BCE plus
Tversky, and online hard-negative mining. The original automated 35M gate
required an 8M validation-AUPRC gain of >=0.01; none cleared it. This was
only a compute-screening gate and missed a signal in the primary metric.

Checkpoint-level scoring found that 8M weighted BCE recovered 270/6205
linker residues (recall 0.043513, precision 0.9000), whereas asymmetric
focusing recovered 371/6205 (recall 0.059790, precision 0.900485). Both
had no-linker-protein specificity 0.957447. AUPRC was nearly tied (0.275220
versus 0.275511). A matched 35M asymmetric confirmation in
`artifacts/transfer-35m-asymmetric-highprecision-run-001` completed with
recall 0.084609 at precision 0.900515 and no-linker specificity 0.964539,
versus the 35M weighted-BCE reference recall 0.076551 at precision 0.901328
and specificity 0.971631. The 35M focal comparison was worse on recall
(0.063820) and is not promoted. A fixed equal-weight two-head ensemble
reached recall 0.086060, but its small gain over asymmetric alone may not
justify doubled inference. See `reports/DETECTOR_RECALL_VALIDATION_2026-10-09.md`
for exact counts and checkpoint hashes. These are fold-4, single-seed
results, not an independent improvement claim.

The highest-priority subsequent mechanism is the source-code/segment study
in [BREAKTHROUGH_STRATEGY.md](./BREAKTHROUGH_STRATEGY.md): verify raw DLD
annotation semantics, preserve them in versioned records, test an auxiliary
source-class head and a span-aware decoder separately, then hybridize only if
both help. This round does not begin until raw-code semantics and provenance
pass their gates, and it must not compete with any active GPU job.

Stop after this bounded round and its validation comparison. Additional
unattended trials require an explicit run budget and a durable job runner;
the current Windows scheduled-task registration was denied.

## New bounded identifier round (10 October 2026)

The user approved **three new architecture trials / six aggregate GPU-hours**.
The existing Codex hourly heartbeat is now assigned to the natural-protein
identifier rather than the fusion-linker ranker. Its frozen configuration is
`configs/detector_autoresearch_round_2026-10-10.json` and its cumulative
ledger is `reports/detector_autoresearch_ledger_2026-10-10.json`. It must
check the ledger and running GPU jobs before every trial. No new architecture
trial has been run at the time of this update.

The immediate software baseline is a FASTA-to-interval/composition adapter,
`scripts/identify_natural_linker.py`, plus an IoU-0.5 region evaluator.
Fold-4 region diagnostics for the pre-existing weighted-BCE and asymmetric
heads are in `reports/DETECTOR_AUTORESEARCH_ROUND_2026-10-10.md`.
The first new mechanism is span-aware supervision/decoding. The source-class
auxiliary head remains gated until DLD code `0` semantics are documented.
DisProt 2026_06 has 460 explicit flexible-linker annotations, but its
relationship to DLD is not homology-audited; it is not an independent test.

### Completed identifier round

The user-approved three-trial span-supervision round completed on 10 October
2026. No checkpoint met a material-improvement standard. The full comparison,
including the trial that violated the no-linker specificity guardrail, is in
`reports/DETECTOR_SPAN_AUTORESEARCH_RESULT_2026-10-10.md` and the machine-readable
ledger. Do not launch additional trials under this exhausted three-trial cap.
