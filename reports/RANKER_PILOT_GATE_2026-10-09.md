# Linker-ranker data gate: 2026-10-09

This is a read-only audit of `data/processed/cath_full_pilot.jsonl`, not a trained-model result or training-set approval. Reproduce with `node scripts/audit_ranker_pilot.mjs` from the repository root.

- Input SHA-256: `20deca0e0bff4d1c68b245cc4e15756fc4e6462537c67a7d4508b5f8f58cfd85`.
- Records: 91. All 91 are `uncertain` and `manual_review_status=pending`.
- Both attachment residues are marked resolved in all 91. Cached PDB SHA-256 matches all 91 records, and both port residue identities match the cached coordinates in all 91.
- No record has a fully resolved linker interior. The sequence is obtained from the mmCIF polymer scheme; missing interior coordinates do not by themselves disprove a flexible linker, but they prevent direct coordinate-based ground-truth claims.
- There are 57 unique **CATH architecture proxies**, not 57 independently verified homology clusters. This field must not be used as the sole basis for a claimed homology-disjoint blind split.
- The local RTX 3050 reports no GPU process. This is only a snapshot, not proof of cloud availability.

## Decision

The attachment-port mapping gate passes at the residue-identity/hash level. The scientific-label gate fails: domain-gap segments have not been adjudicated as true linkers, unresolved interiors cannot be structurally inspected directly, and homology clusters are proxies. Do not run publication-directed GNN training or report natural-linker recovery from this pilot as a scientific result.

## Next validation work

1. Review a small, architecture-diverse set of chains in CATH/UniProt/PDB context. Confirm that each gap is a same-chain interdomain linker rather than missing annotation, cleavage, engineered junction, or another domain segment. Record reviewer, evidence, reason codes, and citation/source IDs.
2. Build domain-local Cα graphs only for reviewed records; audit sequence-to-coordinate mapping and graph extraction. Do not use native interdomain geometry in the deployment-compatible track.
3. Replace architecture proxies with frozen sequence/homology clusters; deduplicate multiple PDB chains/structures representing the same protein before splitting.
4. Freeze a candidate pool and implement identical baseline/ranker evaluation on a development-only split. Keep blind reference sequences sealed during model selection.
5. Pin and verify Python/PyTorch on the college-cloud image. The current local Python launcher is broken/missing; no predictor test or training run is claimed from this audit.
