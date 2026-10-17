# Fusion linker sequence generator

Implementation requested by the human on **18 October 2026 (Asia/Calcutta)**,
following [architecture PR #7](https://github.com/richennacht/LinkerForge/pull/7),
component 5, at `8e0a75f0148c6d2e3fda753e6e49e42ec135c9ad`.
[SPEC/CHECKLIST PR #6](https://github.com/richennacht/LinkerForge/pull/6)
at `d4256b7f9e677a3ad0994643f5cd7cf281888793` was also inspected.
Those PRs are drafts; implementing this component does not assert team review.

This is executable model/trainer/decoder software awaiting data. It has no
biologically trained generator weights or demonstrated fusion performance.
It preserves the detector benchmark firewall and does not use detector labels,
old benchmark errors, structural reference coordinates or pseudo-labels.

## What is implemented

The conditional causal transformer receives this fill-in-middle serialization:

```text
BOS PREFIX domain_A_C_terminal_flank SUFFIX domain_B_N_terminal_flank
rigidity cleavage LENGTH [cited_motif MOTIF_POSITION] MIDDLE linker_residues
```

The **length is supplied**, not predicted. Domain B is visible before the first
generated residue. Both flanks use attachment-adjacent cropping, with the same
full-linker space reservation at training and inference. Residues are single
tokens. Prompt/padding/explicitly supplied motif positions are excluded from
the loss. Each training record contributes its mean free-residue cross entropy,
so long linkers do not automatically dominate short ones. There is no EOS
decision: generation emits exactly the requested residue count.

Two backbones share the interface:

- `native`: an actual trainable pre-norm causal transformer with learned residue,
  control and positional embeddings. It starts randomly initialized and is the
  reference/scratch comparator, not a pretrained protein model.
- `hf_causal_lm`: a compatible Hugging Face causal protein LM, optionally frozen
  with trainable low-rank projection residuals, new control embeddings and a
  20-residue output head. Model code must be built into Transformers; remote code
  execution is disabled. Remote revisions must be immutable commit SHAs; local
  assets are hashed and checked again at checkpoint reload.

**A suitable public pretrained checkpoint has not been selected or downloaded.**
The HF path was tested with a tiny locally created, randomly initialized GPT-2
fixture, not ProtFIM weights. The LoRA config deliberately leaves model/revision
null until an approved compatible asset is available. Set actual projection
names for that backbone; `c_attn,c_proj` is tested for GPT-2 only. The tokenizer
must encode canonical sequences as distinct individual residue tokens. BPE
checkpoints such as ProtGPT2 are not silently accepted as residue-exact models.
The native config can train without external weights when reviewed data exists.

The implemented topology is **one tandem C(A) to N(B) connection**. Requests for
internal attachment, insertion or multiple tethers fail explicitly. Chosen
sites and a geometrically appropriate length are upstream inputs; this package
does not replace the geometry calculator or attachment-site scorer.

Rigidity is a conditioning label/design intent, not measured helicity. A
cleavable design requires an exact motif, its source and a position (or a
deterministic default). Rigid plus cleavable requests have a distinct spacer
and flexible cassette layout; `cassette_flank=2` is an editable engineering
layout default, **not a biological unfolding threshold**. Neither motif presence
nor a design label proves cleavage, rigidity, expression, folding or function.
`no_known_motif` never means resistance to every protease.

Decoding supports an allowed residue alphabet, temperature/top-k, reproducible
seeds, forced motif placement and bounded attempts. Postfilters screen forbidden
motifs overlapping the new linker/junctions and duplicates. All rejected attempts
remain in the output. Exhausting the budget means search failed, not that no
possible sequence exists. No pLDDT filter or fusion-success probability exists.

## Run and verify

Create a dedicated environment rather than installing over another worktree's
package. The dependency versions below are the tested CPU versions; the college
GPU image still needs its own verification.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements/generator-cpu.txt
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
.\.venv\Scripts\python.exe scripts/fusion_linker_generator.py --help
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_fusion_generator.py -v
.\.venv\Scripts\python.exe scripts/fusion_linker_generator.py smoke --output tmp/generator-smoke
```

The smoke command creates **three invented software records**, performs exactly
three CPU optimizer updates with a small native model, saves/reloads checkpoints,
generates one proposal and runs the two training-only baselines. Every artifact
is labelled synthetic. Its losses/recovery are not biological evidence. Existing
output paths are refused. Keep these artifacts out of scientific datasets.

`train`, `preflight`, `generate`, `templates`, `evaluate-development` and
`environment` have command-specific `--help`. The script prepends this checkout's
`src`, avoiding accidental imports of another worktree's installed package.

## Future data handoff: private v0 proposal

No shared JSON Schema was changed. This adapter is a **private review proposal**
for the mining/data team, not automatic adoption of a new shared contract.
The manifest directory contains train/development JSONL files and any audit and
exclusion-registry files. All referenced paths must remain inside that directory.

```json
{
  "format": "fusion-generator-dataset.v0",
  "dataset_id": "REPLACE_WITH_REVIEWED_VERSION",
  "kind": "scientific_dataset",
  "review": {"approved": false, "reviewer": null, "reference": null},
  "splits": {
    "train": {"path": "train.jsonl", "sha256": "REPLACE_WITH_ACTUAL_SHA256"},
    "development": {"path": "development.jsonl", "sha256": "REPLACE_WITH_ACTUAL_SHA256"}
  },
  "benchmark_registries": [{"name": "FULL_PROTECTED_REGISTRY", "path": "exclusions.json", "sha256": "REPLACE_WITH_ACTUAL_SHA256"}],
  "split_audit": {"path": "family-audit.json", "sha256": "REPLACE_WITH_ACTUAL_SHA256"}
}
```

Each JSONL record has exactly the `TrainingExample` fields in
`src/linkerforge/generation/contracts.py`: `record_id`, `request`, `linker`,
`source_id`, full-source `source_sha256`, nonempty audited `family_ids`,
`evidence_tier`, and `training_eligible=true`. `request` has the `DesignRequest`
fields (two canonical domain sequences, positive residue `length`, optional
rigidity/cleavage constraints, etc.). The target length/motif/alphabet must agree
with the supplied request. IDs, provenance and evidence tiers do not enter the
model prompt. A request's `motif_start` is **zero-based**; attachment positions,
reported segments and substitution positions are **one-based inclusive**.

Unknown property labels remain `unknown`; missing labels do not become flexible
or non-cleavable examples. Natural observations, predicted spans and measured
function remain distinct. Predicted spans are refused without a separate
reviewed policy (`review.allow_predicted_spans=true`); that flag does not validate
their annotations. Ineligible examples and synthetic/scientific mixing fail.

Exclusion registries have exactly `format="sequence-exclusion-registry.v1"`
and `records`, each containing only `source_id`, `sequence_sha256`, `family_ids`.
Labels/predictions/errors are prohibited. Use complete, approved protected
registries, not a convenient subset. The adapter checks duplicate IDs, sources,
full supplied sequence hashes, exact concatenated A-linker-B duplicates and
family overlap across train/development and protected registries. The split
audit must record `passed=true`, `method`, `review_reference`,
`split_sha256s={train:...,development:...}` and
`benchmark_registry_sha256s={registry_name:...}` binding the actual file hashes.
These checks **cannot independently establish homology, family assignments,
complete annotation, cohort suitability or permission to train**. Those remain
data-team review inputs; do not bypass the detector's spent-benchmark exclusions.

## Train when the data and execution review exist

```powershell
python scripts/fusion_linker_generator.py preflight --manifest artifacts/reviewed-generator-data/manifest.json
python scripts/fusion_linker_generator.py environment
python scripts/fusion_linker_generator.py train --manifest artifacts/reviewed-generator-data/manifest.json --config configs/fusion-generator-native.json --execution-receipt artifacts/reviewed-execution.json --device cuda --output artifacts/generator-round-01
```

For adapters, first configure `configs/fusion-generator-pretrained-lora.json`
with the real approved checkpoint/revision and verified architecture names.
For local assets use an existing directory and `revision="local"`; remote assets
require an exact 40-character SHA. Default `local_files_only=true` avoids
implicit network access. No particular pretrained asset or licence is assumed.

A scientific execution receipt must contain `approved=true`, `institution`,
`review_reference`, actual `host`, `environment` exactly as printed by the
environment command, `config_sha256` of canonical sorted compact JSON for
`asdict(TrainConfig.from_dict(config))`, and `input_hashes` exactly as returned
by preflight. It is a recorded operational review, not cryptographic approval.
Preflight alone never grants execution approval. Long scientific runs belong
on the verified institution-approved cloud; this implementation launched none.

The trainer uses finite update/wall-clock ceilings, AdamW, gradient clipping,
finite loss/gradient checks and deterministic shuffles. Records include PID,
host, source/config/input hashes, seed, versions, record counts, parameter counts,
per-step raw free-residue NLL/counts and measured wall time. Failures are retained.
GPU kernels and resource use still require validation on the actual cloud image.

Checkpoints include model safetensors, optimizer state, CPU/CUDA/Python RNG,
step and deterministic epoch position. Resume into a new output directory with
`--resume .../step-000100`; the config (including total steps), data, source,
environment, mode and device must match. Optimizer loading uses
`weights_only=true`. Model/optimizer/metadata hashes are verified; frozen local
base files must still match. No old outputs are overwritten, and no automatic
retry or weight promotion occurs. Adapter checkpoints require their original
frozen base assets. There is no automatic best-checkpoint or seed selection.

## Baselines, proposals and future X2

The `templates` command consumes the exact source-library JSON interface from
[PR #2](https://github.com/richennacht/LinkerForge/pull/2), pinned during review to
`7e49569ad895fa8232328c699ceb8cc47f22f05a`. That library and its unmerged schemas
were not copied or changed. Missing/excluded sequences are skipped, citations
are required, and lengths/properties are matched. Optional substitutions alter
only an explicitly supplied cleavage cassette and record every changed residue;
they never inherit source function measurements. Templates are not resized.

```powershell
python scripts/fusion_linker_generator.py templates --library PATH_TO_REVIEWED_LIBRARY.json --request request.json --max-substitutions 0 --output template-proposals.json
python scripts/fusion_linker_generator.py generate --checkpoint artifacts/generator-round-01/step-001000 --request request.json --seed 17 --count 8 --max-attempts 32 --output proposals.json
python scripts/fusion_linker_generator.py evaluate-development --checkpoint artifacts/generator-round-01/step-001000 --manifest artifacts/reviewed-generator-data/manifest.json --output development-reconstruction.json
```

Development diagnostics use **one candidate and one attempt per record/method**,
comparing the infiller with length-matched training frequency and an unfitted
training-only flank 2-mer retrieval control. Null baselines/failures count against
attempted coverage; no test references choose a retrieved entry. These controls
are explicitly not ESM retrieval or the external curated-library comparator.
The external library comparator still needs a reviewed exposure/family audit
and common protocol before adding it to a scientific X2 comparison.

Reports retain per-record calls, families, exact matches, edit distances and all
failures. Supplied length makes length error zero by construction; it is not
evidence of learned length prediction. This is a known-length development task,
not blind linker generation, structure recovery or measured-function evaluation.

When data arrives, freeze source/family exclusions and the development protocol;
retain the retrieval/frequency baselines and add the audited external library.
Test one factor at a time: context versus shuffled context; scratch versus the
approved pretrained backbone; full fine-tuning versus LoRA. Repeat promising
variants across at least three predeclared seeds. Final independent evaluation
still needs frozen matching, full attempted coverage, paired family-cluster
uncertainty, all failures, measured compute and the applicable structural checks.
No blind benchmark reader or automatic scientific claims are implemented here.

## Technical basis and limits of transfer

- [ProtFIM original preprint](https://arxiv.org/abs/2303.16452): motivates exposing
  prefix and suffix before generating a missing protein segment. This software
  applies that idea to supplied-length linker infilling; it does not reproduce
  ProtFIM's training or establish that its results transfer to fusion linkers.
- [LoRA original paper](https://arxiv.org/abs/2106.09685): motivates trainable
  low-rank residuals around frozen projections. This implementation uses native
  PyTorch residual modules, not PEFT; LinkerForge efficacy remains untested.
- [Official Transformers GPT-2 documentation](https://huggingface.co/docs/transformers/en/model_doc/gpt2):
  reference for the tested local causal-backbone fixture/API. GPT-2's text
  checkpoint is not a protein pretrained model.
- [Official ProtGPT2 repository](https://github.com/TeletcheaLab/protGPT2):
  documents its BPE oligomer representation, explaining why direct residue-count
  decoding is not a verified drop-in path for that model.
