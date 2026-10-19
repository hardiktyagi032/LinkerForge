# Untouched DFL comparison contract (2026-10-17)

Status: binding research gate, not a performance result. The goal is sequence-based disordered flexible linker detection. A benchmark is **evaluation-only**: its labels, scores, protein-specific errors and thresholds cannot enter training, development selection, feature design, or data filtering. Filtering may use benchmark IDs and sequences only.

## Current evidence and gate

- Public CAID3 common-27 has already been viewed after one frozen-checkpoint comparison. It is a retrospective result, not an untouched benchmark; do not rerun or use it to choose another model.
- DisoFLAG DP94 is a *candidate*, not a certified independent **DFL** test. Its sequence-only registry is `data/processed/prospective_dfl_holdout_dp94_v1/`. Under the declared local-alignment screen, 88 of 98 benchmark proteins connect to 148 existing train/development/auxiliary proteins (65/35/48 by split; proteins may connect to multiple references). The current protected-data preflight therefore **fails closed**. This is not proof that the remaining ten are family-independent, that DP94 was unseen by published competitors, or that its published label track represents the same linker target. The DisoFLAG paper presents DP94 primarily as an intrinsic-disorder test; target semantics require source-level verification before any DFL evaluation.
- No new DFL training on `data/processed/caid3_protected_dfl_v1` is authorized while this gate fails. Previously completed experiments remain historical exploratory results, not a clean DP94 comparison.

## Required sequence and family firewall

1. Version and hash an evaluation registry containing benchmark accession, sequence, source release and label-seal state. Do not open its labels while preparing data or models.
2. Before creating any train/development/auxiliary split, exclude exact accession, exact sequence, containment, and the preregistered local-similarity connections to *every* nominated benchmark. Extend this to domain/family or homology clusters with explicit tool, version, thresholds and cluster manifest; all members of a connected family stay on one side. Audit any competitor training-set lineage separately.
3. Assign train/development at cluster level. Save record provenance, positive/negative/unknown mask semantics, source release, split hash, screening report and exclusions. Unknown is never silently relabeled negative. Retain an independently adjudicated no-linker set if specificity is claimed.
4. A training launcher must recheck source and split hashes plus the full benchmark registry on every job, before allocating GPU. Any missing registry, changed sequence, ambiguous ID, unresolved family collision, or manifest mismatch stops that job. One GPU job at a time; bounded rounds of at most three architecture variants and six GPU-hours.

## Selection, seal and one-time evaluation

- Use only family-disjoint development data for model/epoch/threshold selection. Compare each proposal with baselines retrained on the same records, masks, encoder/input modality, residue coverage and evaluation code; use at least three seeds for a promising variant.
- Before opening a benchmark label: freeze architecture, source revision, weights and hashes, all preprocessing, calibration and thresholds, competitor versions/predictions, common-target and common-residue intersection, metric code, and the analysis plan in an immutable selection manifest. A separate reviewer or script verifies the seal.
- Score each sealed model and obtainable published baseline once on identical covered residues. Report raw TP/FP/FN where thresholded, residue APS, AUROC and Fmax; add span IoU/boundary metrics, high-precision recall, no-linker specificity (only where adjudicated), coverage/exclusions, per-protein paired differences and cluster-bootstrap confidence intervals. Record both matched-input comparisons and any richer-input published models as distinct comparisons.
- A superiority or breakthrough claim requires a positive prespecified effect over the strongest matched published method with uncertainty excluding a trivial gain, acceptable specificity and reproducibility across seeds on a genuinely untouched, family-audited test. No result can guarantee this in advance. A public, retrospectively viewed benchmark cannot supply this claim.

## Coordinated schedules

The transfer track owns provenance, masks and family-split audits; the competitor track owns published-method training lineage, input modality and frozen common-target baseline availability; the ML track owns fail-closed code, matched development trials and job reconciliation. Each wake reads this contract and the other tracks' latest handoffs, makes one durable state transition, and writes a dated artifact in its own directory. Every completed audit updates the next executable gate; schedules must not repeatedly launch the same failed job or manufacture progress. They remain active until the user asks to stop, but no schedule may relax the isolation or one-time evaluation seal to produce a score.
