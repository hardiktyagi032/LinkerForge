---
name: linkerforge-autoresearch
description: Plan and run bounded, reproducible LinkerForge linker-detector experiments using Karpathy-style propose-train-evaluate-keep/discard loops. Use for autonomous or repeated model-improvement trials, not ordinary one-off training or the downstream fusion-ranker without a separate contract.
---

# LinkerForge autoresearch

This is a LinkerForge adaptation of [Andrej Karpathy's autoresearch](https://github.com/karpathy/autoresearch), **not** an official skill published by Karpathy. His original `program.md` and README define a small editable surface, immutable evaluation, fixed compute budget, and an experiment ledger. They target GPT pretraining and validation bits per byte; this skill targets LinkerForge's DLD linker-residue detector and must not copy that benchmark's metric or dataset.

Before changing this repository, read its `README.md` completely and follow `AGENTS.md`. Inspect current Git status and preserve all pre-existing work. Never use `git reset --hard`, `git checkout --`, or an automatic commit/revert loop in this shared checkout. Use isolated branches/worktrees or separate output directories for experiments; restore only files created or changed by this experiment after checking ownership.

## Establish the experiment contract

Agree on the editable model/strategy surface, immutable data and split hashes, baseline checkpoint, GPU/time budget, maximum number of trials, stop conditions, and output directory. Do not assume that a request to install or inspect this skill authorizes training. Start trials only when the user requests execution. Check for an existing GPU job before launching another.

For the current DLD detector, folds 1–3 are training and fold 4 is development. Fold 5 has already been viewed in earlier LinkerForge work and is **not** a fresh blind model-selection set. Freeze preprocessing, baseline comparisons, and evaluation code before the first trial. Do not derive model inputs from target labels. Maintain separate provenance for natural annotations, synthetic negatives, predictions, and experimental observations.

Primary decision metric is maximum residue recall at empirical precision >= 0.90 with at least 50 true-positive residues, with score ties handled intact. Guard against more than 0.02 absolute loss in no-linker-protein specificity. Record AUPRC, region-level metrics, runtime, GPU memory, seeds, and raw TP/FP/FN as secondary evidence. If a proposed change requires a new dataset or label semantics, audit and version that data first; do not compare incompatible runs as a model-only improvement.

## Bounded loop

1. Reproduce and record the baseline under the frozen contract.
2. Propose one mechanism and cite its supporting paper or diagnostic evidence. Record the hypothesis and expected failure mode before training.
3. Run one bounded, checkpointed trial. Save exact config, source/data hashes, software versions, model revision, GPU, seed, logs, and failures.
4. Compare only on development data with the frozen metric and guardrails. Mark the result `promising`, `negative`, `inconclusive`, or `invalid`; never auto-promote a tiny single-seed gain.
5. Repeat promising changes with multiple seeds and matched compute. Hybridize only independently useful mechanisms, then compare hybrid against each component.
6. Stop at the agreed trial/time/compute limit, on repeated infrastructure failure, or when evaluation integrity is compromised. Summarize all trials including failures and limitations. Never claim an experimental or independent-blind result from development metrics.

Prefer the data-and-span hypothesis in `literature/BREAKTHROUGH_STRATEGY.md` over undirected loss sweeps when its source-label gates pass. The project-specific comparison contract is in `literature/TRANSFER_EXPERIMENT_PROTOCOL.md`. The user's scientific goal and repository instructions override this skill.
