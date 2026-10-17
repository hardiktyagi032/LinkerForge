# LinkerForge checklist: minimum viable publishable result

Companion to `SPEC.md`. Read that first, especially section 5 (integrity constraints). Items are ordered. Do not start a blocked item until its dependencies are checked off.

Status update (18 October 2026): Dorya explicitly resumed work, beginning with the classifier and then geometry-plus-template design with a retrieval baseline. See `CURRENT_DIRECTION_2026-10-18.md`. The scientific dependencies and benchmark seals below remain in force.

Subagent rule: at most two at a time, and Haiku only. Never Sonnet or Opus. Prefer doing the work inline.

Format: `[ ]` open. **Done when** is the test for completion. **Depends on** lists what must already be true.

---

## PAPER I: benchmark and methods analysis

These items need no GPU, no laptop and no new data. They use committed reports and the frozen score files under `artifacts/`, which are gitignored. Item P1 is blocked until those files exist.

- [ ] **P0. Confirm the frozen score artifacts are reachable.**
  - What: check whether the frozen score files that feed `scripts/audit_dfl_mask_policy_counterfactual.py` exist under `artifacts/`. They are gitignored and do not appear in a clean clone.
  - Done when: either the files are present locally and their SHA-256 hashes are recorded, or Dorya has been asked for them and the blocker is stated in the PR.
  - Depends on: nothing.
  - If absent: Paper I can still cite the committed outputs, but must say that the counterfactual is reported from committed JSON and not reproduced.

- [ ] **P1. Reproduce the mask-policy counterfactual.**
  - What: run `scripts/audit_dfl_mask_policy_counterfactual.py` on frozen TE82 scores. Compare unknown-as-excluded against unknown-as-negative.
  - Done when: the output reproduces APS 0.450 (excluded) and 0.115 (negative), matches `reports/DFL_POOR_TRANSFER_CAUSE_AUDIT_2026-10-12.md` lines 20 and 21, and records input hashes.
  - Depends on: P0.
  - Note: check the residue-count column meaning before quoting it. The audit table lists 13,694 (16.23%) and 36,938 (6.02%).

- [ ] **P2. Confirm the 93.35% unknown-label inventory.**
  - What: verify the figure in `reports/DFL_LABEL_MASK_AUDIT_2026-10-12.md` against the DisProt-derived annotation source. Quote the denominator (233,315 DisProt residues per the memory record, unverified here).
  - Done when: the count of unknown residues and the total are reproduced from the source, with the script that computes them named.
  - Depends on: nothing.

- [ ] **P3. Equal-coverage CAID3 reanalysis.**
  - What: recompute the common-27 comparison (15,570 residues, 1,214 positive) using only predictions that cover every residue. Include the 90.3% coverage predictors as a separate, labelled row.
  - Done when: a table exists with coverage per predictor. The published-style mixed table is shown only as a contrast. Sources: `reports/dfl_sam_repeat_locked_caid3_2026-10-17/`, `scripts/build_caid3_common_coverage.py`, `reports/caid3_common_coverage_2026-10-11.json`.
  - Depends on: nothing.
  - Integrity: this is retrospective on a spent set. Select nothing. Do not add any threshold. Report the 0.482 and 0.241 rows as they are, and never put 0.7918 in the same table.

- [ ] **P4. Verify the input modality audit.**
  - What: confirm from the tools' own documentation or source code that the LINKER-Pred family uses inputs beyond sequence at inference (structure or other features). Li et al. is not a source here.
  - Done when: each claim cites a document or code line that was read. Unconfirmed claims are removed or marked unverified.
  - Depends on: nothing.

- [ ] **P5. Collect the clean negative ablations (about ten).**
  - What: list the negative results under `reports/` (for example `DFL_SAM_REPEAT_AND_LOCKED_CAID3_2026-10-17.md`, `DFL_CONTEXT_SPAN_ROUND_2026-10-17.md`, `DFL_BOUNDED_SPAN_ROUND_2026-10-16.md`, `DFL_CROSS_DOMAIN_ROUND_2026-10-12.md`, `YOLO1D_DFL_EXPLORATORY_ROUND_2026-10-13.md`). For each, record the metric, the baseline, and the verdict.
  - Done when: a table has one row per ablation, each with its source file and whether it was evaluated on development or on the spent CAID3 set.
  - Depends on: nothing.

- [ ] **P6. Write the Paper I manuscript.**
  - What: draft the methods analysis. The abstract must say no new method is introduced. Include P1 to P5. Use only the corrected numbers from `SPEC.md` section 2.4.
  - Done when: a draft exists with a figure list where each figure names its source JSON, and every number has a source. No figure may be produced from a number not in the reports.
  - Depends on: P1, P2, P3, P4, P5.
  - Venue: a bioinformatics methods journal, not an ML main track.

- [ ] **P7. Internal integrity read.**
  - What: check the draft against `SPEC.md` section 5. Confirm: no "guarantee" near the 0.90 threshold; 0.7918 and 0.241 never adjacent; no "first" near multi-tether work; no Li et al. number used; no template library presented as a contribution.
  - Done when: a checklist of section 5 is signed off in the PR description.
  - Depends on: P6.

---

## BLOCKED: prerequisites for Paper II

Paper II is the certified high-precision caller plus mined set. Do not draft it until B1 passes.

- [ ] **B1. Family-disjoint train, development and auxiliary split with a passing preflight.**
  - What: build a new versioned split that is disjoint by family cluster (not by protein ID). Make its launcher pass a hash-checked preflight against all nominated benchmark sequence registries, including `data/processed/prospective_dfl_holdout_dp94_v1/`.
  - Done when: `scripts/preflight_caid3_protected_training.py` and `scripts/check_detector_autoresearch.py` pass on the new split. The current split (`caid3_protected_dfl_v1`) is not used.
  - Blocker: the current split overlaps DP94. DP94 is a candidate, not an independently validated benchmark. Its label semantics are unverified.
  - Depends on: a chosen family clustering method. `MINING_RUN_SIZING.md` proposes MMseqs2 at 30% identity and 50% coverage for leakage control. That is a proposal, not a tested setting, and it is not yet decided whether it defines families.

- [ ] **B2. Conformal thresholds with abstention.**
  - What: implement conformal risk control (Learn then Test) for a precision target. Calibrate on a small clean protein-split calibration set drawn from B1's split. Report the abstention rate.
  - Done when: the threshold is calibrated on the calibration set only, the test set is untouched, and the coverage guarantee is stated with its assumptions (exchangeability is not met across proteins with shared family structure, so the guarantee holds only within B1's family-disjoint design).
  - Blocker: PR #1 has selective prediction with a binomial bound, not conformal risk control. It is an input, not a substitute.
  - Depends on: B1.
  - Integrity: the 0.90 operating point from current development data is not a guarantee and must not be called one.

- [ ] **B3. Adjudicated no-linker set.**
  - What: assemble proteins believed to contain no linker, with each one checked for absence of flexible linkers (manual or evidence-based adjudication). Keep it disjoint from B1 and from CAID3.
  - Done when: the set exists with per-protein evidence and adjudicator notes, and specificity can be measured on it.
  - Blocker: without this set there is no specificity claim, and therefore no mining claim. This is the most important blocked item after B1.
  - Depends on: B1 (for disjointness).

- [ ] **B4. Label-ceiling analysis.**
  - What: estimate how many apparent false positives are unannotated real linkers. Use the flagged residues from development and the known unknown-label inventory.
  - Done when: a count and its method are written up, with the uncertainty stated.
  - Depends on: P2, B1.

- [ ] **B5. Untouched test, opened once.**
  - What: freeze model, weights, thresholds, evaluator and competitor coverage. Then run the test set a single time.
  - Done when: the result is reported with raw counts, hashes and coverage, including negative results. `RESEARCH_HANDOFF.md` binding rule 4 applies.
  - Depends on: B1, B2, B3.
  - Integrity: a second test run requires a new benchmark. Do not reuse.

---

## BLOCKED: data and environment

- [ ] **E1. LinkerDB access.**
  - What: allow `www.ibi.vu.nl` (or `*.vu.nl`) in the environment allowlist. `ibi.vu.nl` alone redirects and fails at `zeus.few.vu.nl` with 403.
  - Done when: a bulk download of natural inter-domain linkers succeeds and its file hash is recorded.
  - Blocker: environment setting, changed by Dorya in Project settings.
  - Caveat: LinkerDB was last updated in 2002. Its size claims are a snapshot.

- [ ] **E2. Decide end-to-end versus internal insertion.**
  - What: Dorya answers the open decision card. Recommended: end-to-end (tandem).
  - Done when: the answer is recorded in `SPEC.md` section 9 and the calculator's Q2 scope is updated accordingly.
  - Blocker: only Dorya can answer.

- [ ] **E3. Li et al. 2026 access (optional).**
  - What: obtain the paper through a library or a mirror.
  - Done when: figures are read directly. Until then they stay permanently unverified and are not used as benchmark or comparison.
  - Blocker: captcha on PMC, robot block on ScienceDirect, no library access.

---

## CHEAP DECISIVE EXPERIMENTS (no wet lab, no generator)

These can run on existing mined or natural linker data. Each is publishable either way.

- [ ] **X1. Do Li et al.'s relative-position structural features transfer across domain pairs?**
  - What: Li et al. assert that relative-position structural features transfer across domain pairs and never test it. Test on natural linkers from LinkerDB (E1) or SynLinker-derived sources, grouped by domain pair, with features computed from AlphaFold DB structures.
  - Done when: a held-out-domain-pair result is reported with a baseline that uses sequence only, and with raw counts.
  - Depends on: E1 or another source of natural linkers with flanking domains.
  - Integrity: Li et al.'s own figures are not used. The test is on our own data.

- [ ] **X2. Does template retrieval reconstruct held-out natural linkers from flanking context?**
  - What: hold out natural linkers. For each, retrieve the closest linker from the template library (PR #2) using flanking domain context only. Measure sequence recovery and length error. Include a non-retrieval baseline (for example, the most frequent linker of matching length).
  - Done when: the retrieval result and baseline are reported with raw counts.
  - Depends on: E1 for natural linkers with flanking context. PR #2 for the library.
  - Integrity: a strong retrieval result collapses the generative contribution. Report it either way.

---

## Housekeeping (before any PR is merged)

- [ ] **H1. CI for the active branch.** Add `codex/dfl-research-handoff` to the `pull_request` branches in `.github/workflows/ci.yml`, and add a Python job running `python3 -m unittest discover -s tests` on Python 3.11. Do this in its own PR. Note: `tests/` is not a package, so discovery needs a path or an `__init__.py` fix (not investigated).
- [ ] **H2. Repo consistency.** Known issues a reviewer will find: `configs/detector_autoresearch_active.json` reports zero completed trials, which contradicts the 16 and 17 October rounds; a local Windows path appears in `reports/DFL_ANNOTATION_AND_CONTROL_TEST_2026-10-12.md`; LINKER-Pred checkpoints have no license at the pinned commits; both `.tex` drafts describe the design project while the evidence is for the detection project.
- [ ] **H3. Commit the frozen-score manifest.** Hashes and paths of frozen score files, so a clean clone can tell what is missing (ties to P0).
