# LINKER-Pred2 input-modality audit — 2026-10-17

## Verified sources

- The [authors' server documentation](https://pcrgwd.ucd.ie/linker_pred/help/) states that LINKER-Pred2 is CNN-based, trained on DLD and DisProt annotations, and integrates ProtTrans plus MSA-Transformer embeddings. LINKER-Pred-Lite excludes MSA features. This is the authors' method claim, not an independently reproduced ablation.
- The [released LINKER-Pred2 repository README](https://github.com/deemeng/punch_linker2) specifies per-residue `.npy` inputs aligned by sequence ID and length: one-hot `(1,L,21)`, ProtTrans `(1,L,1024)`, and MSA Transformer `(1,L,768)`. It provides source and a Docker invocation requiring external embedding directories. Thus the full model is not sequence-only at inference: an MSA-derived representation must first be available.
- The protected LinkerForge config uses frozen `facebook/esm2_t12_35M_UR50D` and 510-residue windows, with no ProtTrans or MSA input. This is a demonstrated input/representation difference. It is **not** demonstrated to be the cause of the LINKER-Pred2 performance gap. Different training records and label semantics also confound a direct attribution.

## Fair implementation handoff

1. Build a feature preflight that rejects missing files, sequence-ID mismatch, wrong length, nonfinite values, and dimension mismatch for each channel. Record feature-generator revision and source sequence SHA-256. Do not silently substitute zeros for missing MSA embeddings.
2. Run a matched rich-encoder-only ablation before MSA fusion. Compare ESM2 versus ProtTrans on exactly the same protected split, masks, head/training budget and coverage. This tests representation, not the published predictor as a whole.
3. Only compare MSA fusion on the intersection for which both variants have valid embeddings. Report excluded proteins and MSA-generation cost. Do not use CAID3 labels or its spent retrospective to choose the architecture.
4. DLD structural linker labels cannot simply become DFL positives. Source-specific heads or masks require a separately audited label map and family split.

## Relationship to other tracks

The transfer track's [protected-windowing audit](../track-transfer/2026-10-17-protected-windowing-audit.json) found just 1/61 training and 0/30 development positive spans crossing a 510-residue cut. That weakens a crude span-fragmentation explanation on these protected splits, but does not quantify whole-protein context loss. The ML track has a completed three-variant screen pending its own reconciliation; no result from it is used in this audit.

## Local provenance

- `scripts/run_dfl_disorder_transfer.py` SHA-256 `43c529dd72cc42f4ff1a5ade38a5d5601a6e4c7ecdce6501c162219a8128a4d4`
- `scripts/train_dfl_masked_cnn.py` SHA-256 `4e0b7b6e9c7a4df57148dff89756af2e378e933b153a824f3ca7b3d217a75ce8`
- `configs/dfl_caid3_protected_baselines_2026-10-16.json` SHA-256 `e49780fa6917a446a73d8fb93ae9303151268617fe482cd357c0fa1db69035a1`
- Transfer audit SHA-256 `eb0716a6c16d8592f60b04d132b5e0ebca716afb06b3e6591dc76102c9c21d46`

No GPU job or CAID3 comparison was run for this audit.
