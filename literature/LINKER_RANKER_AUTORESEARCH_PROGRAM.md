# LinkerForge predictor autoresearch contract (2026-10-09)

## Scientific question and claim gate

Can **independent attachment-port geometry** improve ranking of an observed natural peptide linker against length/composition-matched alternatives for previously unseen domain-family clusters, beyond sequence-only, fixed-GS, retrieval, and hand-feature baselines? This is a *hypothesis*, not an established novel result. The paper claim becomes permissible only after a documented close-method review, matched-compute ablation, cluster-disjoint evaluation, and at least three seeds. Natural-linker recovery is a proxy for sequence plausibility, **not** fusion functionality or evolutionary optimality.

## Editable and frozen surfaces

- Editable model: `src/linkerforge/models/port_gnn.py`, its training configuration, and explicitly named architecture variants. Current implementation is a proof-of-concept and does **not** yet include frozen ESM-2 embeddings or a data loader.
- Frozen evaluation before first comparable trial: sequence/structure preprocessing, candidate pool, group split, baseline rules, tie handling, metrics, and evidence-quality exclusions. Keep split IDs and input hashes in every run manifest.
- Training inputs: only each domain's independently centered local C-alpha graph, the candidate linker sequence, and approved frozen sequence embeddings. Never provide native cross-domain coordinates or the hidden natural linker to the port encoder. A native-pose oracle may be reported separately and must never be called deployment-compatible.
- Positive label: observed natural linker. Negatives: explicitly tagged synthetic alternatives, **not** observed biological failures. At least half the negatives should match observed length and similar composition; otherwise the task is confounded by easy length signals. Deduplicate exact sequences across candidate pools.
- Holdout: group entire homology/domain-family components *before* experimentation. Tune only on validation; seal the blind partition and save predictions before revealing references. Synthetic alternatives must be constructed without blind-reference-dependent tuning.

## Minimum benchmark

1. Adjudicate records and create structure-derived port graphs with sequence-to-coordinate mapping. Reject unresolved attachment residues, nonfinite coordinates, dubious domain boundaries, and records lacking provenance. The current 91-record CATH pilot is `provisional_unreviewed_pilot`, not a paper-grade benchmark. Do not train publication claims on it.
2. Freeze a candidate pool with observed linker, fixed `(GGGGS)3`, train-only retrieval candidates, equal-length composition-matched alternatives, and scrambled controls. The exact same pool and hard rejection rules apply to every method.
3. Run fixed-GS, length heuristic, nearest-training retrieval, trained hand-feature ranker, sequence-only neural model, and local-port GNN. Sequence-only versus GNN is the primary geometry ablation. An ESM-2-augmented variant is later, explicitly separate.
4. Primary metric: mean reciprocal rank of observed linker on held-out groups. Secondary: top-1/top-5 recovery, pairwise accuracy, stratification by linker length/domain-family/evidence quality, runtime, and confidence intervals bootstrapped over leakage groups. Record tied scores without arbitrary favorable tie-breaking.
5. Mechanism trial budget: at most three architecture variants and six GPU-hours in the first bounded round, one change at a time, with three seeds for any promising variant. Report every trial as promising, negative, inconclusive, or invalid. Do not automatically select the best validation seed or change the blind set.

## Execution gate and stop rules

Before GPU training, require: versioned graph/pair schemas, adjudicated source IDs, coordinate mapping audit, frozen homology clusters, candidate-pool hash, split manifest, baseline execution, and a no-competing-job check. If any gate fails, work on the missing artifact and do not burn GPU hours. Stop after budget, failed integrity checks, or repeated infrastructure failure. Existing detector trials and metrics are separate and must never be represented as predictor evidence.

## Research positioning

SynLinker already designs linkers for uploaded domain structures, so “linking two proteins” is not a novelty claim. A defensible incremental claim would be *measured benefit of deployment-compatible independent local-port geometry under homology-disjoint natural-linker retrieval*, if the benchmark demonstrates it. The null result is also publishable as a careful benchmark or negative finding, provided the data and baselines are strong enough. Before submission, compare against close recent fusion/linker ranking and geometric protein design work, not merely the 2015 SynLinker paper.

Initial primary references: [SynLinker (Bioinformatics, 2015)](https://doi.org/10.1093/bioinformatics/btv447) establishes the prior two-domain linker-design workflow; [Jing et al., GVP-GNN (ICLR, 2021)](https://openreview.net/forum?id=1YLJDvSx6J4) motivates geometric protein graph encoders. The present code is a simpler distance-only message-passing prototype, **not** a GVP implementation or a proven improvement over either method.
