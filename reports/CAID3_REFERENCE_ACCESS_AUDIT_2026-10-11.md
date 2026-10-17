# CAID3 linker-reference access audit (11 October 2026)

Status: source-access/preflight audit, updated after retrieving the official
Linker reference. No clean matched-model superiority claim is established.

The official `Linker` FASTA is directly available at
<https://caid.idpcentral.org/assets/sections/challenge/static/references/3/linker.fasta>.
Its local ignored copy `artifacts/caid3-linker.fasta` has SHA-256
`4c204ef49ffa12fe166883e6b2cff0012cabee21260b8f32f997081d0e2fa0f8`.
Parsing gives **31 proteins and 1,379 positive residues**, consistent with
the CAID3 paper. This corrects the earlier access uncertainty below: the
GitHub reference-builder repository itself does not bundle the reference,
but the official static challenge URL does.

| Official source | Pinned local snapshot | Finding |
| --- | --- | --- |
| [CAID reference builder](https://github.com/BioComputingUP/caid-reference) | `c788f1a59c40b1de100092ef06418b12e3d57ca7` in ignored `artifacts/caid-reference/` | Notebooks and supporting data are present. The old/new DisProt Mongo snapshots needed to regenerate the challenge reference are **not** bundled; its README directs users to obtain them from DisProt/developers. |
| [CAID evaluator](https://github.com/BioComputingUP/CAID) | `7bab7e8880d7f949e480fdb377c5a5c8546ae336` in ignored `artifacts/caid-evaluator/` | Official scoring code and a **Disorder-PDB** demonstration reference/predictions are present. No linker reference or linker leaderboard predictions are bundled in `demo-data/`. README says challenge references/results can be downloaded from the [CAID results portal](https://caid.idpcentral.org/challenge/results). |

The evaluator's input contract is a reference FASTA with one sequence and one
per-residue label string per target (`1` positive, `0` negative, `-` excluded),
and predictor `.caid` files with per-residue scores/states. The repository can
be used to test software integration with its demonstration data, **not** to
claim a reproduced linker benchmark score.

Next access gate: retrieve exact competitor predictor-score archives from
the official results portal or challenge maintainers and record their
URLs/licences/checksums. If comparator scores are unavailable, do not
substitute the Disorder-PDB demo or compare against numbers copied from the
paper; document the missing comparator and construct a separately
adjudicated prospective test.

The first contamination audit is already informative: the CAID3 protein IDs
appear in the local DisProt 2026_06 extract **31/31**, contributing 41 of its
460 explicit flexible-linker annotation records. Training on that full
extract and then evaluating on CAID3 would be direct leakage. An initial
top-5 k-mer/local alignment screen of CAID3 against DLD flags three
high-identity targets: DP04066 and DP04255 against DLD training, DP04392
against DLD validation. See `caid3_dld_overlap_2026-10-11.json`; this
screen can miss remote homologs and does not certify the remaining targets.
All CAID3 IDs and homologs must be removed from any new training source
before even a retrospective transfer comparison.
