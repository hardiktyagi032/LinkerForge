# First masked-DFL CNN baseline — development result

The bounded frozen-ESM2-35M residue-CNN trial completed all six epochs on
TR166. `x` residues were excluded from loss and TE82 scoring. The best model
was selected on **TE82 development** average precision (APS) at epoch 4,
not on TE64 or CAID3. Its output is
`artifacts/dfl-cnn-seed7-001/` (manifest, epoch log, checkpoint).

| Development measure | Value |
| --- | ---: |
| Masked TE82 APS, best epoch | 0.4501 |
| Masked TE82 AUROC at that epoch | 0.7734 |
| Scored positive / negative residues | 2,223 / 11,471 |
| Eligible recall at empirical precision >=0.90 with >=50 TP | None |
| Runtime / peak PyTorch VRAM | 62.39 s / 242,914,816 bytes |

The training, development, config, and source hashes in the manifest were
verified against current files. Best checkpoint SHA-256:
`3e41d94048b60581ed7321f723d5c3c77e48a68465ef031172d93b196a2c05d1`.
No numerical comparison with published APOD, TransDFL, or CAID scores is
valid until run on matched examples and masks. This is one seed on a
historically public development set, **not** a blind or publishable win.

The model did not find a threshold with at least 50 true-positive residues
and empirical precision >=0.90. No-positive-protein specificity at such a
threshold is therefore undefined, not zero or one. Region IoU and boundary
errors still require a frozen evaluation pass before comparing a span-aware
variant. The manifest records a null resolved backbone commit; future runs
must pin or otherwise independently verify the exact cached model revision.

The subsequent [schema-validated TE82 interval audit](./dfl_cnn_te82_region_audit_2026-10-12.json)
used the frozen best checkpoint and chose a **development-only** threshold
maximizing masked-residue F1 (0.2261). At that threshold residue precision is
0.4168 and recall 0.5502 (1,223 TP, 1,711 FP). There are 46 annotated linker
regions, 139 predicted regions after masking `x`, and 29 one-to-one matches
at IoU >=0.5: region precision 0.2086, region recall 0.6304. Only 19 of 44
TE82 proteins without a positive label have no prediction on their *scored*
residues (specificity 0.4318). These values reveal substantial false-positive
burden. They are not independent performance estimates; the threshold was
selected on TE82 itself. `x` positions are excluded from this specificity
measure and should not be interpreted as verified no-linker residues.
