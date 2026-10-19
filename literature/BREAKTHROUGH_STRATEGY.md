# Highest-priority detector strategy: preserve labels, then model spans

Status: proposed and gated; not a demonstrated improvement. Scope is the DLD
linker-residue detector, not the downstream LinkerForge fusion-linker ranker.

## Why this outranks another loss-function sweep

The current DLD converter maps source codes `1` and `2` to IDL and DDL, but
maps **all** other source codes (`0`, `3`, `4`, `5`) to binary background. That
may be appropriate for a particular binary benchmark, but it discards whether
a false positive was a loop, domain residue, terminus, or a residue with
uncertain annotation. In particular, code `0` must **not** be called
unlabeled until the source documentation confirms its meaning. Linkers are
also contiguous regions; the current CNN is trained only on residue-wise
loss. These are data/target mismatches that a new focal-like loss cannot by
itself repair. The negative focal-loss result strengthens the priority of
testing them, but does not prove that this strategy will work.

Primary hypothesis: preserving *verified* reference-code distinctions and
learning region boundaries increases validation recall at empirical residue
precision >= 0.90, without reducing no-linker-protein specificity, compared
with the frozen ESM-2 35M + residue CNN baseline.

## Ordered, falsifiable experiment

1. **Recover and verify source semantics.** Re-download the official DLD
   archive, verify its checksum, source member, publication/version and exact
   definitions of codes `0`–`5`. Save a source-to-target mapping table and a
   raw-code frequency/count audit by fold. If code `0` is undocumented, mark it
   `unknown_semantics`; do not silently treat it as a trusted negative or an
   unlabeled positive. Preserve original labels in a *new versioned record*;
   do not overwrite the existing converted shards or their manifests.
2. **Leakage and error audit.** Use only folds 1–3 to build the new training
   records, fold 4 for model choice, and no fold-5 model selection. Recheck
   duplicate sequences and source clusters. Manually inspect a small,
   stratified sample of the baseline's high-score false positives in fold 4,
   especially source codes `0`, `3`, and `5`, without changing ground truth.
   Record the fraction that appears biologically ambiguous versus clear
   nonlinkers. This distinguishes label noise from genuine hard negatives.
3. **Ablation A: source-code supervision.** Keep the ESM-2 revision,
   training folds, windowing, optimizer, compute budget, and seed matched.
   Add an auxiliary source-class head for the verified codes, while retaining
   the original binary IDL/DDL evaluation. If code `0` is confirmed
   unannotated/unknown, mask it from supervised loss; otherwise include it
   according to the source definition. Never create a domain-token input from
   these target labels.
4. **Ablation B: span-aware prediction.** Add linker start/end heads and a
   constrained interval decoder (or semi-Markov/CRF decoder) to the same
   frozen embeddings. Train on contiguous IDL/DDL segments; report region
   precision/recall with a prespecified overlap and boundary tolerance in
   addition to residue metrics. Do not let a post-processing minimum-length
   rule use fold-4 labels to tune itself outside the declared validation
   protocol.
5. **Hybrid only after wins.** Combine A and B only if each adds an
   independent validation benefit. Repeat with at least three seeds. Compare
   each component, hybrid, and baseline at matched compute, identical source
   records, and one frozen operating-point rule. A new homology-audited source
   is required for an independent claim because DLD fold 5 was viewed in
   earlier project work.

Primary selection metric: maximum residue recall at empirical precision
>= 0.90 with at least 50 true-positive residues, calculated with score ties
kept intact. Co-primary guardrail: no-linker-protein specificity must not
drop by more than 0.02 absolute. Secondary: AUPRC, region-level recall and
precision, boundary error, and runtime. Report raw TP/FP/FN and uncertainty
across proteins/clusters. No result is called a breakthrough from a single
validation split or a retrospective threshold.

## Stop/go gates

- If raw codes cannot be recovered and defined, stop A; B can still be tested
  on the existing binary records.
- If high-scoring false positives are mostly clear loops, prioritize a
  loop-versus-linker hard-negative head. If many are unannotated/ambiguous,
  prioritize label review and partial-label training; do not auto-relabel.
- If A or B cannot improve high-precision recall without violating
  specificity, retain the simpler baseline and publish the negative result.
- Expanded unlabeled sequences can be used only after separate source and
  contamination audits; millions of sequences do not mean millions of
  trustworthy linker labels.

## Scientific basis

- [DLD source project](https://dld.chemeslab.org/) supplies the reference
  task and annotations; source-code meaning must be checked against its own
  documentation before remapping.
- [Semi-Markov Conditional Random Fields](https://papers.neurips.cc/paper/2648-semi-markov-conditional-random-fields-for-information-extraction.pdf)
  provides a principled precedent for contiguous labeled segments.
- [BiLSTM-CNN-CRF sequence labeling](https://aclanthology.org/P16-1101/)
  motivates structured decoding rather than independent token decisions.
- [Confident Learning](https://jair.org/index.php/jair/article/view/12125)
  motivates an auditable *review queue* for suspected label errors, not
  unreviewed replacement of reference labels.
- [Focal Loss](https://openaccess.thecvf.com/content_iccv_2017/html/Lin_Focal_Loss_for_ICCV_2017_paper.html)
  is the already-tested imbalance comparator; it did not improve the
  LinkerForge 35M validation AUPRC in the first matched run.

This is a prioritized research strategy, not a claim that these papers prove
its effect on DLD or that any linker predictions are experimentally valid.
