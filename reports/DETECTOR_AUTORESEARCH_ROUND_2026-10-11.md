# DLD detector autoresearch round: LoRA and fixed-span decoding

Status: **three trials complete; no checkpoint promoted**. This concerns the
natural-protein linker identifier, not the fusion-linker ranker. DLD folds 1–3
were training data and fold 4 was development data. Fold 5 had already been
viewed and was not used as a fresh blind set.

## Frozen comparison

Primary decision: maximum residue recall at empirical precision at least
0.90, at least 50 true positives, with equal scores handled as ties. Guardrail:
no-linker-protein specificity no more than 0.02 below the weighted-BCE
reference's 0.971631. All results below use the same 6,205 labelled positive
residues in fold 4. The minimum span length was fixed at four *before* the
second and third trials, based on the training-label span distribution and a
fold-4 error audit. This makes the decoder comparison development-informed.

| Scorer and decoder | TP | FP | Precision | Recall | No-linker specificity | Matched regions / 477 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Weighted BCE, independent residue threshold | 475 | 52 | 0.901328 | 0.076551 | 0.971631 | 55 |
| Asymmetric, independent residue threshold | 525 | 58 | 0.900515 | 0.084609 | 0.964539 | 60 |
| Weighted BCE, fixed min-four span decoder | 540 | 58 | 0.903010 | 0.087027 | 0.992908 | 60 |
| Asymmetric, fixed min-four span decoder | 542 | 60 | 0.900332 | 0.087349 | 0.985816 | 61 |
| ESM-2 35M LoRA + residue CNN | 0 eligible | n/a | no qualifying point | 0 | n/a | n/a |

The decoder removes predicted intervals shorter than four residues *after*
thresholding. The threshold is then selected over all distinct fold-4 scores,
processing ties together. The 540 and 542 true-positive counts are therefore
not values at the old unfiltered threshold. The minimum length was not
adjusted between models. On the weighted-BCE checkpoint, the reference audit
found 15 false-only predicted spans at its original threshold, 13 of which
were 1–4 residues long. All 1,350 contiguous labelled positive spans in the
training folds had length at least four. Nevertheless, thresholding can split
real linkers into shorter runs, so this heuristic is not guaranteed to help
outside fold 4.

The asymmetric-plus-decoder result exceeds the weighted-BCE-plus-decoder
result by only **two residues** and one matched region. That small difference
is not a meaningful architecture win on one development split. The decoder
mechanism itself is promising relative to each unchanged scorer, but not yet
generalized. The unmodified score AUPRC remains 0.399801 for weighted BCE and
0.404802 for asymmetric; interval decoding changes the operating-point mask,
not the underlying residue-score ranking.

## LoRA trial

The query/value LoRA experiment ran ten epochs with the pinned ESM-2 35M
revision. No epoch yielded at least 50 true positives at precision 0.90. Its
highest recorded AUPRC, 0.398033, was slightly below the weighted-BCE
reference's 0.399801. The trial was marked negative, not repeated, and its
checkpoint was not promoted. Its experiment directory is
`artifacts/lora-35m-r8-seed7-001`.

## Provenance and limitations

The machine-readable ledger is `reports/detector_autoresearch_ledger_2026-10-11.json`.
The unchanged-reference error audit is
`reports/dld_false_positive_audit_2026-10-11.json`. The two decoder trial
results, including checkpoint/data/config/source hashes, runtime, model
revision, GPU, and region/boundary metrics, are in
`artifacts/frozen-reference-min4-span-decoder-001/result.json` and
`artifacts/asymmetric-35m-min4-span-decoder-001/result.json`.

No biological false-positive adjudication was performed. Label-negative spans
may include unannotated linkers. DLD raw code 0 remains semantically
unverified, so no source-class head was trained. DisProt is not an independent
test until homology and coordinate overlap are audited. None of these
development results proves reliable detection in new protein families, and
none is experimental validation.

## Decision for the next round

Do not retune minimum length on fold 4 or promote either decoded model.
Prioritize an independently adjudicated, homology-audited test source and a
matched sequence-context architecture experiment (for example a dedicated
BiLSTM head inspired by [IDPFunNet](https://doi.org/10.1093/bib/bbag126)).
Evaluate that architecture against the same frozen weighted-BCE and asymmetric
baselines before combining it with the decoder. A larger ProtT5 backbone is
not assumed to fit the local 6 GB GPU; first establish a resource plan.
