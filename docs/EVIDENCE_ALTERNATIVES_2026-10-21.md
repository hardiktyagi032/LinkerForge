# Evidence alternatives and future integrations

This addendum covers the fusion application and its external-method audit.
It changes neither the active DFL training contract nor the protected-data
firewall. An available alternative answers a specific question; it does not
turn an unmeasured outcome into a positive result. Wet-lab execution remains
outside this project's requested scope.

| Evidence question | Practical method | Implementation and remaining scope |
| --- | --- | --- |
| Does a linker bury a domain residue in the predicted pose? | Differential solvent-accessible surface area (SASA) with Biopython Shrake–Rupley | Implemented CPU analysis, sequence and coordinate hash checks, per-residue outputs and evidence-record linking. Requires researcher-supplied functional annotations to interpret protected sites. |
| Is an annotated residue near the linker? | Existing heavy-atom distance/SASA report plus the app's Cα screen | Implemented. Ligands, binding partners and conformational ensembles remain future context. |
| Does the structure contain unrealistic atomic contacts? | MolProbity Reduce/Probe and geometry analysis | Suitable complementary alternative. CLI tools were not found on Windows or WSL PATH during this audit. Installation, pinning and execution remain future implementation; no MolProbity score is claimed. |
| Can strained coordinates relax? | Existing OpenMM minimization | Available and executed as part of the prior smoke protocol. Energy decrease does not establish biological stability or replace Rosetta loop reconstruction. |
| Can a missing linker conformation be reconstructed? | Rosetta KIC or another separately validated loop-sampling method | Future integration. Surface area, clash checks and minimization do not replace this test. |
| Are results reproducible across public constructs? | Matched ColabFold controls across three public pairs | Existing single-pair panel complete; additional two-pair durable prediction job is separate and ongoing. This panel is descriptive, not a family-disjoint prospective evaluation. |
| Does an external detector recognize inserted linkers? | Published DFLpred implementation on the existing 28-construct public panel | Executed comparator. It assesses flexible-linker propensity. LINKER-Pred, TransDFL and DisoFLAG remain future pinned comparisons. |
| Are structural conclusions robust across architectures? | ESMFold; another validated independent model family; OpenFold for AlphaFold-family reproducibility | Future integration with the same sequences and analysis rules. Five AF2 parameter models are not five independent model families. |
| Is the compatibility ranker scientifically calibrated? | Independently evidenced engineered-fusion outcomes and an untouched grouped evaluation | No computational substitution establishes this. Future scientific development. The mined corpus remains useful for discovery/retrieval and reviewed weak supervision. |
| Are MD trajectories long enough to support stability claims? | Replicated production simulations with convergence checks | Future execution. The existing 3 × 50 ps run verifies software execution only. |
| Can the app run without institutional cloud access? | Existing local Tauri/WSL execution and durable run manifests | Implemented for bounded public inputs. Approved institutional/cloud execution remains future deployment. |
| Can research results be preserved without a signing service? | Existing checksummed research ZIP and SHA-256 history | Implemented integrity alternative. Publisher signing and institutional signatures remain future release/deployment work. |

## Surface-burial calculation

`scripts/assess_fusion_surface_burial.py` reads a completed structure-comparison
record and the public sequence manifest. Each input must match both its recorded
PDB hash, complete sequence, and domain/linker boundaries. It rejects ambiguous chains, models,
alternate locations, missing backbone atoms and unsupported residues/elements.
It records source identifiers, configuration, executable, arguments, code hash,
commit and software versions in `linkerforge.fusion-surface-burial.v1` JSON.

For every domain residue it calculates:

1. SASA in the full fusion.
2. SASA after removing linker atoms while retaining both domains in place.
3. SASA in its isolated domain at those same coordinates.

`SASA_without_linker − SASA_full` estimates surface additionally buried by the
linker in that pose. `SASA_isolated_domain − SASA_full` measures burial by the
linker and the other domain together. Both calculations use the same 1.4 Å
probe, heavy-atom radii, and 960 surface points per atom. They do not simulate
the physically separated domain, restore a natural terminus, or relax it.

All domain residues are retained. No residue is called functional or protected
without an annotation. No acceptance cutoff or winner is inferred from the
measurements. High PAE and low local confidence must remain visible when
interpreting burial. Missing sidechains, excluded ligands/partners and alternate
poses are limitations. Domain totals sum lost per-residue surface; they are not
the half-sum convention sometimes used for interface area.

The research command and detached dependency chain are available in
`configs/detached-surface-evidence-20261021.json`. They use the seven completed
1UBQ–2GB1 structures and leave the running GPU prediction job untouched.
The analysis is currently a research CLI/report workflow; automatic per-design
UI execution/import is future interface integration.

Output directory: `runs/structure-audits/surface-burial-20261021/`.
The durable job's `status.json` is authoritative for completion. Existing run
directories and evidence records are never overwritten.

## Sources checked

- [Biopython SASA API](https://biopython.org/docs/latest/api/Bio.PDB.SASA.html):
  Shrake–Rupley implementation, probe radius and sphere-resolution controls.
- [MolProbity CLI documentation](https://github.com/rlabduke/MolProbity/blob/master/doc/command_line_tools.txt):
  hydrogen addition/Probe clash analysis and geometry tools.
- [MolProbity methods paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC1933162/):
  why explicit hydrogens are important for all-atom contact validation.
- [OpenMM user guide](https://docs.openmm.org/latest/userguide/): minimization
  and simulation execution; interpret results according to the executed protocol.

The external-method rows in the main audit retain their measured status.
Unavailable methods belong to future scope. Invalid sequence matches, malformed
outputs and measured geometry failures remain actual failed checks.
