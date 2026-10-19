# Published masked DFL splits — preparation result

The original TransDFL `TR166`, `TE82`, and `TE64` files have been converted
without changing their residue labels. The authors' released source confirms
`x` is masked from supervised residue evaluation. The converter
`scripts/prepare_published_dfl_splits.py` writes ignored JSONL files plus a
source-hashed manifest under `data/processed/published_dfl_splits/`.
All 312 records and the manifest pass formal JSON Schema validation; each
sequence length equals its label-string length, no DisProt ID repeats across
sets, and no exact ID matches the CAID3 Linker reference.

| Set and proposed role | Proteins | `1` positive | `0` published negative | `x` masked | Proteins without a positive label |
| --- | ---: | ---: | ---: | ---: | ---: |
| TR166 — train | 166 | 3,670 | 17,552 | 38,337 | 87 |
| TE82 — development | 82 | 2,223 | 11,471 | 23,244 | 44 |
| TE64 — retrospective test | 64 | 949 | 9,307 | 30,065 | 32 |

This solves the immediate *representation* issue: `x` is preserved as an
explicit mask; `0` is the source's negative label, not an inferred absence of
annotation. No-linker examples are present in each published set. It does not
yet establish a fresh independent evaluation. CAID3 is public; earlier
local-alignment screens produced many low-complexity candidate matches and
need a defensible homology exclusion policy. The old TE64 set is a
retrospective published test, not a prospectively blinded one. A model may be
developed on TR166/TE82 with these limitations clearly separated from any
CAID3 or state-of-the-art claim.
