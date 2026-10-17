# Components 2–5: software readiness, 18 October 2026

The human requested all work after component 1, without data generation or
scientific fitting. This checklist concerns **implemented, tested software**.
It does not sign off scientific results or team review. The older detector and
publication checklist in `CHECKLIST.md` remains intact.

| Order | Software item | Evidence |
|---|---|---|
| [x] 1 | Scope and preserve existing work | Isolated `codex/design-pipeline-readiness`, stacked on attachment PR #10 and generator PR #9; detector, data and prior model checkouts preserved. |
| [x] 2 | Define the future mining-to-training boundary | `pipeline/intake.py`, `review-candidate`; exact source/span/flank/model/calibration identities; output remains predicted and training-ineligible. No mining execution or tolerance labels. |
| [x] 3 | Reuse geometry and source-library properties | Existing geometry solver and cited templates; `assess-geometry` checks files and explicit residue maps; all contacts share one placement problem. No altered physical constants. |
| [x] 4 | Site model, tasks, loss, frozen features and checkpoints | PR #10, `ATTACHMENT_SITE_MODEL.md`, site MLP and linear configs; insertion/terminal tasks and unknown masks remain separate. |
| [x] 5 | Explicit count/contact/topology architecture | `pipeline/routes.py`; tandem, insertion and explicit multi-contact routes, operation-level site scores, exact sequence assembly/mapping, direct-fusion control. Count is derived from the supplied route, not predicted as optimal. |
| [x] 6 | Conditional sequence model, adapters and training loop | PR #9, `FUSION_GENERATOR.md`; native causal FIM, local compatible LM/LoRA interface, exact length/cassette controls, resumable trainer. Optional protein backbone assets still require selection/review. |
| [x] 7 | Connect models, geometry, properties and assembly | `pipeline/design.py`; bounded plans/proposals/assemblies, unknown site/geometry states, complete attempts and final cross-junction motif screen. Internal-fragment FIM transfer is explicit opt-in and unvalidated. |
| [x] 8 | Future data/feature/split handoff and launch setup | Existing private generator/site loaders; `DESIGN_PIPELINE.md` lists exact required files. `prepare-training` writes nine immutable seed configs and unsigned receipts; missing inputs block launch. |
| [x] 9 | Execution, resource and failure controls | `pipeline/training.py`; aggregate reservation, one host/account lock across rounds, exact execution receipt, child PID/logs, hard timeout, checksum-verified completion, no overwrite/automatic retry. Remote jobs remain unverified. |
| [x] 10 | Matched development benchmark paths | Site MLP/linear/uniform/proximity and reviewed external-score interface; generator frequency/training-only context retrieval/optional exposure-reviewed source library; full/common counts and paired family uncertainty. `benchmark-commands` retains every requested seed. |
| [x] 11 | Scoped verification and packaging entry point | `scripts/verify_design_architecture.py`; `linkerforge-design` entry point; dated evidence under `reports/pipeline-readiness-2026-10-18.*`. Existing model regressions use invented fixtures only. |
| [x] 12 | Scoped CPU CI configuration, separate review increment | `design-python.yml`: standard-library geometry on Python 3.11, model wiring on Python 3.14 CPU, exact action revisions, timeouts/offline weights/report artifacts; active PR branches enabled. Hosted outcome is recorded separately and is not college-cloud or reviewer approval. |

Still required before scientific execution:

- [ ] Independent team review of these draft code changes, shared-contract
  decisions, and the observed hosted CI outcome.

- [ ] Traceable, reviewed generator data and donor-aggregated site supervision,
  including genuine negative controls; mined flanks do not supply tolerance labels.
- [ ] Complete exclusion registries and audited family-disjoint train/development
  splits, with target/evidence semantics approved. Detector benchmarks remain protected.
- [ ] Actual encoder assets/caches, any optional pretrained protein LM and licence
  review; approved institution cloud image, resources and exact execution receipts.
- [ ] Reviewed topology, input-information, benchmark/exposure and structural
  validation protocols. No independent labels are opened by these tools.
- [ ] Real three-seed training and matched development results; later frozen
  independent comparison and structural validation. No function/efficacy claim yet.

These unchecked items cannot be completed with invented data. Actual UniProt
mining, new labels, detector changes, data scaling, structural jobs and a trained
optimal-count/function model are outside this code-only increment.
