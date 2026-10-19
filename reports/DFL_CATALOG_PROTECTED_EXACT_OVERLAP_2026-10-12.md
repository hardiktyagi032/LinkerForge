# Exact-sequence overlap audit for the linker catalog

Date: 12 October 2026. Input: `data/processed/linker_catalog/unique_sequences.v1.jsonl`, built under `configs/linker_catalog_2026-10-12.json`.

Of 2,621 unique exact linker sequences, 39 occur in multiple source datasets:
36 in both CAID3 Linkers and DisProt 2026_06, and three in both DLD and
DisProt 2026_06. There are 37 exact sequences in the CAID3 positive-span
catalog; 36 of them are also in DisProt 2026_06. One additional sequence
appears in DLD's protected blind split and DisProt. These **37 exact
protected/nonprotected sequence collisions** are direct leakage hazards for
motif discovery or classifier training.

This is a lower bound: different linker sequences from homologous proteins
can still leak family information. DisProt records remain quarantined. CAID3
and DLD blind records remain protected; the exact-sequence catalog is an index,
not a training list. The next data action is a protein/family-level overlap
filter applied *before* any sequence motif or DFL model training. Also note
that DLD IDL/DDL and DisProt/CAID3 DFL are distinct labels; duplicate strings
do not make the ontologies equivalent.

Reproduce the audit from the JSONL index by counting records with more than
one `sources` value and those having both a `protected_*` usage status and
another usage status. No test labels were used for model selection in this
audit, and no model was trained.
