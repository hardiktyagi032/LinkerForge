# Classifier workstream: first-stage data gate

This document assigns the **first** build stage to the DFL residue classifier.
Geometry, cited templates and the retrieval baseline are downstream, separate
work. `CURRENT_DIRECTION_2026-10-18.md` gives the complete order.

## Implemented, not yet unblocked

- `scripts/predict_dfl_frozen.py` provides a hash-checked, provisional inference
  interface for the historical checkpoint. It abstains by default. It is **not**
  a certified mining classifier.
- `scripts/preflight_dfl_family_training.py` is a tracked CPU gate for a *new*
  family-disjoint split. It requires pinned sequence-only CAID3 and DP94
  registries, unopened label seals, a versioned family manifest, hashed
  train/development/auxiliary files, source-specific `1/0/x` semantics,
  provenance, and exact/containment/local-similarity exclusions. It checks
  cross-role family and exact-sequence overlap and requires observed DFL
  positives in train and development. The similarity rule is BLOSUM62 with
  gap 10/1, at least 50 aligned residues, 25% identity and 50% coverage of
  the shorter sequence. It opens **no** benchmark label file.
- Passing this script proves only consistency with the supplied family map.
  A self-declared or poor family map is not a biological independence proof.
  The clustering source, parameters, input SHA-256, version and family/domain
  audit still need external validation. The source-specific negative semantics
  also need evidence, not just a manifest assertion.

The old `caid3_protected_dfl_v1` split fails closed. The read-only detector
status check identifies a local-similarity collision between train protein
`DP00919` and candidate holdout `DP03956`. DP94 remains a sequence-only
*candidate*, not a certified DFL benchmark. Neither that candidate's labels
nor the spent CAID3 labels/scores are available for model selection.

The 18 October source-capacity audit found at most 40 unique positive
sequences after direct screening of four candidate training sources, and 5
outside benchmark-touching components under the conservative transitive local
graph. This is not a validated family split. See
`reports/DFL_B1_FEASIBILITY_AUDIT_2026-10-18.md` for hashes, source tiers and
the alternative annotated-data route. **B1 remains open.**

That route now has a versioned local candidate artifact: 884 current UniProt
full-protein sequences matched their explicit flexible/disordered-linker region
peptides exactly, with all other residues masked unknown. Only 11 sequences
avoid direct CAID3/DP94 screening, one from the PubMed-supported tier. These
are not adjudicated DFL gold or negatives. The script, schema and hashes are
in the B1 feasibility report; neither training nor a split was launched.

The paper survey and sequence-only sensitivity audit in
`reports/DFL_B1_PAPER_SURVEY_AND_SPLIT_DESIGN_2026-10-18.md` diagnose the
present local rule as a poor stand-alone family definition. A *proposed*,
unvalidated reciprocal full-length screen flags 37/279 unique positive
candidate sequences against CAID3/DP94, versus 243/279 under the binding local
rule. The 206 changed decisions are not cleared for training: shared-domain
homology, low-complexity effects and the benchmark contract require a separate
family review. B1 and the current preflight remain unchanged and blocked.

## Reproduce the implemented checks

From the repository root, with `parasail` installed in the selected Python
environment:

```powershell
python -m unittest tests.test_preflight_dfl_family_training tests.test_predict_dfl_frozen -v
python scripts/preflight_dfl_family_training.py path/to/new_split/manifest.json
```

The tests create only synthetic benchmark sequences and masks. A command that
prints `pass_declared_sequence_and_family_manifest_only` is **not** a launch
authorization. The real trainer must invoke the new gate *and* the active
detector status check before GPU allocation, after a qualified versioned split
and all nominated benchmark registries exist. No such split is approved yet.

## Work remaining in this first stage

1. Select and document a DFL-labelled training source with verified positive,
   negative and unknown semantics, source release, rights and accession lineage.
   A positive-only source may contribute positives/unknowns; its unannotated
   residues must not become negatives. DLD labels are not DFL ground truth.
2. Freeze sequence-only benchmark registries and an independently justified
   domain/family clustering method. Hash inputs and cluster membership, then
   build a new train/development/auxiliary split and run the preflight. The
   current split cannot be re-labelled as passing.
3. Establish an independently adjudicated no-linker set, disjoint by family.
   Without it, specificity and large-scale mining remain unmeasured.
4. Wire preflight into a bounded training launcher. Retrain matched baselines
   and proposals on identical masks, encoder, scoring and coverage. Select
   only on development; repeat promising arms across seeds.
5. Calibrate abstention on a clean family-disjoint calibration subset. Freeze
   model, threshold, evaluator and competitor coverage before a one-time
   untouched comparison. Only then decide whether mining is justified.

No classifier breakthrough or published-method superiority has been
demonstrated. The one-time CAID3 retrospective is spent and must not be rerun
or used for tuning. See `RESEARCH_HANDOFF.md` and
`literature/DFL_UNTOUCHED_COMPARISON_CONTRACT_2026-10-17.md`.

The 18 October paper survey and hash-checked full-length/domain-family
sensitivity audits are in
`reports/DFL_B1_PAPER_SURVEY_AND_SPLIT_DESIGN_2026-10-18.md`. They found 134
exact-metadata DFL-positive candidate sequences in 112 components outside
both sequence-only benchmark registries under the combined exploratory family
graph. This is not yet a defensible train/development split or permission to
replace the binding firewall; B1 remains open.
