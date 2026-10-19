# DFL direct-versus-disorder-transfer paired round (old data)

Status: **completed as a development-only exploratory round**. The original suite was interrupted when one YOLO-1D trial recorded a long host-suspension interval after one epoch; the continuation reran that invalid trial and the five missing trials in isolated output. All 12 planned architecture/condition/seed combinations finished 12 DFL epochs. The interrupted one-epoch run is excluded. Original and continuation ledgers are `artifacts/dfl-disorder-transfer-2026-10-13/ledger.json` and `artifacts/dfl-disorder-transfer-resume-2026-10-16/ledger.json`.

| Architecture and condition | TE82 masked-residue APS, mean of seeds 7/17/31 | AUROC mean | Recall at empirical precision ≥0.90 mean |
| --- | ---: | ---: | ---: |
| SAM-like, direct | 0.682 | 0.864 | 0.392 |
| SAM-like, disorder transfer | 0.672 | 0.881 | 0.301 |
| YOLO-1D, direct | 0.494 | 0.795 | 0.061 |
| YOLO-1D, disorder transfer | 0.573 | 0.816 | 0.145 |

These are rounded descriptive means of each run's **best TE82 development epoch**, not a held-out test. The source, data, and config hashes are recorded in every run manifest. SAM-like transfer is not consistently beneficial: its seed-7 APS increased, but seeds 17 and 31 decreased. YOLO-1D transfer improved APS at all three tested seeds on this old-data development condition, but remained below SAM-like. Per-seed region recall also varies sharply; a high residue APS is not sufficient evidence of reliable linker-span boundaries. No model is promoted.

This round used the **unfiltered** TR166/TE82 training/development files and a DisoFLAG auxiliary pilot. Candidate CAID3 sequence similarities were subsequently identified. Therefore these checkpoints must not support a CAID3 independence or state-of-the-art claim. The next baseline round must run on the versioned CAID3-protected data after a fresh blacklist preflight, and its results cannot be compared with this round as if only architecture changed. CAID3 remains public and previously viewed even after filtering.
