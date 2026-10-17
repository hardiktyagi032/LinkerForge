# Attachment model readiness — 18 October 2026 (Asia/Calcutta)

The human requested component 4: attachment/contact point identification with
training and benchmarking ready before data exists. The generator was first
committed and published in [draft PR #9](https://github.com/richennacht/LinkerForge/pull/9),
commit `7a4ccc2cf87a3cba6fb54ba5539a08ddb48511ce`. Implementation here is isolated
on `codex/attachment-site-scorer`, based on that commit and the merged architecture.
No other worktree was reset or edited. No release or scientific result is merged.

The model, training loop, benchmark harness and geometry adapter are executable.
See [ATTACHMENT_SITE_MODEL.md](../ATTACHMENT_SITE_MODEL.md) for the architecture,
input proposal and exact future commands. This is a reviewable implementation
awaiting data, peer review and an actual approved execution environment.

## What changed and why

Frozen per-residue ESM features feed a shared small MLP, applied independently
to each domain. Separate internal-insertion and N/C-extension channels prevent
label transfer between different operations. Unsupervised channels remain
unassessed. The trainer uses masked record-balanced BCE, with true unknowns
excluded and explicit positive/negative evidence required per fitted task.
Natural linker-flank observations are not accepted as tolerance ground truth.

Connection count follows supplied tandem/insertion topology, with one/two
peptide connections, rather than an untrained count classifier. Both insertion
connections share a donor placement. An adapter validates sequence-to-PDB anchors
and delegates to the existing bounded geometry calculator. Infeasibility,
observed clash, witness and undetermined results retain their meanings.

Benchmarking is task-stratified with uniform, terminal-proximity and trainable
linear controls, optional versioned/exposure-reviewed peer scores, conservative
coverage ties, attempted/common coverage and paired family-component bootstrap.
Unknown labels or failed outputs cannot silently improve full-coverage claims.
No final blind benchmark reader or automatic threshold tuning was introduced.

## Actual software verification

| Check | Observed outcome |
| --- | --- |
| Attachment tests | 28 passed in 10.772 seconds |
| Generator regressions | 31 passed in 8.964 seconds |
| Existing geometry regressions | 80 passed in 1.846 seconds |
| Synthetic smoke | Four invented sequences represented by 12 task records: 6 train, 6 development; 3 CPU updates; seed 17; 195 fitted parameters |
| Smoke counts per split | 4 invented positives, 4 negatives, 16 unknown annotation positions across task records |
| Smoke ceiling/outcome | One CPU thread, 3 updates, 120 seconds; completed in 1.535 seconds measured trainer wall time |
| Checkpoint resume | Four steps with dropout matched two-plus-two resumed steps exactly in weights/history |
| Frozen encoder path | Tiny local randomly initialized ESM fixture verified special-token removal, freezing, local asset loading and mutation detection; no ESM-2 3B download |
| Geometry adapter | Synthetic coordinates verify explicit numbering and a two-tether necessary-condition failure; existing fixture regressions also pass |
| CLI | Smoke, task-separated benchmark-development and single-domain score commands completed; synthetic flags retained |
| Packaging | Wheel built; contents and extracted CLI checked in machine-readable evidence |

All fitting/model metrics here use invented software fixtures. Existing geometry
regressions use the repository's committed test structures; no new structures,
labels or model weights were acquired. No real-data fit, scientific benchmark
rescore, large embedding job, cloud training, paid provisioning or weight
promotion occurred. No biological performance or uncertainty calibration is
claimed. External ProDomino weights/scores were not loaded or executed.

The borrowed read-only CPU runtime is CPython 3.14.7, torch 2.14.1+cpu,
Transformers 5.20.1, safetensors 0.8.0 and NumPy 2.5.4. It does not verify the
college-cloud GPU environment. Detailed hashes, counts, seeds, commands and
resource evidence are in [attachment-readiness-2026-10-18.json](./attachment-readiness-2026-10-18.json);
raw logs and synthetic artifacts remain under ignored `tmp/attachment-verification/`.

## Research design and unresolved gates

Hypothesis: frozen domain residue context plus a small operation-specific head
may rank tolerance beyond position-only and linear controls on unseen families.
The first controlled comparison changes only linear versus MLP head with the
same encoder, masks, split, optimization/compute budget and seeds 7/17/31.
`configs/attachment-benchmark-plan.json` records the draft. No biological decision
can be made from these software tests; no favourable seed or architecture was
selected. Preserve failure if an apparent gain disappears under linear controls,
matched coverage, family uncertainty or correct endpoint semantics.

Still required: reviewed endpoint/donor-aggregation/negative evidence definitions;
traceable tolerance examples; full protected sequence registries and audited
family-disjoint splits; a real immutable frozen encoder asset identity; official
peer licensing/position/exposure checks; approved cloud/environment/resources;
and a frozen independent benchmark protocol before label reveal. The benchmark
coverage fraction, data and approval fields deliberately remain null in the pilot
plan. Detector labels/spent comparisons are not insertion-tolerance data. There
is no optimal-tether-count or fusion-function target to train at present.

## Source-level findings

- [ProDomino author MLP source](https://github.com/Niopek-Lab/ProDomino/blob/e0762470a27a5804a5c96c44d6e923bc21ee13f6/src/ProDomino/models/base.py)
  and [inference source](https://github.com/Niopek-Lab/ProDomino/blob/e0762470a27a5804a5c96c44d6e923bc21ee13f6/src/ProDomino/inference/inference.py)
  verify the frozen ESM-2 3B/layer-36 interface and `2560→1280→1` head. The new
  code implements the general architecture with separate endpoints; it does not
  reproduce the original predictor or claim its accuracy. Source licence is
  CC BY-NC 4.0. The publisher article was inaccessible; source-reported numerical
  handoff claims were not adopted.
- [The Kir2.1 paper](https://www.nature.com/articles/s41467-021-27342-0) supports
  keeping donor-dependent expression assays distinct from general function and
  requiring an explicit aggregation target. No assay rows/cutoffs were imported.
- [Official ESM configuration](https://huggingface.co/facebook/esm2_t36_3B_UR50D/blob/main/config.json)
  and [API documentation](https://huggingface.co/docs/transformers/en/model_doc/esm)
  support the reference dimensions and extraction interface, not cloud readiness.
