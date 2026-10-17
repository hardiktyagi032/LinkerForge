# DFL negative-label semantics audit — 11 October 2026

Training remains **gated**. This audit identifies a defensible candidate
masking rule, not an approved training set.

[APOD, Methods 2.1](https://academic.oup.com/bioinformatics/article/36/Supplement_2/i754/6055918)
explicitly excluded residues without functional annotations and used
non-DFL-functionally annotated disordered residues plus structured residues
as negatives. It also grouped proteins at 25% sequence identity before
splitting. We should reproduce this *label policy* only after reconciling
DisProt 2026 ontology and coordinate overlaps; we must not inherit APOD's
reported accuracy as a LinkerForge result.

The local 2026_06 DisProt response has 3,337 entries. Excluding the 31 public
CAID3 reference entries leaves 329 proteins with 419 explicit `IDPO:0000033`
flexible-linker regions. On those 329 proteins the response also contains
7 explicit `IDPO:0000006` order regions and 923 `IDPO:0000002` disorder
regions. These are *region counts*, not unique residues or verified negative
counts. There are 371 regions with terms outside the seven broad structural
state/linker terms used in this quick inventory; not all of them are distinct
non-linker functions, and some may overlap a DFL. The inventory was computed
from `data/raw/disprot/disprot_2026_06_regions.json` after exact DisProt-ID
exclusion via `artifacts/caid3-linker.fasta`.

Proposed per-residue tri-state precedence for a future extraction:

1. A curated DFL region is positive, subject to valid coordinates and
   conflicting-annotation review.
2. An explicitly ordered region *may* be negative only where it does not
   overlap a DFL or conflicting disorder annotation.
3. A disordered region with an explicit, ontology-confirmed non-DFL function
   *may* be negative only after checking functional-term meaning and overlap.
4. Everything else is unknown and masked from supervised loss and held-out
   metrics. In particular, an unannotated residue is not a negative.

This policy still needs an executable overlap audit, independent homology
clustering, no-linker-protein adjudication, and a frozen development split.
Until those checks pass, no DFL GPU run or CAID3 model selection is justified.
