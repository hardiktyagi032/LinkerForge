# Published linker-predictor inference

This reproduces **inference**, not training or the authors' published accuracy.
LINKER-Pred-Lite and LINKER-Pred2 are distinct published DFL-identification
baselines; they are not LinkerForge's fusion-linker compatibility ranker.

## Inputs and provenance

- Authors' code and checkpoint sources:
  [LINKER-Pred-Lite](https://github.com/deemeng/punch_linker_light),
  [LINKER-Pred2](https://github.com/deemeng/punch_linker2), and
  [embedding pipeline](https://github.com/deemeng/embedding).
- Lite uses five released `cv20_filter_cc5_...protTrans.pth_f*` checkpoints.
  Pred2 averages fifteen released checkpoints: five MSA, five ProtTrans, and
  five MSA-length-10 models. The authors' threshold is strictly `score > 0.07`.
- Exact input requirements are one FASTA record, its matching
  `(1, sequence_length, 1024)` ProtTrans `.npy`, and for Pred2 its
  `(1, sequence_length, 768)` MSA Transformer `.npy`. The source repository
  contains one complete 577-residue example, `DP04257`.
- This repository does **not** redistribute the authors' checkpoints. The
  downloaded repositories reside in ignored `artifacts/third_party/`.
  No license file was present at the checked commits; clarify redistribution
  terms with the authors before packaging their files.
- `scripts/reproduce_linker_pred_inference.py` reimplements the authors'
  three-layer CNN and uses restricted `torch.load(weights_only=True)` with
  narrowly allowlisted NumPy metadata types. It does not execute the authors'
  `main.py`, which includes filesystem cleanup. One checkpoint's output was
  compared against their original network definition on the same input;
  maximum absolute difference was `0.0` on CPU.

## Reproduce the included smoke test

Using a Python environment with `torch`, `numpy`, and `biopython`:

```powershell
git clone --depth 1 https://github.com/deemeng/punch_linker_light.git artifacts/third_party/punch_linker_light
git clone --depth 1 https://github.com/deemeng/punch_linker2.git artifacts/third_party/punch_linker2

python scripts/reproduce_linker_pred_inference.py --model lite --upstream artifacts/third_party/punch_linker_light --fasta artifacts/third_party/punch_linker2/data/input.fasta --prottrans artifacts/third_party/punch_linker2/data/protTrans/DP04257.npy --output artifacts/published-inference/lite-DP04257.json

python scripts/reproduce_linker_pred_inference.py --model pred2 --upstream artifacts/third_party/punch_linker2 --fasta artifacts/third_party/punch_linker2/data/input.fasta --prottrans artifacts/third_party/punch_linker2/data/protTrans/DP04257.npy --msa artifacts/third_party/punch_linker2/data/msaTrans/DP04257.npy --output artifacts/published-inference/pred2-DP04257.json
```

At the checked upstream commits (Lite `d417554e82ed77be42bfa520cbd132f19290b544`,
Pred2 `cdc9e6adb8bde98131f31994ff80b109970fdbfa`), the smoke test
produced 577 scores for each predictor, with 112 Lite and 129 Pred2 residues
above their threshold. Those counts establish that inference runs; they do
**not** establish predictive accuracy or a fair head-to-head benchmark.

The bundled `DP04257` sequence exactly matches its entry in the official
[CAID3 linker reference](https://caid.idpcentral.org/assets/sections/challenge/static/references/3/linker.fasta).
To score this **one bundled example only**:

```powershell
python scripts/score_published_linker_smoke.py --reference data/processed/caid3_linker_reference.fasta --bundled-fasta artifacts/third_party/punch_linker2/data/input.fasta --lite artifacts/published-inference/lite-DP04257.json --pred2 artifacts/published-inference/pred2-DP04257.json --output artifacts/published-inference/DP04257-labelled-smoke.json
```

It has 99 labelled linker residues. The single-sequence AUPRC was 0.8312
for Lite and 0.7968 for Pred2; thresholded F1 was 0.7678 and 0.8246,
respectively. These figures are labelled `not_independent_benchmark` in the
machine-readable report. They cannot be compared to dataset-level scores.

## Before reporting benchmark accuracy

The authors' models were trained on DLD/DisProt. Our preliminary sequence
screen found substantial DLD–CAID3 overlaps, including train-set overlap.
Therefore, first document the upstream training-set provenance and run a
homology-aware exclusion audit on a separately annotated test set. Freeze
that set and its labels, generate the exact ProtTrans/MSA features without
using labels, then score all methods with identical residue-level masks and
metrics. Do not compare the smoke-test counts with our validation AUPRC, and
do not call overlapping examples independent test data.
