# Model research log

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
