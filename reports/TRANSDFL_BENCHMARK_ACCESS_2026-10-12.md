# Original TransDFL benchmark access — 12 October 2026

The original [TransDFL benchmark page](http://bliulab.net/TransDFL/benchmark/)
is reachable. Its linked `TR166.txt`, `TE82.txt`, and `TE64.txt` were fetched
unchanged into ignored `artifacts/transdfl-benchmark-original/`. The
reproducible parser `scripts/audit_transdfl_benchmark.py` produced
`reports/transdfl_benchmark_audit_2026-10-12.json`, validated against
`schemas/transdfl-benchmark-audit.schema.json`. The record stores source URLs,
SHA-256 hashes, sequence lengths, and exact-ID overlap checks.

| Original set | Proteins | Residues | `1` | `0` | `x` |
| --- | ---: | ---: | ---: | ---: | ---: |
| TR166 | 166 | 59,559 | 3,670 | 17,552 | 38,337 |
| TE82 | 82 | 36,938 | 2,223 | 11,471 | 23,244 |
| TE64 | 64 | 40,321 | 949 | 9,307 | 30,065 |

All files have three lines per protein (ID, sequence, label string), valid
sequence/label lengths, unique IDs within each set, and no exact DisProt-ID
overlap between sets or with the 31 CAID3 reference proteins. The label
alphabet includes **`x`**, not just 0/1. The
[APOD methods](https://academic.oup.com/bioinformatics/article/36/Supplement_2/i754/6055918)
say unannotated residues were excluded; the
[TransDFL methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC10626177/)
describe TR166 fine-tuning and TE82/TE64 tests. This encoding has now been
checked against the authors' [released source-code archive](https://ngdc.cncb.ac.cn/biocode/tools/BT007312),
downloaded unchanged as ignored
`artifacts/transdfl-benchmark-original/TransDFL_source_code.zip` (SHA-256
`0ba5bb72be093ae30abdf6b8642a9cd7f1407782c66cdcbad3421577b8ab257c`).
In `prepare_data.py`, `residue_mask` assigns mask 1 only to label `1` or `0`
and mask 0 to everything else; `lable_2_value` converts non-`1` characters
to a numeric 0, but the mask excludes those positions. `evaluator.py`
likewise appends labels/predictions only for 0 and 1. Thus the **operational
meaning of `x` is confirmed: excluded from supervised residue loss and
evaluation, not a negative**. The paper's annotation protocol suggests many
`x` positions lack usable functional labels, but the archive does not by
itself prove one biological reason for every `x` position. Preserve it as
*masked/unscored*, not as a definitive biological class.

This substantially improves access to a historically used DFL training
source with explicit masked positions, but is **not** a fresh independent test.
TR166/TE82 are older public sets; TE64 is also published. CAID3 exact IDs are
absent, but sequence homology against CAID3 and modern DisProt remains to be
audited. Baselines and new models must share the same frozen, masked split.

An additional current-DisProt accession/UniRef screen mapped 155/166 TR166,
77/82 TE82, and 63/64 TE64 proteins to the local 2026_06 release. Their
exact full sequences matched in 153, 74, and 62 cases respectively. None of
the mapped proteins shares a nonempty UniRef50 or UniRef90 cluster identifier
with the 31 CAID3 proteins. This is useful triage but **not a complete
homology clearance**, especially for the unmapped or sequence-changed records;
the sequence-level screen remains mandatory before training or test claims.

An initial all-pairs *local-alignment candidate screen* has now scored every
TR166/TE82/TE64 sequence against all 31 CAID3 sequences (5,146, 2,542, and
1,984 pairs). It uses parasail 1.3.4 Smith–Waterman with BLOSUM62 and flags
local identity >=25% over >=50 aligned positions. The screens completed and
are schema-validated in `reports/transdfl_{tr166,te82,te64}_caid3_similarity_2026-10-12.json`.
They flag 1,031, 573, and 507 pairs respectively—**many likely short or
low-complexity matches**, not adjudicated homologs. Even a post hoc >=60%
shorter-sequence alignment-length proxy leaves 144, 51, and 23 pairs. This
screen therefore does *not* clear CAID3 independence or provide a usable
exclusion list. A reproducible clustering method with coverage and
low-complexity handling, followed by manual review of borderline matches,
is the next gate. No GPU training was launched on these preliminary flags.
