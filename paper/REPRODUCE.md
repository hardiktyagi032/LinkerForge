# Reproducing the preliminary LinkerForge pilot

This is an unreviewed data-mining and diagnostic-ranking pilot, not a validated
fusion-design result. Its two figures are generated from the CATH/RCSB extraction
counts and a reference-injected linker-ranking benchmark, respectively.

## Sources

- CATH v4.4 public download: <https://download.cathdb.info/cath/releases/latest-release/cath-classification-data/>.
  Pin the `v4_4_0` release for a future archival rerun rather than relying on
  `latest-release`. The files used here are `cath-domain-boundaries.txt` and
  `cath-domain-list.txt`.
- RCSB files are retrieved by PDB ID from
  `https://files.rcsb.org/download/<PDB_ID>.pdb` and `.cif`. Raw bytes are
  cached and SHA-256 hashed in the derived records.
- The separate DLD dataset is described at <https://pcrgwd.ucd.ie/linker/>.
  It was identified as an important external comparator but was **not** used
  to train or evaluate this pilot.
- The million-scale yield probe uses the pinned InterPro 110.0 directory at
  <https://ftp.ebi.ac.uk/pub/databases/interpro/releases/110.0/>. This is a
  separate unlabeled source and was not used in the pilot ranking metrics.

## Commands

Run at the repository root with Python and `PYTHONPATH=src` configured:

```text
python scripts/select_cath_pilot.py --boundaries data/raw/cath/cath-domain-boundaries.txt --domain-list data/raw/cath/cath-domain-list.txt --output data/processed/cath_full_candidates.csv
python scripts/build_rcsb_pilot.py --candidates data/processed/cath_full_candidates.csv --cache data/raw/rcsb --output data/processed/cath_full_pilot.jsonl --max-requests 120
python scripts/train_pilot_baseline.py --records data/processed/cath_full_pilot.jsonl --output data/processed/cath_full_baseline.json --seed 7
python -m unittest discover -s tests -q
```

The inputs and outputs under `data/` are intentionally ignored by Git. Retain
the generated JSONL, manifest, baseline JSON, raw-file checksums, and the Git
commit together when archiving an actual experiment. The current pilot was
run on a working tree; `pipeline_commit` is the last commit, while uncommitted
source edits are not captured by it. For strict reproducibility, commit the
pipeline before a paper-level rerun.

## What these numbers do not establish

The gap between CATH domains is only a candidate linker. This pilot has not
independently reviewed engineered constructs, unresolved segments, or linker
secondary structure. The `homology_cluster_id` field currently contains an
ordered CATH-family-pair proxy; it is **not** an MMseqs2 or equivalent
sequence-homology cluster. The blind reference is injected into the evaluation
candidate pool, so MRR is conditional ranking, not production recovery. The
production pool's exact-reference coverage is reported separately. Native
linker recovery is not a measurement of expression, stability, or activity.
