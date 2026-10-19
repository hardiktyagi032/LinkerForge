# LinkerForge structure-ensemble evaluation

Status: proposed evaluation contract, 8 October 2026. A C-alpha-only diagnostic
scorer and CLI now exist, but no folding or molecular-dynamics runs described
here have yet been executed. This extends the README's
Rosetta -> folding -> hard-rejection -> OpenMM funnel; it does not replace the
natural-linker detector or the A--linker--B ranking baselines.

## Question

For an identical complete single-chain sequence `Domain A--candidate--Domain
B`, do structurally different predictors agree that the linker closes the
chain, preserves both domains, and leaves protected surfaces unobstructed?
Agreement increases computational confidence; it does not prove fusion
function, expression, or a particular flexible-linker conformation.

## Three-model panel

1. **AlphaFold2 via ColabFold:** primary complete-fusion predictor; pin exact
   model weights, ColabFold version, MSA database, templates, recycles, seeds,
   and output confidence files. ColabFold is an AF2 pipeline, **not** a second
   independent folding architecture.
2. **ESMFold:** distinct language-model-based prediction method. Pin model
   weights/version and sequence-length settings. Record failures; do not drop
   difficult sequences from the denominator.
3. **OpenFold:** open, separately trained AF2-style implementation. This is a
   reproducibility/sensitivity track, **not independent evidence equivalent to
   a different architecture**. If deployment or resource constraints make it
   infeasible, predeclare a third validated open model in the run manifest and
   justify the substitution before seeing outcomes.

These are structural evaluation instruments, not baseline *linker-design*
algorithms. The no-linker, fixed `(GGGGS)3`, random GS-rich, geometry-only,
retrieval, and feature-ranker baselines remain required. Fold the same
predeclared shortlist from each design method with the same model panel,
sampling budget, and scoring rules. Never compare a LinkerForge candidate
folded by three models against a control folded by one.

## Common input and prediction protocol

1. Freeze domain sequences, orientation, permitted attachment points, candidate
   linker sequences and the scoring thresholds. Build a full-length FASTA for
   each candidate, including controls. Hash each FASTA and record exact domain
   and linker residue intervals.
2. Run all three predictors on the same FASTA. Do not provide a fusion template
   to one method alone. If domain templates are used, declare a separate
   template-assisted stratum for every compatible method. Use predeclared
   multiple seeds/models per method when supported; this estimates within-model
   variability without falsely treating correlated outputs as independent.
3. Align **each domain separately** to its fixed experimental reference or
   predeclared input structure. Keep linker coordinates and interdomain pose
   unaligned for distance/orientation measurements. Log missing atoms,
   residue mapping, chain breaks and confidence-field availability.
4. Apply an identical scorer to every valid model output: bond continuity,
   nonlocal severe clashes, per-domain RMSD/TM-like preservation, protected-site
   clearance, terminal geometry, linker exposure, and interdomain orientation.
   Keep domain/linker confidence and PAE-like uncertainty in separate fields;
   do not compare raw confidence values across architectures as calibrated
   probabilities. Low linker confidence alone is not a failure for a flexible
   linker.
5. Report per-method values and the median/range of each *comparable physical
   metric*, plus model-disagreement and method-specific failure counts. Never
   average atomic coordinates or collapse the panel into an unqualified score.
   Predeclare whether the decision rule requires all models to pass or a
   majority to pass; show both sensitivity analyses. A method missing required
   outputs is `not_evaluable`, not a pass.
6. On held-out natural proteins, compare predicted complete structures with
   experimental structures only where the reference coordinates exist and are
   reliable. Report potential predictor training/template overlap. For
   unresolved natural linkers, assess domain preservation and geometry, not
   exact linker-coordinate recovery.

## Water and motion: separate MD stage

PyMOL is for inspection, measurements, figures, and viewing trajectories. It
does not supply a validated explicit-water molecular-dynamics force field.
For 1--3 finalists **and matched controls**, take a predeclared representative
predicted structure, repair missing chemistry, add hydrogens and explicit
water/ions with OpenMM, minimise, equilibrate, and run replicated short MD if
compute permits. Fix force field, water model, temperature, ionic strength,
box padding, restraints, timestep, seeds and run length in the manifest.
Analyse trajectories with MDAnalysis or OpenMM tools; view them in PyMOL.

Compare linker/end-to-end distance distributions, domain RMSD, interdomain
angle, protected-site accessibility, clash/contact persistence, and whether the
linker remains connected. Report trajectories and uncertainty across replicate
seeds. Short MD probes local stability only; it neither estimates real-world
fusion success nor samples the full conformational ensemble. If there is not
enough compute for matched, replicated MD, perform minimisation only and label
it as such. Do not cherry-pick the best-looking frame.

## Provenance and publication table

For every candidate x predictor x seed, record FASTA hash, predictor/code and
weight versions, MSA/template inputs, seed, structure artifact hash, confidence
artifact hash, scorer commit/config hash, status, all metrics, and rejection
reasons. For MD additionally record starting-structure hash, force-field/water
files, conditions, seed, trajectory hash, frame interval and analysis version.
The paper's table uses identical rows/columns for LinkerForge and every design
baseline, with `not_run` and `failed` explicitly distinguished from zero.

The implemented `scripts/score_fusion_pdb.py` reads a pre-existing, already
mapped PDB and records sequence-port junction distances, C-alpha gaps and
severe overlaps, plus optional domain internal-distance RMSD against mapped
references. It is not an all-atom score, not a predictor, and does not apply
pass/fail thresholds. Inputs must use full-fusion residue numbering without
insertion codes; mmCIF and complex mappings remain to be implemented.

## Primary sources

- [AlphaFold2 implementation](https://github.com/google-deepmind/alphafold)
  and [ColabFold paper](https://doi.org/10.1038/s41592-022-01488-1).
- [ESMFold paper](https://doi.org/10.1126/science.ade2574) and
  [official model repository](https://github.com/facebookresearch/esm).
- [OpenFold paper](https://doi.org/10.1038/s41592-024-02272-z) and
  [official implementation](https://github.com/aqlaboratory/openfold).
- [OpenMM user guide](https://docs.openmm.org/latest/userguide/application.html)
  for explicit solvent and simulation; [PyMOL](https://www.pymol.com/) for
  molecular visualization.
