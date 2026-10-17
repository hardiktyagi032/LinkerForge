# Protected-split no-positive proxy audit

Read-only count of the frozen `data/processed/caid3_protected_dfl_v1/{train,development,auxiliary}.jsonl` records on 2026-10-17. The split manifest SHA-256 is `a8f5348c6b6d2845e51bc12fdba0b1dcf02c33b22039baa04cab91069b792d24`. A no-positive protein here means its label string contains no `1`; all counted records contain at least one `0`, so none are entirely masked.

| Split | Proteins | No-positive labelled proteins | Entirely unknown among those |
| --- | ---: | ---: | ---: |
| Train | 79 | 32 | 0 |
| Development | 42 | 17 | 0 |
| Auxiliary disorder | 72 | 0 | 0 |

The development proxy specificity is based on only **17 proteins**, so its smallest nonzero change is 1/17 = **0.0588**. The preregistered maximum loss of 0.02 absolute therefore amounts, on this split, to *no additional false-positive protein at all*. This explains why a modest APS gain could not pass the guardrail, but does not justify retrospectively relaxing it after seeing outcomes. The `0` labels are published negatives under TransDFL's label semantics; these 17 proteins have not been separately adjudicated as truly linker-free natural proteins. Therefore the measure is a **proxy**, not a validated no-linker specificity estimate.

Before another claim-oriented round, audit negative-label provenance and obtain a larger independently adjudicated no-linker set with family-aware splitting. Do not use the public CAID3 result to select new architectures or tune this guardrail.

Follow-up coverage audit: `scripts/audit_protected_no_positive_coverage.py` generated `reports/dfl_protected_no_positive_coverage_2026-10-17.json` after checking frozen split hashes. Among the 17 development no-positive records, the median fraction of residues explicitly labelled `0` is **0.722**; the minimum is **0.402**. The remaining positions are masked `x`, not confirmed nonlinkers. The corresponding train values across 32 records are median **0.761**, minimum **0.403**. Thus the proxy's denominator is small *and* many of those proteins have substantial unknown regions; calling it whole-protein linker-free specificity would be incorrect. The audit does not adjudicate whether source `0` labels represent actual absence of linker function.
