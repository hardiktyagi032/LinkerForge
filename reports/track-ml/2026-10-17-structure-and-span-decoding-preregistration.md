# Structure features and span decoding preregistration — 2026-10-17

Status: interface and decoder code only. **No model has been trained, no structure has been downloaded, and no result is claimed.** No CAID3 label, score or per-protein result is used here or may be used to choose any setting below.

## A. Versioned AlphaFold-derived feature interface

Code: `src/linkerforge/structure/af_features.py` (schema `linkerforge.af_features.v1`), tests in `tests/test_structure_span_decoding.py` using a synthetic, clearly labelled fixture (invented numbers, not AlphaFold output).

Rules the loader enforces (fail closed, no imputation or fallback): schema version match; `provenance.generated_independent_of_labels` literally true and a named source; valid UniProt accession keys; canonical sequence; pLDDT in [0,100] and optional per-residue mean PAE >= 0, both finite and exactly sequence length; unknown fields rejected. `get(accession, sequence)` refuses a missing accession, a length mismatch and a sequence mismatch. `require_all(targets)` must pass over the **entire** train, development and every compared-baseline target set before any feature-using arm runs, so the feature is available for every compared target and the matched baseline sees identical coverage (the baseline arm either gets the same inputs or the feature arm is dropped to the covered subset for both).

Planned use (not yet run): feature-augmented arm vs the matched no-structure arm on the same split, masks, encoder and scoring coverage, three seeds, selection on development masked APS only. Features for benchmark sequences may be generated but benchmark labels may not inform them. Sequence-to-accession provenance and file SHA-256 must be recorded with any result. Accessions with no AlphaFold model are reported as coverage failures, not zero-filled.

## B. Span decoding

Code: `src/linkerforge/detector/span_decoding.py`. Decoders consume probabilities only.

- `hysteresis_decode(high, low, min_length, max_gap)`: keep runs of p>=low containing p>=high, merge gaps <= max_gap, drop runs < min_length.
- `viterbi_decode(switch_penalty, prior)`: exact two-state smoother in numpy.

Evaluation reuses `evaluation.region_metrics` (greedy one-to-one IoU matching, region recall/precision at IoU>=0.5, matched start/end MAE as boundary error) and adds pooled residue IoU. The baseline for comparison is the plain fixed-threshold-0.5 mask used by existing reports.

Preregistered grid (fixed now, tuned on protected-development predictions only, never on CAID3): high in {0.5}, low in {0.3, 0.4, 0.5}, min_length in {1, 4, 8}, max_gap in {0, 2, 4}; Viterbi switch_penalty in {1, 2, 4}. Selection: highest development region recall (IoU>=0.5) subject to region precision not falling and residue-level precision at the matched operating point not falling more than .02 absolute versus the undecoded baseline; ties by lower matched start+end MAE. Report every grid cell, including negatives. Prior bounded-span variants were negative, so a null result is the expected default; any gain is developmental and not independent superiority.

## Not yet done

Neither component has been run on real predictions or real AlphaFold data. The grid has not been executed. Decoder gains on a single development set may reflect threshold fitting; repeat across the three seeds before any promotion.
