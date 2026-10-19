# Generator implementation readiness — 18 October 2026

Date uses the human's Asia/Calcutta workspace date. Worktree:
`C:/Users/saubh/Documents/ChatGPT/Research/LinkerForge-generator`, branch
`codex/fusion-linker-generator`, based on architecture PR #7 commit
`8e0a75f0148c6d2e3fda753e6e49e42ec135c9ad`.

The direct human instruction authorizes building component 5 now, before data
exists. The implementation is ready for data integration/review; no generator
has been scientifically trained or validated. Existing detector, fusion-ranker
and data worktrees and their unreviewed proposals were preserved.

## Implemented increment

An executable conditional FIM transformer, optional frozen-backbone LoRA path,
training/collation/preflight, exact-length constrained decoding, source-library
template/cassette-substitution adapter, training-only frequency and context
retrieval baselines, development reconstruction diagnostics, checkpoint/resume,
CLI, pinned dependency declarations and a built wheel. The detailed interface,
future training commands and limitations are in [FUSION_GENERATOR.md](../FUSION_GENERATOR.md).

The causal hypothesis for this software increment was that both flanks can
condition an infiller without target leakage, while explicit length/motif
constraints remain enforced and resume preserves optimization. Tests falsify
incorrect causal masking, target/prompt leakage, changed frozen parameters,
data-family/exclusion collisions, altered checkpoints and non-equivalent resume.
They do not test biological efficacy of the architectural hypothesis.

## Observed verification

| Check | Observed outcome |
| --- | --- |
| Generator tests | 31 passed in 8.885 seconds |
| Existing region regressions | 4 passed |
| Native CPU smoke | 2 invented train records, 1 invented development record, seed 17, 3 updates, 17,044 parameters, 1.016 seconds measured trainer wall time |
| Smoke checkpoint and baseline path | Saved/reloaded; 1 candidate from 1 development attempt; frequency/retrieval controls both executed |
| Separate CLI proposal path | 2 candidates returned from 2 attempts with the synthetic flag retained |
| Exact optimizer resume | Four uninterrupted versus two-plus-two resumed steps produced identical histories and model tensors with dropout enabled |
| Optional HF/LoRA path | Tiny locally constructed GPT-2 fixture; frozen parameters unchanged, adapter updated, exact checkpoint reload; no pretrained weights or network download |
| Incompatible tokenizer | Residue-merging BPE fixture refused before weight loading |
| Packaging | Wheel built; all 11 generator source files match wheel bytes; 44 members contain no ignored tmp/artifact/environment content; extracted wheel CLI imports and prints help |
| Formatting | `git diff --check` passed |

All sequence fixtures are **synthetic software tests**, not training data or
biological performance evidence. No recovery rate, structural score, fusion
success or frontier improvement follows from them. Scientific training remains
blocked before model loading without the actual reviewed dataset and execution
receipt. Deliberate negative tests exercised those failures.

Runtime used read-only from the model worktree: CPython 3.14.7,
PyTorch 2.14.1+cpu, Transformers 5.20.1, safetensors 0.8.0, NumPy 2.5.4.
No environment was installed into another worktree. A temporary isolated build
environment resolved the pinned Hatchling build backend. The uv warning about
an in-source ignored cache was checked against the actual wheel contents; no
cache was packaged. This is not a verified cloud/GPU image.

[The machine-readable evidence](./generator-readiness-2026-10-18.json) records
commands, source/config/input/artifact hashes, versions, counts, ceilings and
remaining prerequisites. Raw logs, synthetic checkpoint and wheel are retained
under ignored `tmp/generator-verification/`. The smoke's resource ceiling was
one CPU thread, three updates and 120 seconds. No scientific cloud job,
acquisition, real-data fit, benchmark reveal, commit, push or merge occurred.
Peer/team review remains outstanding.

## Decisions and remaining work

Use this as the generator implementation for review and future data handoff.
Keep tandem C(A)-to-N(B) infilling explicit; internal insertion/multi-tether
generation is not implemented. Keep length and exact cleavage motifs supplied,
and do not train on arbitrary predicted linker spans or silently infer missing
rigidity/cleavage labels. The source-library adapter does not merge PR #2 or
adopt its shared schema automatically.

The native model can be trained from scratch once reviewed data/execution
inputs exist. The adapter path is implemented and tested as software, but a
compatible pretrained protein checkpoint/licence has **not** been selected.
The next data integration task is to review the private v0 input adapter with
the mining team, provide traceable linkers and audited family-disjoint splits
and full protected sequence registries, and verify the actual approved cloud
image. Then freeze an X2 development comparison including the exposure-audited
external template library and seed/compute budgets before fitting. Independent
structural/function evaluation is a later gate, not a claim of readiness here.

## Sources linked to decisions

- [Architecture PR #7](https://github.com/richennacht/LinkerForge/pull/7), component
  5: FIM, supplied length/cassette, adapters and template-first baseline.
- [SPEC/CHECKLIST PR #6](https://github.com/richennacht/LinkerForge/pull/6): current
  scoping/checklist reviewed as a draft; no team approval inferred.
- [Template PR #2](https://github.com/richennacht/LinkerForge/pull/2), inspected at
  `7e49569ad895fa8232328c699ceb8cc47f22f05a`: loader/source interface, exclusions,
  separate axes and absent sequences; used for the adapter, not as training data.
- [ProtFIM](https://arxiv.org/abs/2303.16452): prefix/suffix infilling mechanism,
  not proof of linker-generator transfer or a reproduced result.
- [LoRA](https://arxiv.org/abs/2106.09685): low-rank residual adaptation of frozen
  weights; here implemented with native PyTorch, not PEFT.
- [Transformers GPT-2 documentation](https://huggingface.co/docs/transformers/en/model_doc/gpt2):
  tested causal-backbone interface.
- [ProtGPT2 official repository](https://github.com/TeletcheaLab/protGPT2): BPE
  oligomers explain the residue-token compatibility restriction.
