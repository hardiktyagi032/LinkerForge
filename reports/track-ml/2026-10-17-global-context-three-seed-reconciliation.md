# Global-context three-seed protected-development reconciliation — 2026-10-17

Status: repeat round completed, **not promoted**. Both seed-17 and seed-31 trials exited 0 after the protected-data blacklist passed before each run. Ledger charged 161.626 seconds (0.045 GPU-hours), below the six-hour cap. No CAID3 label, score, or per-protein result was used.

| Seed | Matched SAM-like APS | Global-context APS | Matched recall@precision≥.90 | Global-context recall@precision≥.90 | Matched proxy specificity | Global-context proxy specificity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 7 | .8012 | .8269 | .5706 | .6433 | 14/17 | 14/17 |
| 17 | .8041 | .8536 | .5927 | .6425 | 13/17 | 12/17 |
| 31 | .7702 | .7537 | .5138 | .5328 | 13/17 | 12/17 |

Mean APS is .7918 for the matched baseline versus .8114 for global context, an exploratory +.0196. The variant improves APS in 2/3 seeds and high-precision recall in 3/3 seeds. However, it loses 1/17 = .0588 absolute proxy specificity at each of seeds 17 and 31, beyond the preregistered ≤.02 loss guardrail. Its APS is also worse at seed 31. Consequently, the three-seed result does **not** warrant promotion or a superiority claim. The 17-protein measure is a partially masked no-positive proxy, not verified no-linker specificity; the guardrail is nevertheless applied as preregistered. Fixed-threshold span recovery is variable across the repeats (5/28 at seed 17, 15/28 at seed 31), so residue APS is not evidence of reliable boundaries.

Fmax rescoring of the APS-selected checkpoints is now complete, using exact score ties on the same known development residues, with no checkpoint reselection. At seeds 7/17/31, matched-baseline Fmax was .7152/.7193/.6722; global-context Fmax was .7548/.7597/.6741. The gains are positive but variable and **do not reverse** the preregistered guardrail failure. The machine-readable checkpoint hashes and Fmax details are in `reports/track-ml/2026-10-17-global-context-fmax.json`; the scorer is `scripts/score_protected_global_context_development.py`. A next architecture round requires its own independent preregistration and matched baseline, not CAID3 retuning.

Evidence: `artifacts/dfl-global-context-repeat-2026-10-17/ledger.json` and per-run manifests; original seed-7 manifest `artifacts/dfl-competitor-gap-round-2026-10-17/global_context/manifest.json`; matched baselines `artifacts/dfl-caid3-protected-baselines-2026-10-16/samlike-disorder_transfer-seed{7,17,31}/manifest.json`. Repeat data-manifest SHA-256 `a8f5348c6b6d2845e51bc12fdba0b1dcf02c33b22039baa04cab91069b792d24`, repeat config SHA-256 `3175b15c20908697e9f0618968bf63ed43bd3342f5dd9932094ba9da4f134f2e`, runner SHA-256 `d7e34740b29f731d3b7465da1c6851b7b12dd3ab56babec0a870355582cdb5d4`, model source SHA-256 `808384f8c8e54b96fb52215316a7a54721ecdded39e5f7daf8e118790bd605f1`.
