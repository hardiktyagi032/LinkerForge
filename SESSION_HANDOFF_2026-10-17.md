# Session handoff — 17 October 2026

Read `RESEARCH_HANDOFF.md` first. This file records what a day of parallel research sessions
established, what was corrected, and what is still open. It assumes you have only this repository.

Companion artifact pages (same content, nothing here depends on them):

- Claims register: https://claude.ai/artifact/DVuSZKvmddaZUyY9bvWY8z
- Publication plan: https://claude.ai/artifact/NwQKGpHyCA1RseRQmRYzhh

## 1. Corrections to numbers that were circulating wrongly

**The field's best is not F1 0.38.** On the CAID3 common-27 intersection the strongest published
submission is IPA-AF2-Linker at APS 0.482 / AUROC 0.898 / Fmax 0.491. The published range across
seven released submissions is APS 0.097 to 0.482. Any plan stating the frontier as "roughly F1 0.38"
is wrong. The target of 90% recall at 99% precision (about F1 0.94) is still out of reach, but it is
out of reach because of the labels, not because the field is at 0.38.

**Chain extension bound is 3.8 Å, not 3.0–3.5 Å.** 3.0–3.5 Å per residue is a *design convention*.
The physical bound is the virtual Cα–Cα distance at 3.8 Å. Verified over 412 residues of real
committed structure: no window exceeded 3.8 Å per residue, and short extended segments routinely
exceeded 3.5 Å. Using 3.5 as a bound makes real protein segments look geometrically impossible.
This figure propagated through two literature surveys before anyone checked it against coordinates.
Tests pinning both halves of this are in PR #3. Any survey text, feasibility screen or figure that
used 3.5 Å as a limit needs revisiting.

The general failure mode is worth remembering: a number that is conventional in a design context
but physical in form does not announce which one it is, and nobody downstream re-derives it.

## 2. Integrity lines that must not slip

- **The precision-0.90 operating point is a selected threshold, not a guarantee.** It is chosen on
  the same development split it is then reported on, under the rule "max recall at empirical
  precision ≥ 0.90 with at least 50 true positives". Reporting it as a certified precision level
  would be this project's most likely integrity failure. A guarantee requires calibration on a set
  disjoint at family level, with the risk level and realised coverage both stated.
- **0.7918 and 0.241 are different quantities.** 0.7918 is mean development APS over seeds 7/17/31
  on 7,427 scored residues from 42 proteins, 68% of that split's residues masked unknown. 0.241 is
  CAID3 common-27 APS on 15,570 residues with no masking. They must never appear in the same table,
  and the development figure must never sit near published CAID3 columns.
- **CAID3 is spent.** Public, previously inspected in this project, scored once after a freeze
  manifest. It is retrospective. It cannot select a model, threshold, architecture or filter, and it
  cannot supply a superiority claim. If a reviewer asks for one more number on it, the answer is an
  explanation of why that number would be invalid.

## 3. The strongest measured result: mask policy dominates reported performance

With model scores frozen and only the evaluation mask changed, `x` (unknown) → `0` (negative):

| population | residues | prevalence | APS | AUROC |
|---|---:|---:|---:|---:|
| TE82 original 0/1 | 13,694 | 16.23% | 0.450 | 0.773 |
| TE82, `x`→`0` | 36,938 | 6.02% | 0.115 | 0.635 |
| TE82 linker-containing only, `x`→`0` | 21,767 | 10.21% | 0.144 | 0.558 |
| TE64 original | 10,256 | 9.25% | 0.214 | 0.664 |
| TE64 linker-containing only, original | 2,221 | 42.73% | 0.374 | 0.365 |
| TE64 linker-containing only, `x`→`0` | 28,096 | 3.38% | 0.038 | 0.469 |
| CAID3 common-27 | 15,570 | 7.80% | 0.089 | 0.542 |

ΔAPS −0.335, ΔAUROC −0.139 from the mask change alone. An inference-mode artefact was ruled out
separately: one-at-a-time versus padded-batch rescoring moves TE82 APS by 0.000631 (89 of 13,694
residues differ by more than 0.01).

**Say "a major measured cause", never "the cause".** The same data shows TE64 positive-protein
AUROC at 0.365, below chance, which mask policy does not explain.

**How to reproduce.** Source records are `reports/DFL_POOR_TRANSFER_CAUSE_AUDIT_2026-10-12.md` and
`reports/dfl_mask_policy_counterfactual_v2_2026-10-12.json`; the inference-consistency control is
`reports/dfl_inference_consistency_2026-10-12.json`. Both JSONs are committed. The frozen scores
they were computed from live under ignored `artifacts/`, so a clean clone can re-read the result but
cannot recompute it without re-obtaining the checkpoint and the split named in the report. If you
need to recompute: score the frozen checkpoint once, then vary only the mask applied at evaluation,
holding the score vector fixed. Masked fractions were TE82 63%, TE64 75%, CAID3 0%.

Supporting label-ceiling inventory, from `reports/DFL_LABEL_MASK_AUDIT_2026-10-12.md` and
`reports/disprot_dfl_label_masks_2026-10-12.json`: 329 DisProt proteins (the 31 CAID3 IDs excluded),
233,315 residues = 14,304 DFL positive, 1,209 candidate negative, **217,802 unknown (93.35%)**. Only
24 of 329 proteins carry any candidate negative, and DP04070 alone contributes 560 of 1,209 (46.3%).

## 4. Claims register — what can and cannot be said

### Supported

- **Mask policy dominates reported DFL performance.** Section 3 above. Quantified, with the
  software-artefact control. The project's best standalone result.
- **Disorder pretraining transfers for the SAM-like head and hurts YOLO-1D.** Twelve trials, three
  seeds: SAM-like 0.766 → 0.792; YOLO-1D 0.619 → 0.595.
  `reports/DFL_CAID3_PROTECTED_BASELINE_ROUND_2026-10-16.md`. Development only, and +0.026 APS on a
  split with known homology leakage is within what leakage can manufacture.
- **Large internal improvement over the project's earlier heads.** On identical common-27 residues:
  earlier CNN 0.089, span 0.085, precision-loss 0.087, SAM-like three-seed mean 0.076, YOLO-1D
  0.122–0.145, current frozen baseline 0.241. This is a progress claim, not a competitiveness claim.
- **The multi-tether feasibility answer is two-sided and each side is checkable.** A violated
  pairwise distance-geometry bound *proves* infeasibility; a returned placement is a witness an
  independent party can recheck; anything else returns `undetermined` rather than a guess. No
  threshold chosen, no split selected on, does not inherit the annotation ceiling. This is the only
  provable rather than tuned claim in the project and is worth treating as the standard. Its
  boundary belongs in the same sentence: geometric admissibility is necessary, not sufficient.

### Scope-limited

- **Development APS 0.7918** carries three caveats every time it appears: the split was selected on;
  15,541 of 22,968 development residues are masked unknown; the split manifest status is literally
  `sequence_screened_not_full_homology_certification`, so it is not family-disjoint.
- **Apparent false positives include unannotated real linkers** — directionally supported, not
  established. For it: the 93.35% unknown inventory, and 17.3% of TE82 / 39.5% of TE64 unknown
  residues scoring above 0.5. Against it: the one blinded crosswalk is uninformative — 1 of 20
  model-nominated unknowns matched a curated linker versus 0 of 10 random unknowns, Fisher two-sided
  p = 1.0; only 5 of 10 published positive controls were recovered, so the DisProt extract is an
  incomplete adjudicator; and the single match was already annotated in release 2022_03, so there is
  no "annotation appeared later" story. Needs a powered adjudication of a few hundred nominated
  unknowns against a source that is not the annotation set being audited.
- **One real specificity control**: 20 published-label controls (10/10), AUROC 0.81, AP 0.849 against
  chance 0.50 — but drawn from TE82, which was used for selection, so not a generalization test.
- **DLD supplies ~2,600 structure-derived linkers** — 2,620 usable chains, real training run on it
  (ESM-2 35M validation AUPRC 0.3998, one-time fold-5 AUPRC 0.3805). But its labels are structural
  IDL/DDL, not DisProt-style DFL, code `0` is undefined on the source page, and measured DLD→DFL
  transfer on the full CAID3 reference is APS 0.164. It enters as a separate masked head, never
  pooled into DFL ground truth.
- **The mined linker dataset would be a real contribution.** A 2026 competitor states in print that
  publicly available linker datasets are virtually nonexistent, which is stronger support for the
  gap than this project asserting it. Gated behind everything in section 5.
- **SynLinker is a novelty blocker to address head-on, not in a rebuttal.** It already designs
  linkers for two uploaded domain structures from 2,150 natural plus 110 artificial linkers,
  filtering on length, end-to-end distance, solvent accessibility, composition and proteolytic sites.
  Row-level data has never been obtainable here, so the baseline cannot currently be run — say that
  rather than implying it was reproduced.

### Unsupported

- **"LinkerForge detects DFL residues better than published methods."** Already falsified on the only
  equal-coverage comparison run: APS 0.241 against 0.369–0.482 for six published methods, second from
  last of eight.
- **"90% recall at 99% precision."** Best in-repo operating point is recall 0.6433 at empirical
  precision 0.90, on a selected-on development split with 68% masked residues. The label ceiling
  blocks this independently of any model.
- **Span recovery.** Region recall at IoU ≥ 0.5 swings between 0/28 and 15/28 across runs of the same
  model family, and every bounded-span decoder tried scored below the residue baseline (0.4607–0.4958
  against 0.7913). A metric moving 0 to 15 of 28 under reseeding supports nothing in either direction.
- **"The model rejects no-linker proteins."** The only instrument is a 17-protein proxy whose
  granularity is 1/17 = 0.0588 against a preregistered 0.02 guardrail — the guardrail means "not one
  more false-positive protein". Those 17 are published TransDFL negatives, never adjudicated; median
  fraction of their residues explicitly labelled negative is 0.722, minimum 0.402. CAID3 contains no
  no-linker proteins at all.
- **A family-disjoint split.** Does not exist. No CD-HIT or MMseqs2-style clustering has been run.
- **DP94 as an independent held-out benchmark.** 88 of 98 proteins connect to 148 existing train,
  development or auxiliary proteins; registry status `candidate_not_certified_independent`; preflight
  fails closed.
- **Mining at scale.** Million-scale run not begun; annotated catalog marks zero records
  training-ready; the 113,285-sequence discovery index is stamped
  `discovery_only_not_training_labels`; of 14,011 UniProt region notes containing "linker", only 57
  observations carry PubMed-linked evidence codes.
- **A design dataset.** The 91-record pilot has every record marked uncertain with review pending,
  *no* record with a fully resolved linker interior, and 57 CATH architecture proxies rather than
  homology clusters. Its own gate report says publication-directed training must not run on it.
- **Three or more simultaneous linkers between the same two domains as unprecedented.** Two
  connection points are established practice in GPCR crystallography fusions. No precedent was found
  for three or more, but that is a negative search result and the crosslink and staple literature was
  not searched. Unverified, not open. Do not write "first" near this.
- **A curated template library as a contribution.** SynLinker built one in 2015 with those exact
  filters. Only the learned pair-specific part survives as a claim.

### Unsupportable, or methodologically inverted

These are not matters of more work.

- **"Predicts whether a fusion construct will work."** The best zero-shot predictor that a designed
  construct folds and expresses is ESMFold pLDDT at AUC 0.73 across 614 designs; combining every
  available metric reached 0.74. Solubility predictors top out near MCC 0.46, on natural *E. coli*
  proteins rather than chimeras. No published dataset maps fusion constructs to expression outcomes
  at all. Present as flags, named as flags — never a success probability, and never a phrase in an
  abstract a reader converts into one. This is the claim most likely to drift in unchallenged.
- **Scoring flexible linkers by structural confidence.** Low pLDDT *is* the disorder signal — CAID
  uses one minus pLDDT as a disorder predictor — so confidence filtering systematically rejects the
  correctly disordered linkers. Self-consistency RMSD fails differently: it needs an intended
  backbone, and a flexible linker has no single conformation. What *is* checkable in silico: that a
  rigid linker is actually helical, and that both domains retain their folds. What is not checkable
  without a wet lab: that the fusion works. State that boundary rather than leaving it inferred.
- **Domain compatibility has no negative class.** Natural fusions record only pairs that worked, and
  randomly shuffled pairs are trivially separable on composition and phylogeny. Pick a ranking
  formulation or a published hard-negative construction rule *before* training, not after seeing
  numbers.
- **Breadth does not substitute for labels.** Mined natural linkers carry no functional readout; the
  2026 competitor has 370 measured 18-mers with fluorescence and expression, in one construct, one
  domain pair, one length. Narrow but labelled. You can claim a generated linker is novel and
  structurally plausible. You cannot claim it is better than a SynLinker retrieval, because there is
  no readout on this side to say it with.

## 5. Publication plan

**Two papers, in this order.** Paper I depends on nothing that is blocked; Paper II cannot be written
yet. The reverse order fails twice: Paper II has no results, and attempting it first puts the project
back in the position of needing a number from a benchmark it has already spent.

### Paper I — writable now

A benchmark-and-methods analysis of the DFL detection task. No new method, and the abstract says so
rather than hinting at a model the project does not have.

Venue: a bioinformatics methods venue (*Bioinformatics*, *BMC Bioinformatics*, *NAR Genomics and
Bioinformatics*), or a benchmark/datasets track. Not an ML main track, where "no new state of the
art" reads as a rejection reason rather than the point. The `neurips_2026_author_kit/` in this repo is
unmodified and its checklist untouched, so a NeurIPS submission is format work from zero; do not let
the kit's presence decide the venue. The project's own charter names methods/benchmark analysis as
the honest scope absent a fresh adjudicated test.

Contribution, in order of strength:

1. Equal-coverage reanalysis of the CAID3 linker task. The published comparison mixes coverage
   levels (one leader at 90.3%, others at full). The strict full-residue intersection of the seven
   released submissions is 27 proteins, 15,570 residues, 1,214 positives, scored over identical
   residues with the official evaluator. Hashes and the pinned evaluator commit are on record.
2. Mask policy dominates reported performance (section 3).
3. The annotation ceiling, as an inventory (section 3). Keep this separate in the text from the
   "our false positives are real linkers" sentence, which is not supported yet.
4. A modality audit of the leaders: the LINKER-Pred family requires MSA or ProtTrans representations
   at inference and is not sequence-only; the strongest submission is AlphaFold-informed. The
   published ranking is partly a ranking of input budgets.

LinkerForge appears in the table as a participant at 0.241, with no softening — plus the measured
DLD→DFL transfer failure at 0.164 and roughly ten negative ablations, which are reportable results in
a paper of this kind.

Exhibits needed, and where the data already is:

| # | Exhibit | Source | State |
|---|---|---|---|
| T1 | Equal-coverage comparison, seven predictors plus LinkerForge | `reports/caid3_common_coverage_2026-10-11.json` | data ready |
| T2 | Published versus equal-coverage scores | CAID3 paper figures plus T1 | data ready |
| F1 | Mask-policy counterfactual, scores frozen | `reports/dfl_mask_policy_counterfactual_v2_2026-10-12.json` | plot to draw |
| F2 | Annotation inventory per protein | `reports/disprot_dfl_label_masks_2026-10-12.json` | plot to draw |
| T3 | Input-modality matrix | `reports/track-competitors/*` | needs tabulating |
| T4 | Negative-results ledger | dated round reports, 9–17 Oct | scattered, needs one table |
| F3 | Score distribution over unknown versus labelled residues | frozen scores | needs one short analysis |
| T5 | Reproducibility appendix: hashes, evaluator commit, checkpoint SHA-256s | freeze manifests | assemble only |

**No figure exists as a file anywhere in this repository, and there is no plotting code at all.** The
two "figures" in `paper/LinkerForge_Preliminary_Study.tex` are LaTeX `\rule` bars. Every exhibit above
is a plot still to be written from JSON that already exists. Small, well-defined, and on Paper I's
critical path.

Related-work positioning: IPA-AF2-Linker (AlphaFold structures, APS 0.482 — report as a richer-input
class, and note it has the largest missing coverage of the seven); LINKER-Pred2/Lite/Pred (ProtTrans,
plus MSA-Transformer for Pred2 — not sequence-only, which is the modality finding and not an excuse);
DisoFLAG-DFL (sequence-only ProtT5, APS 0.409 — the genuinely matched-input comparator and therefore
the one the project is most clearly behind; say so directly); APOD (170 features including
conservation, secondary structure, RSA — its own published ablation shows conservation is the
strongest single group, which argues what a sequence-only ESM-2 system is missing using their numbers,
not ours); TransDFL (52-dimensional profile features, never run here — say it was not reproduced);
DFLpred (at chance on the common 27, keep as the historical floor); IDPFunNet (post-dates CAID3 and is
absent from the archive, so this is not a census of published methods — state that limitation).

### Paper II — gated

A certified high-precision caller plus the mined linker set. Abstention is the feature, not the
compromise: precision at the coverage mining would actually use is the quantity the design model
needs, and headline APS is not.

Prerequisites, in order:

1. A family-disjoint split that passes the preflight.
2. A clean calibration set. Conformal risk control inherits its guarantee from calibration labels; 68%
   of development residues are unknown and unknown may not be relabelled negative. Write down the
   risk level the set's size can honestly certify *before* building it.
3. Risk control implemented (Learn-then-Test or conformal risk control with abstention).
4. An untouched test, and adjudicated no-linker proteins. Without this there is no specificity claim
   and therefore no mining claim.

**Do not start drafting Paper II until step 1 passes.** Drafting creates pressure to produce the
number the draft is shaped around, and that pressure is how a spent benchmark gets touched again or a
tuned threshold gets called a guarantee.

Pre-commit to the honest outcome: certification can succeed and still disappoint, if the certified
precision is only reachable at a coverage too low for mining to be worth doing. That is a publishable
result, and agreeing so now is cheaper than discovering it and looking for a different metric.

### The design model — not a paper yet

Run the gate first: hold out natural linkers and check whether a template or retrieval library
reconstructs them from the flanking domains alone. If retrieval does well, a generative model has
little room and the contribution needs reframing before anything is built. Days of work; could
redirect months.

Strongest available design claim is attachment-site prediction. Nothing published takes two domains
plus a linker specification and returns attachment points, and the labels come free from mined
linkers because residues flanking a natural linker tolerate one by definition. It needs a
geometry-only baseline and a retrieval baseline beaten explicitly — terminal geometry alone predicts
a great deal about where a linker can go.

## 6. Draft PRs open against this branch

All three are drafts, all based on `91374ed`, none merged.

- **#1 `claude/dfl-high-precision-toolkit`** — nnPU/uPU residue loss (config `class_prior` null so the
  launcher refuses to run), one-member-at-a-time ensemble scoring that refuses non-development splits,
  a selective-prediction threshold chosen by an exact Clopper-Pearson lower bound on precision, a
  fail-closed AlphaFold feature loader and span decoders. 43 CPU tests pass, 2 skipped (no torch). The
  torch loss, launcher wiring and ensemble CLI are *not* verified, and `unittest discover` fails on
  import because `tests/` is not a package. Note for the register: this is selective prediction with a
  binomial confidence bound, which is not conformal risk control — the bound is residue-level and
  therefore optimistic, and the labels are incomplete so measured precision is itself a lower bound.
- **#2 `claude/linker-property-library`** — 30-entry curated linker property library with a JSON Schema
  that structurally forbids fabricated sequences, plus cleavability lookup and a rigidity classifier.
  28 tests. Its own substantive finding is that the literature treats cleavability as a third category
  parallel to flexible and rigid rather than an orthogonal axis. States plainly that it is not a
  contribution (SynLinker prior art) and claims no calibration (13 labelled entries).
- **#3 `claude/linker-geometry-feasibility`** — deterministic geometry feasibility calculator, standard
  library only, runs on the 6 GB laptop. 80 tests. Carries the 3.8 Å calibration and the two-sided
  multi-tether logic described above.

A fourth draft was mentioned in coordination but is not listed as open on the repository as of this
writing; `gh pr list --state all` will say whether one exists elsewhere.

## 7. Still open

- **No family-disjoint split.** The central blocker. No clustering tool has been run; the preflight
  fails closed and no new DFL training on `data/processed/caid3_protected_dfl_v1` is authorized.
- **No conformal prediction in the repository.** PR #1 adds selective prediction with a
  Clopper-Pearson bound, which is adjacent but is not a risk guarantee.
- **No adjudicated no-linker set**, so no specificity claim, so no mining claim.
- **LinkerDB unreachable.** The resource is live and offers bulk downloads of natural linkers split by
  helicity, but this container's egress allowlist denies the host; an allowlist fix for
  `zeus.few.vu.nl` (also recorded as `ibi.vu.nl` in PR #2) is needed. Note its helicity axis is not the
  same as engineered rigid/flexible design intent.
- **Li et al. 2026 (Synth Syst Biotechnol 13:362–375) is permanently unverified here.** PMC is
  captcha-walled, ScienceDirect blocks automated access, and Dorya has no library access. Only the
  author version up to partway through Results was readable. That includes its ablation on whether the
  structural module beat sequence alone, which bears directly on this project's own structure-features
  decision. Do not cite its results from a summary. What *is* established about it: it is a scorer, not
  a generator — ProtT5 embeddings plus AlphaFold Cα distance features into an MLP predicting
  fluorescence and expression, no generation step, no property switches, no protease-site handling, and
  a wet-lab test on randomly picked colonies rather than model-designed linkers. It does not take the
  design niche; it takes the ability to claim superiority without measurements.
- **End-to-end versus internal insertion is unanswered.** Which regime the design work targets changes
  the geometry, the label source and the relevant prior art, and nothing has decided it.
- **Multi-tether novelty unverified.** The crosslink and staple literature was not searched.
- **SynLinker row-level data never obtained** (server unreachable), so that baseline cannot be run.
- **Repository hygiene a reviewer will find first.** `configs/detector_autoresearch_active.json` points
  at a ledger reporting zero completed trials and zero GPU hours, contradicting the 16–17 October
  rounds, while being labelled the project's current machine-readable status. A local Windows path is
  embedded as a link in `reports/DFL_ANNOTATION_AND_CONTROL_TEST_2026-10-12.md`. The LINKER-Pred
  checkpoints have no license file at the pinned commits, which blocks any artifact release that
  redistributes them.
- **Two divergent objectives in one repository.** Both `.tex` drafts belong to the fusion-design
  project; all the publishable evidence belongs to the DFL-detection project. Resolve this in the
  repository before submitting anything, so an auditing reviewer does not have to work out which
  project the paper is.
