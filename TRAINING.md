# LinkerForge training runbook

Status: official DLD reference data converted and preflight passed on 8 October
2026; an initial CUDA residue-CNN run completed separately. Check
`artifacts/dld-detector-run-001/training-suite-manifest.json`, `stdout.log`, and
`stderr.log` for its actual outcome. The CNN reached validation residue F1
0.146 and no-linker specificity 0 at its default threshold; it is not a usable
pseudo-labeller. Frozen ESM-2 8M and 35M residue-head experiments completed
under `artifacts/esm2-linker-run-001/` and
`artifacts/esm2-35m-linker-run-001/`; consult their manifests for exact
checkpoints and metrics. The 35M model was selected by validation AUPRC and
evaluated once on DLD fold 5. No
geometric GNN ranker or folding model has been trained/run by this repository. The open LaTeX paper
is not a live training log and must not be updated with planned results.

## Official DLD reference conversion (8 October 2026)

The official [DLD database](https://dld.chemeslab.org/) raw archive was 15,029,112
bytes (SHA-256 `635500b45b060786544fc88c2e1a458d9c38a336cee33f8b0517015800bfb5d9`).
`scripts/prepare_dld_detector_reference.py` reads its `domainLinker_chain.json`
member directly from ZIP without extraction. The source has 2,646 full-chain
records, per-residue codes 0–5, source homology-cluster IDs, and five source
folds. Codes 1/2 become IDL/DDL; all other codes become non-linker. Six chains
with unsupported residues and all 20 records belonging to 10 duplicate-sequence
groups were excluded, rather than resolving inconsistent annotations arbitrarily.
No source cluster crosses folds. Folds 1–3 are train (1,560 chains; 1,163
positive and 397 negative), fold 4 is validation (530; 389 positive and 141
negative), and fold 5 was reserved for one-time evaluation (530; 368 positive
and 162 negative).

The emitted `domain_tokens` are **all zero**. They must not be populated from
the source residue labels, as that would leak the answer into the input. This
run is therefore a sequence-only CNN detector, not the intended independent
domain-map/geometry model. Conversion outputs and the preflight report are
ignored temporary files under `data/processed/dld_reference/`; the permanent
converter and this source checksum suffice to recreate them. The downloaded
raw ZIP is removed after conversion. Preflight passed on train and validation,
but it only checks that source-provided clusters do not overlap; an independent
homology audit is required before publication-level leakage claims. Fold 5
was not used for hyperparameter selection.

## Protein-language-model detector experiment

`scripts/train_esm2_linker_detector.py` freezes official ESM-2
`facebook/esm2_t6_8M_UR50D` revision
`c731040fcd8d73dceaa04b0a8e6329b345b0f5df` and trains only a small
residue-level convolutional head on the same DLD train/validation split. It
uses bounded 510-residue windows and CUDA; checkpoint files contain the head,
optimizer and validation metrics, not copied base-model weights. Model weights
are cached in ignored `artifacts/hf-cache/`. The exact source/provenance and
versioned record contracts are in `schemas/detector-reference.schema.json`,
`schemas/detector-training-run.schema.json` and
`schemas/detector-epoch.schema.json`. The run selects its model and operating
threshold from validation only. Fold 5 was evaluated once after selection. This is a
small-backbone adaptation of the pLM strategy, **not** a reproduction of
LINKER-Pred2's ProtTrans + MSA-Transformer architecture or CAID3 score.

The 8M run's best validation residue AUPRC was 0.2752. The 35M run used
`facebook/esm2_t12_35M_UR50D` revision
`6fbf070e65b0b7291e7bbcd451118c216cff79d8`, with best validation
AUPRC 0.3998. Its one-time DLD fold-5 result, saved in
`artifacts/esm2-35m-linker-run-001/blind-evaluation.json`, was residue
AUPRC **0.3805**, AUROC **0.9194**, and F1 **0.4190** at validation-selected
threshold 0.5992 (530 proteins, 228,287 residues). At the separately
validation-selected high-precision threshold 0.9524, test precision was
0.7166 and recall 0.1179. This is an **internal provisional result**, not
published-predictor superiority or CAID3 reproduction.

A candidate-overlap screen of fold 5 against train/validation, saved in
`artifacts/esm2-35m-linker-run-001/dld-split-overlap-screen.json`, found
one blind chain (`1uok_a_P21332`) with two training matches exceeding 0.82
query coverage and 0.63 identity. That chain needs family/domain review and
a prespecified exclusion before any homology-clean claim. The top-10 5-mer
screen can miss remote homologs; a full clustering audit is still due. The
blind evaluation was not used for model or threshold selection.
Re-evaluating with the same frozen checkpoint and thresholds after excluding
that one sequence-only-screened chain gave AUPRC 0.3805 over 529 proteins
(`artifacts/esm2-35m-linker-run-001/screened-blind-evaluation.json`). The
thresholded residue precision and recall were unchanged because the excluded
chain contributed no positive calls at those thresholds. This is a
**screened sensitivity analysis**, not a fully homology-certified test.

A later **validation-only exploratory** threshold sweep for 90% residue
precision is in
`artifacts/esm2-35m-linker-run-001/precision-90-validation-probe.json`.
At threshold 0.99459 it reached validation precision 0.9013 with recall
0.0766 (475 true positives, 52 false positives). This threshold was chosen
after the original one-time blind evaluation and has **not** been tested on
the blind fold. It is not a claim of 90% held-out precision; a newly frozen
independent set would be required to make that claim.

A matched one-epoch experimental policy-gradient fine-tune is documented in
[RL_PERFORMANCE_EXPERIMENT.md](./RL_PERFORMANCE_EXPERIMENT.md). It did **not**
demonstrate a meaningful boost: validation AUPRC was 0.39920 for the hybrid
RL arm versus 0.39917 for equal-compute continued supervised training and
0.39980 for the untouched base. At ≥90% validation precision, the three arms
found 470, 469, and 475 linker residues, respectively. No RL checkpoint is
promoted for deployment or paper claims.

Published [LINKER-Pred-Lite](https://github.com/deemeng/punch_linker_light)
and [LINKER-Pred2](https://github.com/deemeng/punch_linker2) inference was
reproduced on the authors' bundled sequence/feature arrays. See
[PUBLISHED_BASELINE_INFERENCE.md](./PUBLISHED_BASELINE_INFERENCE.md). The
authors' models were trained on DLD/DisProt, so DLD fold 5 is **not** a clean
head-to-head test of their models against ours. A separately curated,
post-training-source, homology-audited test set and exact ProtTrans/MSA
features remain necessary.

On 8 October 2026 the local RTX 3050 6 GB GPU passed
`scripts/smoke_detector_gpu.py` using Python 3.12, PyTorch 2.14.1+cu130 and
NumPy 2.3.3 in ignored `.venv-gpu/`. The test performed one synthetic
forward/backward step and restored an atomic checkpoint. This is an
**environment test**, not reference-label training or a model result. The
local installation is not a substitute for testing the college cloud image.

## Three distinct comparisons

1. **Linker detection:** residue-level linker / no-linker classifier. It needs
   curated reference labels, explicit no-linker proteins, domain maps and true
   sequence-homology clusters. Baselines: older random-forest/DFLpred and
   current LINKER-Pred/IDP-ELM where runnable; our CNN; frozen/LoRA ESM-2
   variants after implementation. Use identical held-out reference proteins.
2. **Linker choice for two domains:** no-linker, `(GGGGS)3`, random GS-rich,
   geometry-only, retrieval, transparent hand-feature and future XGBoost/GNN
   rankers. Use an identical candidate pool and frozen rejection rules.
3. **Structural evaluation:** AF2/ColabFold, ESMFold and OpenFold predict the
   *same complete sequence* for every shortlisted design method. These are
   structure predictors, not trained LinkerForge baseline rankers. Their
   agreement is a sensitivity check, not experimental validation. See
   `STRUCTURE_ENSEMBLE_EVALUATION_SPEC.md`.

The machine-readable registry is `configs/training-suite.json`. An entry
marked `planned_not_implemented` is never silently replaced by another model.

## Verified local pilot

From repository root, using an installed Python interpreter:

```powershell
python scripts/run_training_suite.py --pilot-records data/processed/cath_full_pilot.jsonl --output-dir data/processed/training_suite_smoke
$env:PYTHONPATH='src'
python -m unittest discover -s tests -q
```

The pilot is **unreviewed CATH/RCSB candidate gaps**, not gold linkers; its
split is only a coarse family-architecture proxy. The suite writes a manifest
and baseline report into the ignored output directory. Retrieval and the
hand-feature pairwise model share the same evaluation-only reference-injected
candidate pools. Do not use these provisional scores to claim superiority.

## Before a reference GPU run

1. Resolve legally accessible DLD/DisProt-style residue labels. Map full
   sequences, labels (0=non-linker, 1=IDL, 2=DDL), domain tokens (0..3), source
   ID, label tier, and true homology cluster ID. Do not relabel InterPro gaps
   as curated references. Keep pseudo-labels out of reference detector training.
2. Make immutable train and validation JSONL(.gz) streams; one protein per line.
   Separate whole clusters before fitting. Reserve the blind set entirely.
3. Run `python scripts/preflight_detector_data.py --train TRAIN --validation
   VALID --output PREFLIGHT.json`. The gate rejects missing fields, invalid
   labels, duplicate exact sequences, cluster/sequence split overlap, pseudo
   labels and a split lacking positive or explicit negative proteins. It
   trusts the supplied cluster IDs and cannot certify their biological quality.
4. Pin and test a CUDA-capable PyTorch environment on the actual college cloud
   image. No backend lock file or cloud image has been committed yet, so no
   installation is claimed. Record `torch.__version__`, CUDA version, GPU,
   driver, source checksums/ETags, code commit and job ID in the run manifest.
5. Run the suite through `scripts/cloud/train_detector.sbatch` after adapting
   its scheduler directives. The template is **not** submitted. Set paths via
   environment variables on the cluster; do not put credentials in Git.

Direct launcher example on an already configured CUDA host:

```bash
python scripts/run_training_suite.py \
  --detector-train /immutable/reference-train.jsonl.gz \
  --detector-validation /immutable/reference-validation.jsonl.gz \
  --output-dir /scratch/linkerforge/run-001 \
  --epochs 10 --batch-size 16
```

The detector trainer uses bounded one-batch prefetch, refuses CPU training,
saves atomic checkpoints, and can resume with `--resume`. A remote gzip source
is re-read from the start each epoch; resuming mid-shard skips earlier batches
after streaming them, rather than seeking into compressed bytes. No raw stream
is saved locally by the trainer. Checkpoint and report files are retained.

## Evaluation gate

Do not promote a checkpoint solely because its training loss decreases. Freeze
the model and detection threshold on calibration clusters. Report residue
AUPRC/MCC, linker region overlap, boundary accuracy, no-linker false-positive
rate, IDL/DDL breakdown, and throughput on an independent reference set. The
current trainer only reports preliminary F1 and no-linker specificity; the
full benchmark evaluator and modern comparator adapters are still required.
Only after that gate may high-confidence outputs on the InterPro/UniProt stream
be recorded as **pseudo-labels** for downstream ranker training. Count actual
unique consumed proteins, not archive size or training epochs.
