# DFL cross-domain transfer: bounded round result

This development-only round completed three architecture/loss trials (one seed each) on the same published TR166/TE82 masked-residue contract and frozen ESM2-35M encoder. The third trial adapted the *minimum precision constraint* idea of [Rath and Hughes (AISTATS 2022)](https://proceedings.mlr.press/v151/rath22a.html) to a smooth batchwise count penalty added to BCE. It does **not** reproduce their tight sigmoidal bounds or clinical results. The hypothesis and competing mechanisms are recorded in `literature/DFL_CROSS_DOMAIN_METHODS_2026-10-12.md`.

| TE82 development metric | Residue CNN | Span head | Precision-loss CNN |
| --- | ---: | ---: | ---: |
| Masked residue APS, selected epoch | 0.4501 | 0.4549 | **0.4970** |
| Masked residue AUROC | **0.7734** | 0.7488 | 0.7592 |
| Residue recall at empirical precision >=90%, >=50 TP | No eligible point | 195/2,223 = 8.77% | **210/2,223 = 9.45%** |
| Region recall, IoU >=0.5 at per-model TE82 F1 threshold | **29/46 = 63.0%** | 26/46 = 56.5% | 26/46 = 56.5% |
| Region precision, same rule | **29/139 = 20.9%** | 26/144 = 18.1% | 26/150 = 17.3% |
| No-positive scored-residue specificity, same rule | 19/44 = 43.2% | 24/44 = 54.5% | 22/44 = 50.0% |

At the precision-loss model's >=90% residue-precision threshold: 210 TP, 23 FP, 90.13% precision; 39/44 no-positive proteins clear (88.6% specificity), but only 4/46 linker regions match at IoU >=0.5. Compared with the plain CNN, APS rises by 0.0469 absolute, close to but below the provisional +0.05 material-win target, while region recovery worsens. Compared with the span head, high-precision recall increases by 15 residues but no-positive specificity falls from 40/44 to 39/44 (2.27 percentage points), marginally beyond the 0.02 absolute guardrail. These are single-seed, development-selected results and are not generalization evidence.

The data screen `reports/dfl_tr166_te82_similarity_screen_2026-10-12.json` found no exact TR166/TE82 sequence duplicate or top-20 local-alignment flag at the prespecified >=50% identity and >=70% one-sided coverage. This is **not** homology/family-independence certification. Unknown `x` residues remained masked and were never converted to negatives. TE64 and CAID3 were not used to select this model. Published competitor scores on TE82 were not yet obtained, so no contemporary-baseline superiority claim is possible.

Third-trial provenance: checkpoint `artifacts/dfl-precision-seed7-001/best.pt`, SHA-256 `b9002d55670e5e6a95788d03190bbe5c5ae86a5bd2de1f2611022a9352a66b3a`; source SHA-256 `9710507c5763f6df9da340d5019f01d865081787334e0a0d22330e7e08b4959f`; TR166 SHA-256 `8fbfa1a503857131b8e485f511f5c84d9fbea24b9d5bbac2aa003508cb4f716c`; TE82 SHA-256 `f15ac3eef1edc45b95bc600d661dab348a0cb0bee11e47febeac356ef93db916`; config SHA-256 `4da3727a6d93ef252695f47b8de3631d1174a1e76126030f3f719b8b00c4d485`; pipeline commit `4519cab377c531e0dc3131a8136654b2a98844c3`. Six epochs took 46.062 seconds; peak allocated PyTorch VRAM was 242,914,816 bytes. Raw epoch scores, training logs, manifest and interval audit are retained in isolated artifacts and `reports/dfl_precision_te82_region_audit_2026-10-12.json`.

Disposition: **promising residue ranking mechanism, failed interval-recovery criterion; not promoted**. Next work is family-cluster validation, matched published predictor inference on common sequences, and an annotation audit for whether partial-label methods are scientifically valid. A new bounded round must be documented before more GPU experiments. An independent test and multiple seeds are prerequisites to any paper-level improvement claim.
