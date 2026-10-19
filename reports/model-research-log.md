# Model research log

## 18 October 2026 — separate scoped CI increment (Asia/Calcutta)

After draft pipeline PR #11 (`ba2497964e4e5dc8e086d137c2bf7b95cf4d6cad`),
implemented the code-only part of legacy H1 in a separate branch. Added scoped
geometry/Python 3.11 and Windows CPU model/Python 3.14 jobs; active PR bases;
exact action revisions; offline model loading, report artifacts and timeouts.
No detector suite, scientific job, new labels or model downloads. Existing 165
scoped tests were not needlessly rerun for YAML/docs-only changes.

Read official setup-python documentation; verified v7 action tag SHAs via
`git ls-remote` and the matching torch 2.14.1+cpu cp314 Windows wheel in the
official CPU index. Parsed YAML with `yaml.BaseLoader`, asserted jobs, branches,
contents-read permission, timeouts, offline flags and 40-character action SHAs;
all checks and `git diff --check` passed. Exact workflow hashes and supported
source links are in `reports/design-ci-readiness-2026-10-18.json` and its guide.
Hosted outcome is pending publication, not inferred from local verification.
Legacy full-detector H1 and independent team/cloud review remain pending.

## 18 October 2026 — components 2–5 code readiness (Asia/Calcutta)

**Scope.** The human requested all architecture/training preparation after
component 1 without data generation. Isolated from attachment PR #10 commit
`f037238f756622d5df947ebcc279629a155fab34`; preserved detector/data/model worktrees.
No detector change, mining, new scientific data, real fitting or cloud job.

**Hypothesis/decision.** Explicit chain routes plus the existing common-placement
solver can connect site scores and bounded sequence proposals without treating
multiple tethers as independent tandem fusions. Three- and five-contact fixed
fixtures verify sequence preservation/operation mapping. Final assembly screening
rejects motifs spanning more than one junction. Direct fusion remains separate;
fragment-context FIM reuse remains explicit, unvalidated opt-in. No optimal-count
or fusion-function model/labels are invented.

**Training/comparison setup.** Nine planned jobs: site MLP, matched linear
control and native FIM, seeds 7/17/31, 16,200 reserved child seconds under the
six-hour ceiling, one dispatcher's host/account lock. Every job is blocked by
missing reviewed data/round reference. Receipt/config/input/source checks,
timeout, failure retention and checksum-bound completion are implemented; mocked
children test execution controls. Benchmark argv retain every requested seed.
Generator development comparison now adds full/common coverage and paired family
intervals; frequency/training-only retrieval and optional exposure-reviewed library
remain controls. No biological comparison, calibration or benchmark reveal occurred.

**Files/evidence.** `src/linkerforge/pipeline/`, generator benchmark/helper and
CLI changes, shared family grouping, two scripts/two configs, packaging entry,
26 new tests, `DESIGN_PIPELINE.md`, `DESIGN_READINESS_CHECKLIST.md`, dated readiness
MD/JSON; README/AGENTS/CHECKLIST scope notes. Shared schemas/default models intact.
Sources: [architecture PR #7](https://github.com/richennacht/LinkerForge/pull/7),
[generator PR #9](https://github.com/richennacht/LinkerForge/pull/9),
[site PR #10](https://github.com/richennacht/LinkerForge/pull/10); these establish
component interfaces, not biological efficacy of the new orchestration.

**Validation.** Exact commands, source/input/artifact hashes and raw counts are
in `reports/pipeline-readiness-2026-10-18.json` and its MD companion. Ran
`python scripts/verify_design_architecture.py --scope all --output tmp/pipeline-verification/tests.json`:
165 tests passed, no failures/errors/skips, 17.461 seconds. Existing optimizer
regressions use invented fixtures; the new FIM integration uses random untrained
weights, with no fit. Actual prepare/design/geometry/development-command CLIs
ran on labelled software examples. Two toy-coordinate reports connected to two
design plans (one/three connections); one template assembly each. Wheel built,
78 source files matched, ignored assets absent, extracted-wheel CLI worked,
`git diff --check` passed. CPython 3.14.7, torch 2.14.1+cpu, Transformers 5.20.1,
safetensors 0.8.0, NumPy 2.5.4; existing borrowed CPU runtime, not cloud verification.

**Next.** Publish review increments and add scoped CI in its own PR (legacy H1).
Then obtain reviewed data/assets/exclusions/splits/target semantics and actual
institution-approved execution evidence. Team review and scientific results
remain pending. Local scientific jobs launched: zero; remote jobs unverified.

## 18 October 2026 — attachment sites, topology and benchmark implementation (Asia/Calcutta)

**Instruction and source state.** The human requested publishing the generator,
then implementing component 4 without data. Generator commit
`7a4ccc2cf87a3cba6fb54ba5539a08ddb48511ce` is on GitHub in draft PR #9.
The local Git credential's push was denied for another account; the connected
repository owner's GitHub API published the identical verified Git tree.
No credentials were changed. PRs #2–#7 are now merged on the active architecture
branch. Created isolated `codex/attachment-site-scorer` from the generator commit.
The direct instruction authorizes code/testing, not scientific fitting or release.

**Hypothesis and design.** Frozen ESM residue embeddings and a small domain-wise
MLP may support attachment tolerance beyond linear/position controls on new
families. The implementation separates internal insertion from N/C extension;
natural linkers are not automatically tolerance labels. Unknown positions are
masked, not negatives. Label endpoints require a reviewed donor-aggregation
policy, since a single-domain model cannot represent arbitrary donor interactions.
Connection count is explicit topology (one tandem connection or two insertion
connections), tested by the existing geometry engine rather than a fabricated
count predictor. Comparators, seeds 7/17/31, null data/coverage/approvals, limits
and a falsification rule are in `configs/attachment-benchmark-plan.json`.

**Primary evidence.** ProDomino code at
`e0762470a27a5804a5c96c44d6e923bc21ee13f6`
([MLP](https://github.com/Niopek-Lab/ProDomino/blob/e0762470a27a5804a5c96c44d6e923bc21ee13f6/src/ProDomino/models/base.py),
[inference](https://github.com/Niopek-Lab/ProDomino/blob/e0762470a27a5804a5c96c44d6e923bc21ee13f6/src/ProDomino/inference/inference.py))
verifies ESM-2 3B/layer-36 and the two-layer head. Its weights/code were not
executed/copied; licence is CC BY-NC 4.0. The Nature Methods page could not be
retrieved, so no unverified handoff accuracy figures were adopted.
[Kir2.1 original research](https://www.nature.com/articles/s41467-021-27342-0)
supports the donor/endpoint distinction. [Official ESM model configuration](https://huggingface.co/facebook/esm2_t36_3B_UR50D/blob/main/config.json)
and [API docs](https://huggingface.co/docs/transformers/en/model_doc/esm) support
the extraction interface/dimensions. These motivate design, not biological efficacy.

**Files.** Added `src/linkerforge/attachment/` (head, frozen cache/data preflight,
ESM extraction adapter, trainer/resume, benchmark, topology/geometry plans, CLI),
entry script, MLP/linear configs, frozen-pilot draft, 28 software tests, runbook
and readiness evidence. Updated README/AGENTS and packaging entry point. No shared
schema, detector/source labels, scientific threshold or existing geometry constant
was changed. Generator source remains unchanged.

**Exact verification commands.** In `LinkerForge-attachment`, use
`$attachmentPython = 'C:/Users/saubh/Documents/ChatGPT/Research/LinkerForge-models/.venv/Scripts/python.exe'`
and set `PYTHONPATH` to this checkout's `src` for unittest. `$attachmentUv` is
`C:/Users/saubh/Documents/ChatGPT/Research/LinkerForge/.venv/Scripts/uv.exe`.
TMP/TEMP and UV_CACHE_DIR were inside this checkout's ignored `tmp` directory.

```powershell
& $attachmentPython -m unittest discover -s tests -p test_attachment_sites.py -v
& $attachmentPython -m unittest discover -s tests -p test_fusion_generator.py -v
& $attachmentPython -m unittest discover -s tests -p 'test_linker_geometry_*.py' -v
& $attachmentPython scripts/attachment_site_model.py smoke --output tmp/attachment-verification/smoke-complete
& $attachmentPython scripts/attachment_site_model.py benchmark-development --manifest tmp/attachment-verification/smoke-complete/fixtures/manifest.json --checkpoint mlp=tmp/attachment-verification/smoke-complete/training/step-000003 --coverage-fraction 0.5 --bootstrap-draws 20 --seed 17 --synthetic-smoke --output tmp/attachment-verification/cli-benchmark.json
& $attachmentPython scripts/attachment_site_model.py score --checkpoint tmp/attachment-verification/smoke-complete/training/step-000003 --sequence-json tmp/attachment-verification/sequence.json --embedding $scoreInput.path --embedding-sha256 $scoreInput.sha256 --output tmp/attachment-verification/cli-domain-scores.json
& $attachmentUv build --wheel --python $attachmentPython --out-dir tmp/attachment-verification/dist
& $attachmentPython tmp/attachment-verification/verify_artifacts.py
# With PYTHONPATH set to tmp/attachment-verification/wheel-extracted:
& $attachmentPython -m linkerforge.attachment --help
git diff --check
```

`$scoreInput` is recorded in `tmp/attachment-verification/score-input.json`;
the sequence is an invented development string. This is CLI wiring only.

**Outcomes and raw counts.** 28 attachment tests passed in 10.772 seconds;
31 generator regressions in 8.964 seconds; 80 existing geometry regressions in
1.846 seconds. Four-step versus two-plus-two resumed optimization with dropout
matched weights/history exactly. Tiny random local ESM validated frozen
extraction and asset hashes without a network model download. Synthetic smoke:
6 train/6 development task records over four invented strings, each split with
4 positive/4 negative/16 unknown label positions; seed 17; 3 updates; 195 head
parameters; one CPU thread, 120-second ceiling, measured trainer time 1.535
seconds. All three operation outputs and task-stratified benchmark/CLI paths
executed with synthetic flags. No metric is reported as biological performance.
Pinned CPU runtime and input/source/artifact hashes are recorded in the readiness
JSON. Tests were rerun after cache/endpoint/metadata integrity additions; no
unchanged biological experiment was repeated.

**Decision and next work.** Publish the isolated component for review. The working
model/trainer and development benchmarks await data; no biological training,
blind reveal, cloud job, paid compute or weight promotion occurred. Next: review
endpoint/negative evidence/donor aggregation; provide audited family-split
tolerance examples and full exclusion registries; verify approved encoder/cloud
assets and official comparator exposure/position conventions; freeze a controlled
three-seed development pilot. A separately reviewed benchmark freeze must precede
any independent label reveal. Do not reuse detector errors or unvalidated linker
flanks, and do not call a geometric witness proof of fusion function.

## 18 October 2026 — fusion generator implementation (Asia/Calcutta)

**Authority and scope.** The human changed direction and requested architecture
PR #7's final fusion-linker sequence-generator component, ready for future data.
Inspected repository PRs and PR #6's SPEC/CHECKLIST; created an isolated
`codex/fusion-linker-generator` worktree from PR #7 commit
`8e0a75f0148c6d2e3fda753e6e49e42ec135c9ad`. This resumes implementation only;
it does not approve draft architecture/shared contracts, acquire labels or
authorize scientific training. Preserved the dirty detector/model/data worktrees.

**Hypothesis and comparator.** Causal FIM with A prefix and B suffix can provide
both attachment contexts while supplied length/cassette constraints stay exact.
Software controls test loss/causal masks, suffix influence, target-independent
prompts, length/motif enforcement, frozen LoRA bases and exact resume. Future
reconstruction comparators are length-matched training frequency, training-only
2-mer flank retrieval and the separately exposure-audited curated template
library; the source-library adapter is implemented without copying its rows.
No biological model comparison or benchmark was conducted.

**Sources and decisions.** [Architecture PR #7](https://github.com/richennacht/LinkerForge/pull/7)
defines component 5; [PR #6](https://github.com/richennacht/LinkerForge/pull/6)
is the draft specification/checklist. [PR #2](https://github.com/richennacht/LinkerForge/pull/2)
provides the library interface and source/exclusion semantics.
[ProtFIM](https://arxiv.org/abs/2303.16452) supports the two-sided FIM mechanism;
[LoRA](https://arxiv.org/abs/2106.09685) supports frozen low-rank adaptation;
[official GPT-2 documentation](https://huggingface.co/docs/transformers/en/model_doc/gpt2)
supports the tested backbone API. [ProtGPT2's repository](https://github.com/TeletcheaLab/protGPT2)
documents BPE oligomers, motivating explicit rejection of incompatible residue
serialization. These are design motivations, not reproduced biological results.

**Files changed.** Added `src/linkerforge/generation/` (contracts, residue FIM
tokenizer, native/HF model, data preflight, engine, constraints, baselines,
templates, CLI); source entry script; two generator configs; packaging and
requirements; 31 fixed software tests; `FUSION_GENERATOR.md`; readiness report
and hash snapshot. Added current-authority notes to README/AGENTS. No shared
schema, detector code/weight/data, frontend or peer branch was modified.

**Validation commands.** In `LinkerForge-generator`, `$generatorPython` was
`C:/Users/saubh/Documents/ChatGPT/Research/LinkerForge-models/.venv/Scripts/python.exe`
and `$generatorUv` was
`C:/Users/saubh/Documents/ChatGPT/Research/LinkerForge/.venv/Scripts/uv.exe`.
Set `PYTHONPATH` to this checkout's `src` for unittest; build TMP/TEMP to this
checkout's ignored `tmp`, UV_CACHE_DIR to `tmp/uv-cache`.

```powershell
& $generatorPython -m unittest discover -s tests -p test_fusion_generator.py -v
& $generatorPython -m unittest discover -s tests -p test_detector_regions.py -v
& $generatorPython scripts/fusion_linker_generator.py smoke --output tmp/generator-verification/smoke-final
& $generatorPython scripts/fusion_linker_generator.py generate --checkpoint tmp/generator-verification/smoke-final/training/step-000003 --request tmp/generator-verification/request.json --count 2 --max-attempts 3 --seed 17 --output tmp/generator-verification/cli-proposals.json
& $generatorPython scripts/fusion_linker_generator.py evaluate-development --checkpoint tmp/generator-verification/smoke-final/training/step-000003 --manifest tmp/generator-verification/smoke-final/fixtures/manifest.json --synthetic-smoke --output tmp/generator-verification/cli-development.json
& $generatorUv build --wheel --python $generatorPython --out-dir tmp/generator-verification/dist-final
& $generatorPython tmp/generator-verification/verify_artifacts.py
# After setting PYTHONPATH to tmp/generator-verification/wheel-extracted:
& $generatorPython -m linkerforge.generation --help
git diff --check
```

**Observed outcomes and provenance.** 31 generator tests passed in 8.885 seconds;
four existing region tests passed. The tiny CPU smoke used invented sequences:
2 train, 1 development, seed 17, 3 updates, 17,044 parameters, one thread,
120-second ceiling, measured trainer time 1.016 seconds. A separate CLI returned
two candidates from two attempts; development baselines retained all three
method counts. Dropout-enabled four-step versus two-plus-two-step resume matched
weights/histories exactly. Local tiny random GPT-2 verified adapter updates,
frozen weights and reload; no pretrained model was downloaded. Final wheel built
and its 11 generator source files match current bytes; ignored cache/artifacts
are absent. The extracted-wheel CLI works. No scientific rates are reported.

Runtime: CPython 3.14.7, torch 2.14.1+cpu, Transformers 5.20.1, safetensors 0.8.0,
NumPy 2.5.4. Complete source/config/input/artifact hashes, raw counts, precise
commands and limits are in `reports/generator-readiness-2026-10-18.json`;
checkpoints/raw synthetic logs are retained under ignored
`tmp/generator-verification/`. Tests were rerun after tokenizer/template and
environment/RNG corrections; no unchanged biological experiment was repeated.

**Decision, blockers and next task.** Keep this as reviewable uncommitted code.
No commit, push, merge, weight promotion, paid compute, acquisition, benchmark
reveal or scientific job occurred. Implementation/team review remains pending.
Require reviewed provenance/evidence semantics, audited family splits/protected
registries and an approved cloud environment/receipt before fitting. Select and
verify a licensed compatible pretrained protein backbone before adapter use;
the native scratch model already has a working train path. Next: mining-team
input review/data handoff, then a frozen matched development pilot with three
seeds and explicit structural/function limits, not more synthetic efficacy claims.
