# Promptable linker segmentation: preregistered exploratory trial

This trial adapts the *architecture pattern*, not weights or claimed performance,
of the supplied **SAM 3: Segment Anything with Concepts** paper. A protein
sequence replaces an image; DFL/IDL/DDL ontology IDs replace visual concept
prompts; learned span queries output linker start/end positions and a residue
mask. A separate presence head asks whether the target concept occurs.
Optional positive/negative exemplar prompts are implemented but **disabled in
the fair no-exemplar comparison**.

## What is being compared

- Primary scientific target here: **DFL**, a disordered flexible linker span
  under the original published TransDFL `0`/`1`/`x` label convention. `x` is
  unknown and excluded from loss and evaluation. DLD IDL/DDL labels are a
  different ontology and are not mixed into this trial.
- Frozen encoder: `facebook/esm2_t12_35M_UR50D`, identical to the project's
  original masked-residue CNN baseline. Only the new segmentation head trains.
- Frozen source files: `TR166` train hash
  `8fbfa1a503857131b8e485f511f5c84d9fbea24b9d5bbac2aa003508cb4f716c`;
  `TE82` development hash
  `f15ac3eef1edc45b95bc600d661dab348a0cb0bee11e47febeac356ef93db916`.
  Window width is 510 residues, as in the baseline. No CAID3 or TE64 labels
  are read by the training script.
- Primary exploratory selection metric: masked-residue average precision
  (APS) on TE82, from the semantic residue head. Secondary: AUROC, counts,
  maximum recall at empirical precision >=0.90 with >=50 true positives,
  and no-positive-protein specificity at that threshold. These are computed
  with the same baseline evaluator convention.
- Run: seed 7, at most six epochs, two hours, batch size two (not the
  baseline's batch four), one GPU job. This is **not** an equal compute or
  equal optimization comparison, only a same-encoder/same-split pilot.
- The original published CAID3 27-protein released-score comparison remains
  the external *retrospective* reference in
  `reports/DFL_FAIR_COMPARISON_2026-10-12.md`; it cannot be used for
  hyperparameter selection. TE64 has also been viewed and is not fresh blind.

## Supervision and limits

The head has semantic-residue, presence, query-match, start, end, and instance
mask losses. Complete internal positive spans from published labels supervise
span queries. Crucially, absence is **not** trained from mere lack of a positive
annotation: the original masks do not certify exhaustive no-linker negatives.
Consequently, the presence/abstention output is an uncalibrated research
prototype and cannot yet be advertised as a reliable no-linker detector.
The standalone inference decoder emits one-based inclusive coordinates,
peptide sequence, and composition counts, but it has not passed a biological
external validation.

## Promotion gate

No frontier, breakthrough, or publishable superiority claim follows from a
TE82 win. Next: compare the finished pilot to CNN and span heads on TE82 with
raw counts and uncertainty; audit homology/source overlap; obtain genuinely
adjudicated negative proteins; then freeze model/threshold before a new
prospective, independent test and matched released competitor runs. If the
new head loses on TE82, retain the negative result and diagnose, not retune on
CAID3/TE64. Every trial records hashes, versions, seed, GPU, runtime, VRAM,
and failure reason in its isolated manifest.
