# LINKER-Pred2-style source preparation (13 October 2026)

This is a **reproducible source pool**, not a reconstruction of LINKER-Pred2's
unreleased row-level training split or a finished 2,000-protein DFL training
set. No model training was launched by this preparation.

## Primary-source basis

- [LINKER-Pred2 repository](https://github.com/deemeng/punch_linker2) states
  that its >2,000-example collection combines DLD and DisProt. Its released
  code does not identify the exact row-level train/validation membership.
- [DLD download page](https://pcrgwd.ucd.ie/linker/download/) describes the
  structural IDL/DDL/loop/domain/terminus codes. Its raw code 0 is not
  defined there. The existing local converter mapped that code and known
  nonlinker classes to 0, losing their distinction. This new pool therefore
  masks **all** converted zeros (`x`) in the DLD candidate arm.
- [DFLpred](https://pmc.ncbi.nlm.nih.gov/articles/PMC4908364/) and
  [APOD](https://pmc.ncbi.nlm.nih.gov/articles/PMC7773485/) exclude unlabeled
  DisProt residues and use annotated non-DFL positions as negatives. The
  present DisProt extract records explicit flexible-linker **positives** only;
  every other position stays `x`, not 0.
- [TransDFL](https://pmc.ncbi.nlm.nih.gov/articles/PMC10626177/) publishes
  TR166/TE82/TE64. Only TR166 is considered here; its original `1/0/x`
  labels are preserved. TE82 and TE64 remain protected retrospective tests.

## Reproduction

Run from the repository root:

```powershell
.venv-gpu\Scripts\python.exe scripts\prepare_linker_pred2_style_pool.py
.venv-gpu\Scripts\python.exe -m unittest tests.test_linker_pred2_style_pool
```

The generated records and manifest are in
`data/processed/linker_pred2_style_pool_v1/`. They are ignored data artifacts,
not committed source files. Formal contracts are
`schemas/linker-pred2-style-pool-record.v1.schema.json` and
`schemas/linker-pred2-style-pool-manifest.v1.schema.json`. The manifest records
input hashes, configuration hash, source IDs, pipeline commit, and output
hashes. Rebuilding from the same local source snapshots reproduces the
record sets; byte hashes can differ if software or serialization changes.

## Actual output

| Arm | Proteins | Status |
| --- | ---: | --- |
| Published TR166 DFL | 158 | Original negatives and unknown mask retained; 8 records quarantined on exact protected/duplicate-sequence rules. |
| DLD structural IDL/DDL | 1,556 | Auxiliary **candidate**, not CAID DFL labels; four records quarantined by exact-overlap rules. Converted zeros are masked. |
| DisProt explicit flexible linker | 159 | Positive-only candidate; 201 proteins quarantined by exact protected/cross-source overlap or the existing conservative DLD homology-candidate screen. |
| Quarantine, all sources | 213 | Excluded from the three active arms, retained with reason and provenance. |

Total source records processed: 2,086 (166 TR166 + 1,560 DLD training + 360
DisProt proteins). The final counts above sum to the same total. DLD
validation/blind and TE82/TE64 are protection inputs, never copied into the
training pool. All CAID3 reference IDs and exact sequences are protected.

The 158 TR166 records are the only directly labeled DFL training arm here.
The DLD and DisProt arms are *not* cleared for supervised DFL training, and
the three counts must not be reported as 1,873 interchangeable DFL proteins.
The candidate homology screen is not an independent family-level certificate.
Before a larger experiment, recover DLD raw classes, adjudicate source label
conflicts, complete homology/family separation across all sources and protected
tests, and build a development split with verified non-DFL negatives.
