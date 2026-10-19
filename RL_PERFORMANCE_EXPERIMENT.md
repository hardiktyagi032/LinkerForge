# RL performance experiment for linker identification

## Question

Does policy-gradient fine-tuning of our already trained residue head improve
the precision–recall trade-off beyond the same amount of continued supervised
training? In particular, can it increase **validation recall at ≥90% residue
precision**, with at least 50 true-positive residues, while preserving or
improving average precision?

This is an **experiment**, not an adopted LinkerForge architecture or a claim
that reinforcement learning is inherently better. A confidence-threshold
bandit would only move along an existing precision–recall curve and cannot
improve the underlying ranking. Here RL actually changes the residue-head
weights. The reward is a non-differentiable per-window F0.5 score, so it
emphasizes precision; a supervised BCE anchor prevents immediate policy
collapse. The alternative arm has identical training examples, base weights,
batch order, learning rate and number of updates, but no policy-gradient term.

## Method and decision rule

1. Load the frozen ESM-2 35M backbone and the validation-selected DLD head.
2. Use DLD folds 1–3 **only** for head updates; leave the backbone frozen.
3. Train one matched supervised continuation arm and one hybrid RL arm.
4. In the RL arm, sample linker/non-linker actions per residue. Compare each
   sample's F0.5 reward with the greedy prediction reward and apply a
   self-critical REINFORCE gradient, alongside the identical BCE objective.
5. Evaluate each arm on DLD fold 4 using residue AUPRC and recall at ≥90%
   precision, requiring at least 50 true positives. Compare with the unchanged
   base checkpoint.
6. Treat all results as exploratory. Fold 4 was already used to select the
   base checkpoint. DLD fold 5 has already been examined and is **not** used
   for this experiment. A new, homology-audited independent set is needed for
   any performance-gain claim.

The run script is `scripts/experiment_rl_linker_head.py`; its record contract
is `schemas/rl-linker-head-experiment.schema.json`. The actual metrics belong
in the generated ignored `artifacts/rl-head-experiment-001/report.json`.
Do not write a positive result into a paper unless the RL arm beats the
matched supervised arm on a fresh test set with uncertainty intervals.

## One-epoch exploratory result (9 October 2026)

The completed local run is in ignored
`artifacts/rl-head-experiment-001/report.json`. It used one matched epoch
per arm, learning rate `1e-5`, policy-gradient weight `0.25`, and the same
frozen ESM-2 35M backbone. At the validation-only ≥90%-precision operating
point:

| Arm | AUPRC | Precision | Recall | TP | FP |
| --- | ---: | ---: | ---: | ---: | ---: |
| Unchanged base | 0.39980 | 0.9013 | 0.0766 | 475 | 52 |
| Continued supervised BCE | 0.39917 | 0.9002 | 0.0756 | 469 | 52 |
| BCE + self-critical RL | 0.39920 | 0.9004 | 0.0757 | 470 | 52 |

The RL arm added **one** true-positive residue over the equal-compute
supervised control and recovered **five fewer** than the unchanged base.
This is not a meaningful gain; the RL checkpoint is experimental and must
not replace the base checkpoint. Changing the reward, RL weight, or number
of epochs after seeing these validation metrics would be another exploratory
experiment, not confirmation. A stronger domain-context model and better
labels may be a more promising performance route.

## Why this objective is plausible but risky

Policy gradients can optimize discrete, non-differentiable sequence-level
rewards: see Williams' original
[REINFORCE](https://doi.org/10.1007/BF00992696) and
[self-critical sequence training](https://arxiv.org/abs/1612.00563).
[Sequence labeling via reinforcement learning](https://pmc.ncbi.nlm.nih.gov/articles/PMC11604619/)
specifically discusses the mismatch between token-level training losses and
task metrics such as F1. None of those papers demonstrates that RL improves
protein-linker detection. Sparse positives, noisy annotations, correlated
residues, and high-variance gradients may make RL worse than supervised
training. The matched arm is therefore part of the specification, not an
optional extra.

The biological distinction also matters: linker predictors can mistake
other disordered residues for linkers. That failure mode is documented in the
[CAID2 disordered-linker assessment](https://pmc.ncbi.nlm.nih.gov/articles/PMC10968229/).
If RL changes only the threshold or suppresses almost every prediction, it
has not solved this distinction. Report precision, recall, AUPRC, raw TP/FP,
coverage, and family-level uncertainty together.
