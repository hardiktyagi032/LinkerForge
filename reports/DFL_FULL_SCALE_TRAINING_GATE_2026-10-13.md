# Full-scale DFL training: data gate (13 October 2026)

Status: **not launched**. The local GPU was idle at inspection. Launching the
requested multi-model experiment on a nominal 2,000-sequence pool would not
currently be a valid larger-scale DFL comparison.

## Counts and incompatible labels

| Local source | Count | Current use for CAID-style DFL training |
| --- | ---: | --- |
| Published TR166 | 166 train proteins | Usable under its original `0/1/x` mask; the six-epoch pilots used this set. |
| DisProt 2026_06 explicit flexible-linker regions | 360 proteins, 460 regions | Positive annotations, but nonpositive positions are largely unknown. Exact CAID3 and earlier split IDs overlap; the 205-protein candidate pool after exact exclusions has 9,730 positive and 149,488 unknown residues, zero verified negatives. Homology review remains open. |
| DLD structural domain-linker collection | 2,620 records total, 1,560 original train | IDL/DDL is a different target from CAID DFL. The original validation/blind records cannot be reallocated to training merely to reach 2,000. Raw code-0 semantics and cross-source homology remain gates for auxiliary pretraining. |
| Annotated-only sequence catalog | 24,763 exact-unique linker strings | Mixed NRPS, UniProt, and DLD/DisProt annotations. The manifest marks zero records training-ready; 455 are protected and 404 quarantined. Linker-only strings lack a verified full-protein negative mask. |

LINKER-Pred2's authors state that their model was trained with more than 2,000
linker examples from DLD and DisProt. That is not evidence that our current
2,620 DLD records are 2,620 interchangeable DFL training proteins. The
[DLD download page](https://pcrgwd.ucd.ie/linker/download/) explicitly names
codes 1--5 as IDL, DDL, loop, domain, and terminus but does not define code 0
there. Its published train/validation/blind partition must remain intact.
The [released LINKER-Pred2 repository](https://github.com/deemeng/punch_linker2)
contains predictor code, but its current Git tree does not expose a row-level
train-label file in `dataset/`.

## Experiment to run once the gate passes

1. Freeze a provenance-bearing full-protein DFL train/development manifest.
   Preserve `1`, verified `0`, and `unknown` distinctly. Exclude benchmark
   accessions, exact sequences, close homologs, and their families from
   development/test leakage; quarantine uncertain mappings.
2. Keep DLD as a separate auxiliary task or pretraining arm. Its benefit must
   be measured against a no-DLD arm on the **same** DFL development set.
3. Train the residue CNN, SAM-like segmenter, and YOLO-style segmenter on the
   same eligible examples and frozen split. Use at least five seeds, a longer
   preregistered epoch ceiling with early stopping on development APS, and
   record learning curves, compute, model/data/config hashes, and every run.
4. Select architecture and epoch only on the new development set. Evaluate
   CAID3 as previously viewed retrospective data, not as an optimizer or
   fresh blind test. Use an untouched prospective test for superiority claims.
5. Report full-sequence and masked APS, AUROC, coverage, residue and interval
   precision/recall, boundary error, and no-linker specificity. Compare
   released competitors on identical proteins and positions; label different
   training data/input modalities as such.

The immediate missing artifact is a source-by-source full-protein label
crosswalk with negative/unknown semantics and a homology-separated split.
Until it exists, additional epochs or seeds on TR166 are a learning-curve
pilot, **not** the requested 2,000-example fair comparison. No GPU trial or
performance claim is recorded by this gate report.

Sources in this repository: `data/processed/published_dfl_splits/manifest.json`,
`data/processed/dld_reference/manifest.json`,
`data/processed/linker_catalog/annotated_only_v1/manifest.v1.json`,
`reports/DFL_DATA_EXPANSION_AND_ARCHITECTURE_GATE_2026-10-12.md`, and
`reports/DFL_LABEL_MASK_AUDIT_2026-10-12.md`.
