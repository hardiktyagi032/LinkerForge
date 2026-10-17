# Protected competitor-gap round: seed-7 reconciliation (2026-10-17)

Status: three isolated trials completed; no model promoted. The comparison is on CAID3-protected **development**, not CAID3 or an independent test. All used the same train/development/auxiliary hashes, frozen ESM2-35M encoder, seed 7, 510-residue windows, three auxiliary plus twelve DFL epochs, and masked-APS checkpoint selection. The round ledger charged 247.338 seconds (0.069 GPU-hours), below its six-hour cap. GPU was idle when reconciled. Each output manifest records source, config, data hashes, elapsed time, peak PyTorch VRAM, and blacklist pass.

| Head | APS | AUROC | Recall at empirical precision ≥0.90, ≥50 TP | Region recall IoU≥0.5 at threshold 0.5 | No-positive proxy specificity |
| --- | ---: | ---: | ---: | ---: | ---: |
| Matched SAM-like disorder-transfer baseline | .8012 | .9097 | .5706 (723 TP / 79 FP) | 9/28 = .3214 | 14/17 = .8235 |
| Global context | .8269 | .9172 | .6433 (815 TP / 89 FP) | 13/28 = .4643 | 14/17 = .8235 |
| Dilated local | .7829 | .8888 | .5935 (752 TP / 78 FP) | 13/28 = .4643 | 13/17 = .7647 |
| Predicted disorder gate | .7893 | .9181 | .5209 (660 TP / 73 FP) | 0/28 = 0 | 13/17 = .7647 |

The global-context head is the **only** one with a positive seed-7 APS difference (+.0257), higher high-precision recall (+.0726), and no loss on the preregistered 17-protein specificity proxy. It is therefore eligible for seed-17 and seed-31 repetition on the same protected data. A single seed is not evidence of generalization. The other two heads failed the ≤.02 absolute specificity-loss guardrail: each lost 1/17 = .0588. They are not repeated in this round. The proxy has partial unknown masks and is not a verified no-linker test.

The preregistered Fmax checkpoint rescoring has **not yet been completed** for these new heads; this is an outstanding metric, not silently replaced by APS. No CAID3 labels, per-protein results or scores were inspected for this decision.

Provenance: `artifacts/dfl-competitor-gap-round-2026-10-17/ledger.json`, config SHA-256 `67b20729cb81bce59eb10f85dbfc52c81643700802ec3bd60336eb4234e6b519`, protected data-manifest SHA-256 `a8f5348c6b6d2845e51bc12fdba0b1dcf02c33b22039baa04cab91069b792d24`, runner SHA-256 `d75ac9d9955d41951c9c328fd8af30592a2235a691daad4b13a47a2b69f46d3b`, model source SHA-256 `808384f8c8e54b96fb52215316a7a54721ecdded39e5f7daf8e118790bd605f1`. Matched baseline: `artifacts/dfl-caid3-protected-baselines-2026-10-16/samlike-disorder_transfer-seed7/manifest.json`.
