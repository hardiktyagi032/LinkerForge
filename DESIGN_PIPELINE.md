# Design pipeline and future training handoff

This is the code-only continuation of architecture PR #7, components 2–5.
Component 1 is excluded. No data acquisition/mining, biological fitting,
benchmark reveal, model download or structural job is performed automatically.
Follow [the readiness checklist](DESIGN_READINESS_CHECKLIST.md) in order.

The existing model architecture is unchanged:

```
future reviewed span/source records -> evidence/boundary/split review
                                      |                         |
                          generator training records     site assay/interruption records
                                      |                         |
                         causal FIM / optional LoRA     frozen ESM residue cache -> MLP/linear
                                      |                         |
user-supplied chain routes -> joint geometry + operation scores -> bounded proposals -> full sequence + residue map
```

Mined linker flanks are **not** automatically site-tolerance supervision.
The independent site towers require reviewed donor-aggregated endpoints; they
do not learn donor-specific compatibility, optimal tether count or fusion function.
The generator learns sequence reconstruction, not an experimental-success label.

## Run code preparation now

Use Python 3.12–3.14 and the pinned dependencies in
`requirements/generator-cpu.txt`. The observed environment is documented in the
dated report; it is not a verified college-cloud image. Installed-package commands
are `linkerforge-design`, `linkerforge-attachment` and `linkerforge-generator`.
Source scripts select this checkout's `src` explicitly.

```powershell
python scripts/design_pipeline.py prepare-training --recipe configs/design-training-round.json --output tmp/review-round
python scripts/design_pipeline.py inspect-training --prepared tmp/review-round
python scripts/design_pipeline.py benchmark-commands --prepared tmp/review-round --output tmp/review-round/development-commands.json
python scripts/design_pipeline.py design --input configs/design-request.example.json --library data/curated/linker_property_library_sources.v1.json --output tmp/design-software-example.json
python scripts/verify_design_architecture.py --scope all --output tmp/design-checks.json
```

Preparation writes nine jobs: site linear and MLP, and native FIM, each with
seeds 7, 17, 31. Every job reserves 1,800 seconds; total child-process reservation
is 16,200 seconds (4.5 hours) under the six-hour round ceiling. These are draft
settings, not an efficacy choice or cloud permission. All nine are blocked by
null data/review fields. Unsigned receipt templates have `approved: false`.
The benchmark command plan stays blocked until all requested jobs complete and
the site coverage fraction is explicitly supplied. No fitting occurs here.

The example design uses visibly synthetic short strings and the existing cited
library; its outputs are sequence proposals only. Empty pools, rejected geometry,
untrained site tasks, duplicate/rejected samples and budget exclusions stay visible.
No source-library label is inherited as measured function of a new assembly.

## Required future data files

All interfaces below are private review proposals (`v0`), not changes to shared
schemas. Consult the exact implemented loaders before producing records.

| Component | Required files and semantics | Reader |
|---|---|---|
| Mining handoff | One supplied `mined-linker-candidate.v0`: source ID/release/full sequence/hash, 1-based inclusive span/residues, up to ten flanking residues, finite score, threshold ID, abstention, classifier/calibration/config hashes, commit and family IDs | `pipeline.intake.review_candidate` / `review-candidate`; consistency only, always training-ineligible |
| Generator | `fusion-generator-dataset.v0` manifest; hash-bound train/development JSONL of `TrainingExample`, exact A/linker/B sequences and properties, provenance/family IDs/evidence tier/eligibility; explicit review policy for any predicted spans | `generation/data.py`, `generation/contracts.py` |
| Site scorer | `attachment-site-dataset.v0` manifest; train/development JSONL of `SiteExample`; operation-aligned labels `1/0/-1`, assay/interruption references and reviewed donor-aggregation/negative-evidence policy | `attachment/data.py` |
| Frozen features | One hash-bound safetensors residue matrix per sequence, no special-token rows, exact source sequence and encoder identity; layer/dimension/local asset-bundle hash/pinned revision | `attachment/features.py`, `save_embedding` / `load_embedding` |
| Split firewall | Full `sequence-exclusion-registry.v1` benchmark source/sequence/family metadata only; reviewed audit binding exact split and registry hashes | Both preflights; no labels/errors/predictions in exclusion registries |
| Execution | Institution/review reference, approved exact host/environment, canonical per-seed config hash and full preflight input-hash map | Both trainers and dispatcher |

Natural interruptions establish observed positives, not negatives elsewhere.
Measured insertion and terminal-extension tasks remain separate. Unknown sites
stay `-1`. Each fitted binary site head needs genuine positive **and** negative
controls; positive-only data will fail preflight because a PU trainer is not
implemented for this component. Domain boundaries and provenance must be reviewed
before generator records are constructed. The intake validator cannot supply that
review, establish calibration, adjudicate a linker or conduct homology clustering.

Both preflights reject train/development source/sequence/family collisions and
benchmark exclusions, but cannot independently prove supplied family annotations
or audit decisions. The detector's spent/protected benchmarks are never a source
of training selection. No independent test reader is added.

For future frozen features, `load_local_encoder(directory, identity, device)`
verifies the complete local bundle before loading; `extract_residues` returns
all residue rows or rejects an overlong/misaligned sequence. Use `save_embedding`
with the same identity and the resulting file hash in `SiteExample.embedding`.
No automatic download, truncation or unreviewed window stitching is supported.
See [the site guide](ATTACHMENT_SITE_MODEL.md) and
[generator guide](FUSION_GENERATOR.md) for exact data examples and train/resume APIs.

## Explicit contacts and more than two tethers

Legacy tandem and insertion plans still work. For a multi-contact single chain,
use `topology: "explicit_route"`, with segments `[domain, first, last]` using
1-based inclusive positions, and one length/type per edge. For example:

```
A[1..cutA] — L1 — B[1..cutB] — L2 — A[cutA+1..end] — L3 — B[cutB+1..end]
```

This has three peptide connections between the same two domains. It requires
interrupting both domains; it is not three independent tandem fusions. Domain
fragments must alternate, preserve native residue order and cover each complete
domain once. A maximum of 16 segments is a software resource ceiling, not a
biological cutoff. Disulfides, circular permutations, ligation, two-chain
constructs and omitted/duplicated residues require other protocols.

`required_scores()` deduplicates each internal cut and identifies N/C extension
operations explicitly. `contacts()` maps all A/B anchor pairs into one shared
geometry problem. Scores are uncalibrated operation logits; the mean is a
heuristic, not a joint probability. Unassessed tasks and undetermined geometry
stay unknown. A geometric witness establishes only the engine's geometric criteria.

For `assess-geometry`, supply `fusion-geometry-input.v0` JSON with `plans` keyed
by plan ID; each contains `a` and `b`, each with `file: {path, sha256}`, `chain`,
and `sequence_to_pdb: {"1": 123, ...}`. Add `budget: {restarts: 2, iterations: 20,
seed: 17}`. Paths are relative to that JSON. Every mapped residue is checked
against the supplied sequence; insertion codes/ambiguous numbering are not guessed.
Limits remain eight restarts and 100 iterations per plan. Example command:

```powershell
python scripts/design_pipeline.py assess-geometry --input request.json --structures structures.json --output geometry.json
python scripts/design_pipeline.py design --input request.json --geometry-reports geometry.json --library library.json --output proposals.json
```

The geometry report binds the exact request and structure inputs. A checksum is
an integrity binding, not a reviewer signature. Review supplied score/geometry
files and retain their provenance.

Source templates work for all route edges. The trained generator's native track
is whole-domain C(A)-to-N(B) tandem context. By default it is **not** called for
fragment junctions. An explicit `allow_junction_context_transfer: true` permits
experimental reuse of fragment prefix/suffix contexts, recorded as unvalidated
transfer. That does not establish insertion tolerance or joint multi-tether
generalisation. A validated insertion model needs its own reviewed data/protocol.

Zero-length edges are direct fusion and never call the positive-length generator.
Assembly preserves all supplied domain residues and maps each segment/linker into
the final sequence. All new-junction forbidden motifs are checked again on the
complete assembly, including motifs spanning multiple short segments/linkers.
Motifs already wholly inside a fixed source segment are not new design violations.
Topology and linker intent remain inputs; no optimal-count/function model exists.

## Once reviewed data and infrastructure arrive

1. Fill manifest paths and review reference in a **new copy** of the recipe.
   Select only reviewed architecture variants. Keep matched component input files,
   at least three seeds and the aggregate reservation within the declared ceiling.
2. Run each component's preflight, then `prepare-training` into a new directory.
   Its materialized configs/source/input identities are immutable. A changed input,
   source or configuration requires fresh preparation, never a bypass.
3. Inspect real processes, scheduler jobs and prior ledgers. An empty local ledger
   does not establish that another account/host is idle. Verify the institution's
   actual GPU/driver/assets/image; no Slurm command or cloud availability is assumed.
4. Review/fill a per-job execution receipt for that actual host/environment. Supply
   an approved copy, never modify an `UNSIGNED` file to imply team review occurred.
5. Launch one explicit job through the dispatcher, after approval:

   ```powershell
   python scripts/design_pipeline.py run-training --prepared <round> --job-id site-mlp-seed-7 --execution-receipt <approved-receipt.json> --device cuda:0
   ```

   Logs/child PID/config/source/environment/input identities and measured wall time
   are retained. The dispatcher kills its owned child on timeout, checks completion
   and checkpoint hashes, and never retries or overwrites a previous attempt. The
   lock is shared by this dispatcher's checkouts for the current OS account/host;
   it cannot rule out other accounts, schedulers or standalone training commands.
   Do not remove a stale lock until its actual processes are checked. Existing
   trainer APIs support exact-identity checkpoint resume; review retry/resume
   budgets separately, with every failed attempt retained.
6. After **all** requested seeds/controls complete, prepare development argv:

   ```powershell
   python scripts/design_pipeline.py benchmark-commands --prepared <round> --coverage-fraction <development-choice> --bootstrap-draws 200 --seed 17 --output <new-commands.json>
   ```

   Inspect commands and compute budgets before executing. This command itself
   opens no labels and runs no evaluation. Site benchmarks retain task strata,
   uniform/proximity controls, failed/missing coverage and paired family intervals.
   Generator evaluations retain frequency and training-only flank retrieval,
   one-candidate budgets, exact counts, valid-call edit distance, full/common
   coverage and paired family intervals. Optional fixed-library comparison requires
   an explicit source/family-exposure review; it is not context retrieval when its
   records have no flanking context. No different tasks are pooled into a ranking.
7. Retain every seed and negative result. Freeze preprocessing/weights/decoding,
   endpoint, cohort/exclusions, comparator coverage, compute and rejection rules
   before any separately authorised independent evaluation. Sequence reconstruction
   and site AUROC are development diagnostics; the primary structural endpoint,
   expression, folding, function and cleavage activity are still untested.

## Verification and sources

`verify_design_architecture.py --scope geometry` uses standard-library tests;
`--scope models` adds the generator/site/pipeline fixtures. The latter exercise
optimizer/resume/checkpoint wiring on invented data, not research fitting.
The full historical detector suite is deliberately outside this scoped check.
No scientific performance, calibrated uncertainty, cloud execution or team review
is inferred from passing software tests. See the dated readiness report for exact
commands, versions, hashes and outcomes.

Design authority: [architecture PR #7](https://github.com/richennacht/LinkerForge/pull/7),
[generator PR #9](https://github.com/richennacht/LinkerForge/pull/9),
[site PR #10](https://github.com/richennacht/LinkerForge/pull/10).
The existing guides retain the primary ProDomino, ProtFIM and LoRA sources and
their evidence limits. This increment connects implemented components; it adds
no new biological mechanism or research-success claim.
