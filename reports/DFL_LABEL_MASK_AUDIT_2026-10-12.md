# DisProt DFL residue-mask audit — 12 October 2026

`scripts/audit_disprot_dfl_label_masks.py` generated
`reports/disprot_dfl_label_masks_2026-10-12.json`, validated against
`schemas/dfl-label-mask-audit.schema.json`. The record includes source,
script, CAID3-reference, and repository-commit hashes plus per-protein counts.
It excludes all 31 exact CAID3-reference DisProt IDs before counting.

| Category in 329 remaining DFL-annotated proteins | Residues |
| --- | ---: |
| Total | 233,315 |
| Explicit flexible-linker positive | 14,304 |
| Candidate non-DFL function within annotated disorder | 1,209 |
| Candidate explicit order without disorder conflict | 0 |
| Unknown / masked | 217,802 |

Additional overlap diagnostics: 49 residues have both DFL and explicit order;
382 have DFL and another disorder-function annotation; 296 have order and
disorder annotations. Coordinates were valid in all processed regions. DFL
positives take precedence for this *inventory*, but those 49 contradictory
DFL/order residues need adjudication before training.

The 1,209 are **candidate** negatives, not final verified negatives: functional
term semantics, evidence, and overlaps require review. The zero order-derived
candidate count results from conservative exclusion of order/disorder
conflicts, not a claim that no ordered residues exist. No missing annotation
was turned into a negative. This strongly confirms that naive binary labeling
would make most of this dataset speculative. Homology clustering, no-linker
proteins, a frozen split, and an independent test remain unbuilt, so GPU DFL
training is still gated.

Distribution check: only **24 of 329 proteins** contain any candidate
negative residues. One protein, DisProt `DP04070`, contributes **560/1,209
(46.3%)** of them; its annotated flexible N- and C-terminal tails account
for much of this count. Four proteins have DFL/order conflicts, and 17 have
DFL/other-function overlaps. This concentration would make a nominal
residue-level negative count misleading; a protein-group split could leave
almost no candidate negatives in a fold. The 217,802 unknown residues are
93.35% of the audited positions. A reviewed negative source and explicit
per-protein split feasibility test are therefore prerequisites, not optional
cleanup.
