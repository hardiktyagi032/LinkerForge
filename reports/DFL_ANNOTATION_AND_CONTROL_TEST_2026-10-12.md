# DFL annotation crosswalk and control test (12 October 2026)

## Result

The 50-case packet was cross-referenced against the locally archived
[DisProt](https://disprot.org/) 2026_06 **explicit flexible-linker** regions,
requiring the same DisProt ID, an exact full-protein sequence match, and a
coordinate overlap. This produced **one curated-overlap case among the 20
model-nominated TE82 `x` regions**. Its 20-residue candidate lies wholly in a
curated flexible-linker interval (20/20 overlap; evidence reference PMID
8175654). The older TE82 source had masked all 20 residues as `x`; the frozen
CNN assigned this particular model-selected window a mean score of 0.973.
This is an annotation crosswalk, **not** a blinded independent discovery or
proof that the other 19 cases are false positives.

Evidence clarification: this DisProt region was recorded with release
`2022_03`, so the result does **not** establish that the annotation first
appeared in 2026 or that it was unavailable when TE82 was assembled. The
linked [1994 primary paper](https://pubmed.ncbi.nlm.nih.gov/8175654/)
studied a flexible connection between the DNA-binding and trimerization
domains of yeast heat-shock transcription factor. It discusses a proposed
21-residue linker plus an additional 52-residue intervening region; the
DisProt annotation spans 73 residues. Therefore the exact candidate window
has **curated-region support**, not independent experimental proof that each
of its 20 residues is a functional linker.

| Original packet category | Cases | Exact-sequence curated linker overlaps |
|---|---:|---:|
| Model-nominated unknown | 20 | 1 |
| Random unknown | 10 | 0 |
| Published positive control | 10 | 5 |
| Published negative control | 10 | 0 |

One positive control has a same-ID sequence mismatch between sources and was
not coordinate-mapped. The five positive controls without an exact-sequence
overlap therefore demonstrate that this particular DisProt extract is
**incomplete as an adjudicator**; absence from it must not be promoted to a
negative label. The one-versus-zero unknown comparison is uninformative at
this sample size (two-sided Fisher test, p = 1.0). No `x` residue was
automatically relabelled in training data.

The frozen CNN was then evaluated on the **20 published-label controls** only
(10 positive, 10 negative), scoring each preselected segment by its mean
residue probability. It obtained AUROC **0.81** and average precision
**0.849** (chance AP at this 50/50 control prevalence is 0.50). This is a
retrospective sanity check, **not a generalization test**: TE82 was used for
development/model selection; the controls are small, selected from that
split, and their older published labels are not independent expert decisions.
The model-selected `x` case was excluded from this control metric.

## Annotation status and next gate

Only one unknown case has explicit curated-positive support from the exact
crosswalk. The other 29 unknown cases (19 nominated, 10 random) remain
**unresolved**, not negative. Independent reviewers should complete the
[pseudonymous sequence-only packet](</C:/Users/Perthro/Documents/ChatGPT/Folddiffusion/reports/dfl_te82_sequence_only_review_packet_2026-10-12.json>)
before seeing any source accessions, coordinates, categories, model scores,
or this crosswalk. A second-stage review needs domain/context evidence;
sequence composition alone cannot prove interdomain linker function.

The private case-level crosswalk, key, and control scores are in Git-ignored
`artifacts/` to avoid accidentally unblinding reviewers. They have source,
checkpoint, script, and commit hashes. The public summary intentionally
withholds the case ID. No weights were updated, no CAID3/TE64 labels were used
for selection, and no new performance claim is warranted.

Relevant source definitions: [DisProt](https://disprot.org/),
[TransDFL](https://doi.org/10.1016/j.gpb.2022.10.004), and the
[CAID3 assessment](https://pmc.ncbi.nlm.nih.gov/articles/PMC12750029/).
