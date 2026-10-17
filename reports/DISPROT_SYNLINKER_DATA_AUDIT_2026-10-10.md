# External linker-data acquisition audit (2026-10-10)

## DisProt: acquired, screened, not labelled as linkers

The public [DisProt API](https://disprot.org/help) was queried at
`https://disprot.org/api/search?release=2026_06&show_ambiguous=false&show_obsolete=false&format=json&get_consensus=false`.
The raw JSON is retained locally at `data/raw/disprot/disprot_2026_06_regions.json` (ignored by Git; SHA-256
`1fdfce26a3ea9b626e63559f36abd86e023b50b612dc2c8756acbb08edead140`; 28,301,361 bytes).
The API returned 3,337 entries. The release parameter is pinned to `2026_06`, consistent with the
[DisProt release notes](https://disprot.org/release-notes). Reproduction requires fetching the URL again and
checking its hash; a later server revision may require an archived source copy.

`python scripts/screen_disprot_linker_context.py --input data/raw/disprot/disprot_2026_06_regions.json --output data/processed/disprot_2026_06_domain_gap_screen.jsonl`
produced 291 review candidates from 245 DisProt entries. The script selects 5–30-residue gaps between
adjacent non-overlapping Pfam assignments only when a curated DisProt *disorder* region overlaps the gap.
The output and machine-readable manifest are ignored derived data under `data/processed/`.
The record contract is `schemas/disprot-domain-gap-screen.schema.json`; each row contains the
source hash, config hash, Git commit, software version, evidence code, and pending-review status.

These 291 are **not 291 validated linkers**. Disorder is not linker function; Pfam boundaries are third-party
annotations; coordinates are UniProt positions, not mapped PDB residues; multiple entries may be homologous.
All records are `review_status=pending` and excluded from predictor training and blind evaluation until
domain/linker adjudication, source/coordinate mapping, deduplication, and split auditing are complete.

### Explicit flexible-linker annotations found after the first screen

The same DisProt release also contains 460 regions in 360 proteins explicitly annotated
`flexible linker` (`IDPO:0000033`); 287 are 5–30 residues long. These are stronger
functional annotations than the disorder-overlap screen above, but they are not
automatically two-domain linkers. `scripts/extract_disprot_flexible_linkers.py`
extracts them into a separate versioned, provenance-bearing record type under
`data/processed/disprot_2026_06_flexible_linkers.jsonl`. The JSON contract is
`schemas/disprot-flexible-linker.schema.json`.

An exact/contiguous-sequence screen against the 2,620 deduplicated DLD records
found 17 identical full-sequence matches and 47 additional contained-sequence
matches. The remaining 396 have **not** been certified independent: fragments,
isoforms, remote homologs, and shared regions can evade this simple screen.
`scripts/audit_disprot_dld_overlap.py` writes the match list to
`data/processed/disprot_dld_exact_overlap.json`. Do not use the DisProt source
as a fresh external benchmark or merge its labels into DLD training until a
homology/coordinate audit has been completed.

## SynLinker: dataset not acquired

[Liu, Chin and Lee, Bioinformatics 2015](https://doi.org/10.1093/bioinformatics/btv447) reports a 2,260-linker
collection (natural plus artificial/empirical) and states that supplementary data are at the publisher.
The publisher's [article page](https://academic.oup.com/bioinformatics/article/31/22/3700/241706) advertises
supplementary data, but automated access returned a browser challenge; the published server address timed
out, and an alternate server hostname did not resolve in this check. No original row-level SynLinker file
was obtained, so no SynLinker sequences were imported or presented as verified.

If the supplementary file is obtained, preserve its original bytes, URL, checksum, licence/terms, and
natural-versus-artificial source category. Check overlap with CATH/PDB and DisProt/UniProt before any split.
Treat it initially as a retrieval/baseline or external-comparison resource, not independent validation:
SynLinker's natural subset is also derived from PDB multidomain chains and may duplicate our examples.
