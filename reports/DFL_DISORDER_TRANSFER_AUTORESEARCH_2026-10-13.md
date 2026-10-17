# DFL disorder-transfer autoresearch round — 13 October 2026

Status (16 October): **original suite interrupted; controlled completion running**.
The original launcher was PID `5300`. Its ledger reports `time_budget_exhausted`,
but this is not six GPU-hours of training: six trials finished all 12 DFL
epochs in a combined 1,260.623 seconds; the seventh, YOLO-1D direct seed 17,
stopped after one epoch with a recorded 42,258.906-second elapsed interval.
That interval is consistent with a host suspension/clock gap, not demonstrated
GPU activity. The interrupted trial is invalid for the paired comparison.
The original artifacts remain untouched. A separate continuation ledger is
`artifacts/dfl-disorder-transfer-resume-2026-10-16/ledger.json`; its launcher
repeats the interrupted trial and runs the five missing trials sequentially,
with source/config hash checks and no duplicate of the six completed trials.
It stops on another incomplete run or an accounting anomaly. The full paired
comparison remains pending; no independent benchmark claim is warranted.
The immutable comparison config is
`configs/dfl_disorder_transfer_autoresearch_2026-10-13.json`; the runner is
`scripts/run_dfl_disorder_transfer.py`. Live state and per-trial logs are in
`artifacts/dfl-disorder-transfer-2026-10-13/` (ignored local artifacts).

## Research question and matched design

Inspired by [TransDFL](https://pmc.ncbi.nlm.nih.gov/articles/PMC10626177/),
does learning *general intrinsic disorder* before DFL fine-tuning improve the
same SAM-like or YOLO-1D segmenter compared with direct DFL training?
This is a transfer-principle adaptation, **not** a reproduction of its RFPR-IDP
weights, its 2,645/1,077 IDR split, or its exact feature stack.

Each architecture has `direct` and `disorder_transfer` conditions at paired
seeds 7, 17, and 31. The ESM-2 35M encoder is frozen; architecture, TR166
DFL training labels, TE82 development labels, 12 DFL epochs, batch size,
optimizer, learning rate, and evaluation are matched within architecture.
The transfer arm alone gets three semantic-only IDR epochs before the same
DFL fine-tuning. It therefore uses extra data and compute by design;
runtime and VRAM must be reported. All 12 trials run sequentially on the
local 6 GB GPU with separate outputs, a maximum 30 minutes per trial and
six GPU-hours total. The suite stops on a failed trial or time budget.

Primary development endpoint: masked-residue APS on TE82. Secondary:
AUROC, maximum recall at empirical precision >=0.90 with >=50 true-positive
residues, a no-positive-protein *proxy* specificity, and region recall at
IoU>=0.5 under a fixed score-0.5 decoder. This proxy is not independently
verified no-linker specificity. TE64 and CAID3 are not opened by the runner.

## Auxiliary data and leakage limitations

The source is [DisoFLAG's published training file](https://github.com/YihePang/DisoFLAG/tree/main/dataset),
line 3 IDR labels only. Source SHA-256:
`6f8f0d9f9f446fac9838e5a2b4d746e068943daa36f54052a74b3379aeded2f8f`.
The preparation script `scripts/prepare_disorder_transfer_pilot.py` retained
110 of 589 proteins: 130 were exact protected-ID/sequence matches and 349
were conservatively flagged by local-alignment similarity to TR166, TE82,
TE64, or CAID3. The retained pool has 8,366 IDR-positive and 40,996
IDR-negative residues under DisoFLAG's published track. The screening
threshold is >=30% identity, >=50 aligned residues, >=50% coverage of the
shorter sequence. This is a candidate-homology filter, not a substitute for
all-family clustering; the retained 110 are **not certified independent**.
The auxiliary snapshot and manifest are under
`data/processed/disorder_transfer_pilot_v1/`.

TE82 has already been viewed in this project, so this is a development-only
pilot. Even a substantial paired improvement would require a subsequently
frozen model and untouched, homology-audited test before a superiority claim.

## Execution checks

Before suite launch, both architectures completed GPU smoke runs including
all three auxiliary epochs and at least one DFL development evaluation.
These time-limited smoke results are diagnostic only and are **not** included
in the paired comparison. The suite was started as a hidden independent
Windows process and can continue when this chat ends. Do not start another
GPU training process while its ledger status is `running`.

Once complete, reconcile all 12 trial manifests, hashes, missing/failing
trials, paired seed differences, and interval metrics. No model is promoted
automatically and no paper claim follows from this round alone.

## Final ledger reconciliation (17 October 2026)

The old-data exploratory queue is **not complete**: its ledger ended `time_budget_exhausted` after 7/12 planned jobs. Six manifests are `completed`; `yolo1d-direct-seed17` exited code 0 but its manifest is `time_limit`, so it is **not** a completed paired trial. The remaining five jobs never started. No relevant Python/GPU process remains. The elapsed ledger time includes a long suspension/clock gap and cannot be interpreted as seven trials consuming 12.1 GPU-hours. This queue must not be silently resumed or represented as a full three-seed architecture comparison. Later CAID3-protected baseline and SAM rounds use different filtered data and are reported separately; their results supersede this old-data pilot for model-selection purposes, without turning old-data numbers into comparable protected-data scores.
