# Provisional DFL candidate component gate

`scripts/audit_dfl_candidate_strong_components.py` deterministically grouped the 205 positive candidates in the completed local-similarity screen using only its pre-existing **strong review flags** (at least 30% local identity, 80 aligned residues, and 70% shorter-sequence coverage proxy). It used CAID3 protein sequences as protected anchors, never CAID3 linker labels. Input and script hashes, all components, and protected anchors are in `reports/dfl_candidate_strong_components_2026-10-17.json`.

The 78 strong edges form 182 candidate components. **52 of 205 candidates** lie in components with at least one protected TR166, TE82, TE64, or CAID3 sequence anchor. These 52 must be quarantined from any putatively independent candidate split pending family-level review. The other 153 are **not certified independent**: this local threshold can miss remote homology, shared domains, and low-complexity relationships. The 182 components are provisional connected sets, not a frozen train/development/test assignment.

No model training or test-label-informed selection follows from this result. Next gate: protein/domain-family clustering with reviewed edge evidence, label-coordinate reconciliation, and an untouched adjudicated evaluation set with verified no-linker negatives.
