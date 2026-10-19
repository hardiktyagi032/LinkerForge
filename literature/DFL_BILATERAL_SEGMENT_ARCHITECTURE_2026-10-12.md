# Proposal: Bilateral Connector Segmenter (BiCoS)

Status: **untrained hypothesis**, 12 October 2026. Primary task: predict
DisProt-style disordered flexible linker (DFL) intervals from one amino-acid
sequence. This is separate from the DLD structural IDL/DDL detector and the
fusion-linker ranker. No novelty or performance claim is made here.

## First-principles question

A linker is a *relationship* between regions, not merely an amino-acid
composition. A disordered tail, low-complexity insertion, and flexible
interdomain connector can look alike locally. A useful model must ask, for
each candidate interval `[i,j]`: (1) is the interval linker-like, (2) are
there credible different regions on both sides, (3) do its endpoints form
plausible transitions, and (4) is the whole interval more plausible than
nearby alternatives or no linker at all? The existing residue CNN scores
positions independently after local convolutions; its CAID3 transfer is poor.

## Input and modules

Sequence-only input; no MSA, structure, experimental domain annotation, or
native cross-domain geometry at inference. Use the already cached frozen
ESM-2 35M revision as the **controlled MVP encoder**, so any gain is due to
the decision architecture rather than a bigger feature model. A learned
amino-acid embedding encoder can be a separate later ablation, not conflated
with the span mechanism.

1. **Multiscale context.** For each residue, combine frozen contextual ESM-2
   vector with a small trainable local projection. Compute pooled summaries
   over 16-, 32-, and 64-residue neighborhoods. Respect mask and protein
   boundaries; never use target labels as model inputs.
2. **Candidate interval proposer.** Predict start and end logits from
   contextual residues. Retain the top `B` starts and ends and all lengths
   from 8 to 100 residues in a bounded window. During training include every
   positive reference interval, regardless of proposal score, to avoid
   proposal-recall leakage into loss. Freeze `B` and length limits before
   evaluation. Report proposal recall separately.
3. **Bilateral interval scorer.** For candidate `[i,j]`, pool its interior
   (mean, dispersion, and learned attention) and the independently pooled
   left and right flanks. Score their contrast and boundary transitions:

   `s(i,j) = MLP(interior, left, right, |left-right|, left-to-interior jump,
   interior-to-right jump, log length, simple sequence composition)`.

   The scorer may learn to down-rank disordered tails (missing a flank) and
   internal loops (flanks insufficiently distinct). Composition is an
   interpretable auxiliary input, never a proxy ground-truth label.
4. **Segment decoder.** Select non-overlapping intervals or the null/no-linker
   state by dynamic programming over bounded candidate spans. Return residue
   scores by marginalizing or maximum-score aggregation over intervals;
   retain start/end coordinates and rank. A final abstention threshold is
   calibrated **only** after verified no-linker proteins are available.

Bounded candidates make inference approximately `O(L*K)` rather than all
`O(L^2)` spans for sequence length `L` and maximum span length `K<=100`.
On the local 6 GB GPU, keep the ESM encoder frozen initially, score one
protein at a time, and checkpoint bounded jobs. Do not promise a specific
throughput before measuring it.

## Labels and loss

Preserve three states: curated positive `1`, verified negative `0`, and
unknown `x`. Unknown is **masked**, never converted to negative. Use
positive-span start/end supervision and interval likelihood on verified
positive spans; compare them against explicitly verified negative spans of
matched lengths when available. A residue auxiliary head keeps the exact
baseline endpoint. Where a protein has only positive intervals and unknown
elsewhere, train positive interval terms only; do not construct fake
negative contrastive pairs. No-linker calibration requires separately
adjudicated no-linker proteins. Positive-unlabeled loss is a later ablation
only if the class-prior and label-selection assumptions are audited.

Proposed total loss on eligible records:

`L = L_masked_residue + lambda_b L_boundary + lambda_s L_positive_span
     + lambda_r L_verified_pair_ranking`.

Each term, weight, source eligibility, and maximum region length is frozen in
the run config before development evaluation. The first experiment is
**same encoder, same labels, same compute**: baseline CNN versus CNN plus
bilateral interval scorer/decoder. Do not silently augment only one side.

## Additional data gate, not a completed training set

The local DisProt 2026_06 extract has 460 explicit flexible-linker regions
across 360 proteins. Exact-ID exclusion of TR166, TE82, TE64, and CAID3
leaves 205 distinct candidate proteins; this is **not** homology clearance.
Most residues outside their annotated intervals are unlabelled, not known
negatives. DLD offers 1,560 training sequences with structural IDL/DDL
labels, but that is a different ontology. It may support a separate
auxiliary-pretraining ablation, never direct pooled DFL positives. Before
training, audit sequence identity/family overlap, sequence/version mapping,
annotation release dates, and candidate negatives; freeze a family-held-out
development source that has not been used for model choice. TE64 and CAID3
have already been viewed and must not select architecture or thresholds.

## Falsifiable experiment ladder

| Trial | Single change | Why it could help | Failure criterion |
|---|---|---|---|
| A | Current frozen-ESM2 residue CNN, re-evaluated on the **same new dataset** | Matched reference | Establishes baseline, not a novel model |
| B | Add boundary heads and segment decoder, no bilateral features | Does interval consistency help? | No APS/region gain at matched precision |
| C | Add bilateral flank-interior score to B | Does connector context distinguish loops/tails? | No independent gain beyond B |

Maximum three architecture trials and six GPU-hours in the current bounded
round; promising variants need multiple seeds in a later documented round.
Primary development metrics: full-sequence APS and AUROC, residue recall at
empirical precision >=0.90 with intact ties, and region recall/precision at
IoU >=0.5. Also report boundary error, false-positive intervals on verified
no-linker proteins, coverage/abstention, latency, VRAM, seeds, raw counts,
source hashes, and failures. All methods use identical inputs, candidate
coverage, masks, and evaluation code. A publishable superiority claim needs
an untouched homology-separated test and strong same-input baselines with
paired uncertainty; no CAID3 or TE64 retuning.

## Relation to prior work

This is a **task-specific combination/hypothesis**, not a claim that span
decoding or protein segmentation was invented here. Segment-level scoring is
established by [semi-Markov CRFs](https://proceedings.neurips.cc/paper_files/paper/2004/file/eb06b9db06012a7a4179b8f3cb5384d3-Paper.pdf).
[Zero-shot protein segmentation](https://pubmed.ncbi.nlm.nih.gov/41218076/)
shows that protein-LM embeddings can expose functional boundaries, and
[PSALM](https://www.biorxiv.org/content/10.1101/2024.06.04.596712v3.full)
already uses structured domain calls. [LINKER-Pred2](https://pcrgwd.ucd.ie/linker_pred/help/)
uses a CNN with ProtTrans and MSA-Transformer inputs trained on DLD and
DisProt. BiCoS differs by explicitly scoring a **candidate connector against
both flanks and a null state**, using one sequence at inference. Whether that
is useful or original enough for a paper remains an empirical and literature
question. Do not advertise it as a breakthrough before the matched tests.
