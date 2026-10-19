# LinkerForge agent handoff

Read `README.md` completely before changing this repository. It is the canonical scientific and MVP specification.

On `codex/attachment-site-scorer`, the human's next direct instruction authorizes
component 4 implementation without data. Read `ATTACHMENT_SITE_MODEL.md`.
Keep insertion and terminal-extension endpoints separate; unknown annotations
are not negatives and unvalidated linker flanks are not tolerance supervision.
Use the existing geometry engine for explicit connection plans; do not infer
optimal tether count or function from a site score. Synthetic checks are software
verification only; preserve detector protections and require review before fitting.

On `codex/fusion-linker-generator`, the human's 18 October 2026 instruction
authorizes component 5 implementation from `ARCHITECTURE_HANDOFF.md`.
Read `FUSION_GENERATOR.md` for this checkout's code and limits. Build and test
the generator without biological training while data is absent; preserve the
detector firewall, all other checkouts and unreviewed shared contracts.
Do not interpret the historical detector-only scope below as cancelling that
direct instruction. No team review, cloud readiness or trained performance is
implied by this implementation.

For the **active DFL detector** research, then read `RESEARCH_HANDOFF.md` and
`literature/DFL_UNTOUCHED_COMPARISON_CONTRACT_2026-10-17.md`. The fusion-ranker
decisions below are historical/future scope, not the active detector training
objective. The current protected DFL split fails the prospective benchmark
firewall; never bypass preflight or use public CAID3 scores to select a model.

## Current state

- The React/Vite frontend exists and uses labelled demonstration data.
- CI and GitHub Pages deployment exist.
- The scientific Python pipeline, dataset, trained ranker, and cloud jobs are specified but not implemented.
- Do not imply that proposed architecture or example scores are completed results.

## Frozen decisions

- Demonstration: `sfGFP — linker — mCherry`.
- Linker: flexible, non-cleavable, GS-rich, 5–30 residues.
- Fixed control: `(GGGGS)3 = GGGGSGGGGSGGGGS`.
- Data: natural two-domain proteins for pretraining; engineered fusions for stronger evidence where available.
- Learning task: pairwise/contrastive compatibility ranking, not experimental-success classification.
- Model: frozen ESM-2 embeddings + attachment-point geometric GNN + small linker encoder + multitask heads.
- Generation: constrained enumeration/mutation/retrieval for MVP; learned generation and diffusion are future work.
- Blind test: homology-aware held-out proteins with masked natural linkers; save predictions before revealing references.
- Structural funnel: Rosetta → AlphaFold/ColabFold → hard rejection → OpenMM; optional GROMACS for 1–3 finalists.
- PyMOL is for inspection, measurements, and figures, not the simulation engine.
- Result claim: highest-ranked computational candidate, never experimental proof.

## Development rules

- Preserve user work and unrelated files.
- Use the versioned JSON contracts in README Section 7; add formal JSON Schema before producing scientific records.
- Every derived record needs source IDs, commit SHA, config hash, versions, and evidence quality.
- Label natural observations, synthetic negatives, predictions, and experimental outcomes distinctly.
- Split by homology/domain-family clusters before model development; never tune on blind examples.
- Baselines and LinkerForge must use the same scoring and rejection rules.
- Keep long scientific jobs on the college cloud, not web hosting or ordinary CI.
- Frontend example values must remain visibly labelled until replaced by provenance-bearing outputs.

## Branch contract

- `main`: reviewed release.
- `integration`: combined testing.
- `work/build-port-records`: data and connection records.
- `work/train-linker-ranker`: baselines and ML.
- `work/predict-and-score-fusions`: structural modelling and scoring.
- `work/build-results-interface`: UI and provenance presentation.

Run frontend verification before handing off UI changes:

```bash
cd frontend
npm ci
npm run lint
npm run test
npm run build
```

If no backend environment is committed, do not invent a working installation claim. Pin and test it on the target cloud image first.
