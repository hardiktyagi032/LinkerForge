# Ensemble scoring and encoder-hook preregistration — 2026-10-17

Status: code and tests only; **no ensemble result exists**. Nothing here opens CAID3 labels, scores or per-protein results, and nothing relaxes the untouched-comparison contract.

## Ensemble question (protected development only)

Does averaging already-trained, APS-selected checkpoints of one architecture across seeds 7/17/31 improve on its single-seed members? Two matched ensembles are scored: global-context (`CompetitorGapSegmenter`) and the matched SAM-like disorder-transfer baseline, each from its own three checkpoints. The comparison is baseline ensemble versus proposal ensemble on identical records, masks, ESM2-35M input and known-residue coverage. Members are never mixed across architectures; the scorer refuses differing architectures, protein ids/order, labels, duplicate seeds, fewer than three members, probabilities outside [0,1], or any split label other than `protected_development`.

Combiners (both reported, none chosen on a result): mean of probabilities; mean of logits passed through the sigmoid. Uncertainty output: per-residue population variance of member probabilities (summarised over known, positive and negative residues). Variance is a diagnostic, not a selection criterion, and is not calibrated.

Metrics (same definitions as `scripts/run_dfl_disorder_transfer.py` / `score_protected_global_context_development.py`, reimplemented in numpy at exact score ties): residue APS, AUROC, Fmax, recall at empirical precision >=0.90 and >=0.99 (each needs >=50 TP), and the no-positive proxy specificity (proteins with no `1`, max known score below the precision>=0.90 threshold; raw counts reported; partial-label proxy, not verified no-linker specificity; one protein = 0.0588). `x` residues are dropped, never negatives.

Decision rules, fixed in advance: the ensemble is "eligible for further preregistered work" only if its APS exceeds the mean of its members' APS and the proxy-specificity loss against the matched baseline ensemble is <=0.02 absolute (the existing guardrail). Otherwise report negative. Any gain is developmental; an ensemble cannot claim superiority without an untouched, family-audited benchmark.

Memory/GPU: members are scored one at a time (one GPU job at a time, 6 GB) and saved with `linkerforge.ensemble.save_member`; `stream_ensemble` then folds the `.npz` files sequentially (running sums and Welford variance), so members are never co-resident. The scoring itself runs on CPU. A member's saving step (checkpoint -> per-residue probabilities) is a separate, not yet written GPU adapter around `score_one`; it must also record the checkpoint SHA-256.

Not yet done: the checkpoint-to-`.npz` adapter, any real run, CAID3 anything (forbidden), bootstrap confidence intervals, region/IoU metrics.

## Encoder-swap hook design (ESM-2 650M, ProtT5; interface only)

`src/linkerforge/ensemble/encoder_hook.py`. Encoders are never downloaded or run by this repo's code. An external, user-run extractor writes `<protein_id>.<encoder>.npz` with sequence, its SHA-256, encoder name, revision and an `(L, D)` array, one row per residue (special tokens stripped). Registered encoders and dimensions: `esm2_t33_650M_UR50D` 1280, `prot_t5_xl_uniref50` 1024, `esm2_t12_35M_UR50D` 480. `PrecomputedEmbeddingStore.get` raises on: unknown encoder, missing directory/file, wrong encoder or revision, protein-id or sequence/hash mismatch, wrong length, wrong dimension, non-finite values, unsafe ids; `batch` is all-or-nothing. There is no fallback to another encoder or zeros.

Scientific rules for any use: the baseline must be retrained on the same embeddings (contract rule 4); 650M/ProtT5 runs are labelled richer-input comparisons, a new versioned preregistration and the protected-data preflight come first, and the 3-architecture/6-GPU-hour round caps apply. Embeddings must be extracted for every benchmark-excluded record set identically; benchmark sequences may be used only for exclusion.
