# Continuous detector autoresearch operating contract

The user authorized ongoing local GPU research on the **natural-protein linker
identifier**, with no overall trial or hour cap. This does not waive scientific
controls. Each round has at most three architecture trials and six GPU-hours;
each job has its own time limit. A new round is opened only after the previous
round's ledger and report are complete. Never repeat the exhausted 10 October
boundary-loss sweep as if it were a new hypothesis.

## Anti-stall state machine

Every automation wake-up must perform and record **one state transition**:

1. If a recorded training process is active, inspect its process, manifest,
   logs, epoch progress, and GPU state. Do not start a competitor. If healthy,
   keep the state `running` and remain quiet.
2. If the process ended, reconcile its manifest and ledger, calculate the
   frozen primary metric/guardrail and region metrics, classify the trial as
   `promising`, `negative`, `inconclusive`, or `invalid`, and update `next_action`.
3. If a trial is ready and no training process is active, verify hashes and
   preflight, launch it in an isolated directory, record PID/log paths, and
   verify a manifest or explicit startup error before ending the wake-up.
4. If a method is gated (for example, DLD code 0 is undefined), **do not let
   that gate stall all research**. Work on a separate eligible method such as
   LoRA or a constrained interval decoder, or produce a concrete source audit.
5. If an infrastructure error repeats twice, stop that job, record the error,
   and switch to a safe validation task. Never report an unchanged gate as
   progress or start an uncontrolled retry loop.
6. If a round reaches its cap, write its comparison report and start a new
   bounded round under the ongoing user authorization, unless data integrity
   is compromised or the user asks to stop.

The automation is an hourly wake-up, **not** an operating-system service.
Training jobs are separate Windows processes with their own bounded runtime;
they can continue while this chat is closed, but cannot be guaranteed across
sleep, sign-out, reboot, or app unavailability. The next wake-up must detect
an interrupted process and resume or re-run only under a documented rule.

## Current round and hypothesis

`configs/detector_autoresearch_round_2026-10-11.json` freezes the first LoRA
round. The first trial tests whether task-adapting the existing ESM-2 35M
backbone improves high-precision recall versus frozen embeddings on identical
DLD folds. This is motivated by [Schmirler, Heinzinger, and Rost (Nature
Communications 2024)](https://doi.org/10.1038/s41467-024-51844-2) and
[McGuire et al. (PNAS 2024)](https://doi.org/10.1073/pnas.2405840121).
Those papers establish transferability as a hypothesis, not a LinkerForge
result. The first four-step GPU smoke test passed forward, backward, and an
optimizer step with PEFT 0.21.2 and Transformers 5.19.0; no validated LoRA
result exists at the time this file is written.

The source-class head remains gated: the [DLD portal](https://pcrgwd.ucd.ie/linker/download/)
defines labels 1–5 but does not define code 0. Never assume 0 means a trusted
negative or an unlabeled positive. DisProt 2026_06 is not an independent test
until overlap/homology and coordinate mapping audits pass. Fold 5 of DLD was
previously viewed and is not a new blind model-selection set.

## Selection and communication

Keep raw TP/FP/FN, empirical precision, recall, no-linker specificity,
residue AUPRC, IoU-0.5 region counts, boundary errors, runtime, VRAM, source
and data hashes, model revision, seed, and all failures. A single-seed fold-4
gain is not a generalization claim. Repeat only promising mechanisms across
three seeds within a round or in a documented continuation round. Never
auto-promote checkpoints, commit, push, or modify unrelated user work.
