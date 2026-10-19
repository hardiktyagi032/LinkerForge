# DFL data expansion and BiCoS architecture gate

Date: 12 October 2026. Status: **candidate data and untrained architecture;
no performance improvement demonstrated**.

## New data, with actual label semantics

The archived DisProt 2026_06 source contains 460 explicit flexible-linker
regions on 360 proteins. Excluding all protein IDs in TR166, TE82, TE64, and
CAID3 leaves **205 proteins with 256 curated positive regions**. The versioned
[candidate manifest](../data/processed/dfl_positive_candidates_2026_10_12.manifest.json)
records 9,730 positive residues, 149,488 **unknown** residues, and **zero
verified negative** residues. The [candidate records](../data/processed/dfl_positive_candidates_2026_10_12.jsonl)
retain region references, ECO IDs, release, coordinates, source/config/code
hashes, and evidence quality. They are **not yet a trainable dataset**.

An all-pairs local-alignment review screen compared those 205 candidates
against 166 TR166, 82 TE82, 64 TE64, and 31 CAID3 proteins, plus one another:
91,225 pairs in 114.2 seconds. Using the preregistered *review flag* of
at least 30% local identity, at least 80 aligned residues, and a 70%
shorter-sequence coverage proxy, **45 candidate proteins** flag against a
protected set and 160 do not trigger that strong flag. Some overlaps are
unambiguous contamination risks: a 100%-identity 203-residue local match,
one >90%-identity 422-residue match, and several >80%-identity matches.
Among candidates, 23 strong pair flags need family grouping. The lower
25%-identity/50-residue threshold flags every candidate, often from long or
low-complexity alignments, so it is not a clean automatic exclusion rule.

**Interpretation:** exact-ID exclusion was insufficient. The 160 unflagged
proteins are *provisional review candidates*, not homology-certified
training examples. The alignment length/coverage proxy can misrepresent
gapped local matches; domain-family and low-complexity review remain gates.
Do not train on any candidate until the final family-separated source set is
frozen. Do not use CAID3 or viewed TE64 for model selection.

## Different model mechanism

The [BiCoS specification](../literature/DFL_BILATERAL_SEGMENT_ARCHITECTURE_2026-10-12.md)
is a sequence-only bilateral interval model: propose linker start/end pairs,
score the interior against independent left and right flanks, compare with
the null/no-linker option, and decode consistent non-overlapping intervals.
It uses the **same frozen ESM-2 35M encoder as the current CNN initially**;
there is no ProtTrans or MSA-Transformer requirement. This isolates whether
connector geometry *in sequence representation* helps, rather than changing
features and architecture simultaneously. The candidate proposer and
bilateral scorer are implemented in
`src/linkerforge/models/bilateral_span.py`; three CPU contract tests pass.
The segment decoder, data loader, frozen evaluation, and training trial are
**not yet implemented**. No result or novelty claim follows from a passing
unit test.

## Next executable gate

1. Resolve flagged homology/domain families and freeze a protected-split
   candidate pool. Keep all nonpositive DisProt residues unknown unless a
   separate source establishes negatives.
2. Freeze a new family-separated development set and full-sequence metrics;
   run current CNN and BiCoS on identical train/development records and
   compute. TE82 can be a retrospective reference only, since it selected
   the current checkpoint.
3. If the data gate passes, run the bounded trials in the BiCoS spec: current
   CNN, boundary/span decoder, then bilateral scorer. At most three
   architecture trials/six GPU-hours for this documented round, no duplicate
   GPU jobs. Keep all results, including negative ones.

The [local similarity report](./dfl_positive_candidate_similarity_screen_2026-10-12.json)
contains every flagged pair and its source/provenance. Local alignment is a
screen, **not** proof of family independence. Formal family clustering and
fresh independent evaluation are still required for any publishable claim.
