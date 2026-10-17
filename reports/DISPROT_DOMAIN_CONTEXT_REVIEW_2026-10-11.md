# DisProt/Pfam linker-context review — 2026-10-11

This is a deterministic triage of the four records in
`disprot_domain_context_review_queue_2026-10-11.json`, **not** manual
adjudication, a validated two-domain linker set, or an independent test.

| DisProt region | UniProt | Explicit interval | Pfam gap | Shared residues | Triage note |
| --- | --- | --- | --- | ---: | --- |
| DP00865r003 | Q6P3W2 | 77–92 | 80–95 | 13 | Annotation overlaps the end of domain A by 3 residues. |
| DP04129r025 | P42858 | 2067–2095 | 2063–2091 | 25 | Annotation overlaps the start of domain B by 4 residues; same protein and gap as r027. |
| DP04129r027 | P42858 | 2067–2090 | 2063–2091 | 24 | Nested, shorter annotation of the same protein/gap as r025; do not count as independent. |
| DP04438r004 | Q86YT6 | 315–331 | 312–332 | 17 | Same Pfam family on both flanking assignments; verify repeat/domain boundaries. |

All four explicit and gap sequences match their one-based inclusive slices of
the source UniProt sequence. All four gaps lie exactly between the two Pfam
assignments. Thus the queue comprises four annotation records but only three
unique proteins and three distinct domain gaps. These consistency checks do
not establish that the structures are resolved or that their linker regions
form a suitable domain-pair benchmark.

Next review requires checking the original DisProt evidence and Pfam domain
definitions, resolving the duplicate P42858 annotations, mapping UniProt
coordinates to experimental PDB chain residues, and a stronger homology audit
against every DLD split. No queue record enters training or validation before
those checks pass. DLD fold 5 remains previously viewed, not a fresh blind set.
