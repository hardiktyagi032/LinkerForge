# Provenance of the linker geometry structure fixtures

Source package: MDAnalysisTests 2.7.0 (PyPI source distribution).
Rebuild with `scripts/build_geometry_test_fixtures.py`.

| Fixture | Source file in package | Source SHA-256 | Trim | Fixture SHA-256 |
| --- | --- | --- | --- | --- |
| `4e43_protease_dimer.pdb` | `4E43.pdb` | `d7b6df5e959d13a7d041072705173f9c52bc2628a923cebe574ac1de679071c5` | chains A and B, protein ATOM records only | `ae36f4c36c967109c7d321972a52d055d0a760cfe6921577a44b7d9b7059e41a` |
| `adk_open_4ake_ca.pdb` | `adk_open.pdb` | `d988a6845a7489f8641ce8918471e4b2a19e94f46490571bb33522041fc48f9a` | C-alpha ATOM records only | `00eac482ccb471069d850a690607dab6c9b7a5a3e4abc0e446eea7a742a5f904` |

`4E43.pdb` is RCSB PDB entry 4E43 as redistributed by the package; its header is
intact in the source file. `adk_open.pdb` is a CHARMM-processed file of adenylate
kinase in the open state, labelled `(4AKE)` in its own REMARK: a derived file, so
only C-alpha positions are kept and only distances are measured from it.
