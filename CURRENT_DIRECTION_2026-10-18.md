# LinkerForge direction — 18 October 2026

Work resumed on explicit user instruction. PRs #1–#7 were merged into
`codex/dfl-research-handoff` on 18 October 2026. Their former draft and pause
statements in dated handoffs describe their writing time, not the current
project state. The earlier three detector-research heartbeat IDs were absent
from the app when asked to pause them; no replacement schedules were created.

## Build order

1. **Classifier first.** Build a sequence-based DFL residue caller with
   positive/negative/unknown semantics, family-disjoint training and
   development, a benchmark-sequence firewall, calibrated abstention and an
   independently adjudicated no-linker set. Report precision at actual mining
   coverage, not APS alone. The old protected split fails the prospective
   firewall; CAID3 is a spent retrospective. No new training or mining on the
   strength of the merged PR #1 toolkit alone.
2. **Mine only after validation.** Stream candidate natural proteins, retaining
   source accession, sequence/spans, model and threshold hashes, annotation
   tier and excluded-family audit. Model calls are predictions, not curated
   facts or functional-assay outcomes.
3. **Design using geometry and templates.** PR #3 supplies required-length and
   multi-tether geometry; PR #2 supplies cited templates and property callers.
   Geometry is necessary feasibility, not fusion success. Start with tandem
   end-to-end attachment while retaining internal insertion as an explicit
   separate topology decision.
4. **Run a retrieval baseline.** On a genuinely held-out domain-pair/family
   split, retrieve candidate linkers from training records using flanking
   context only. Compare against fixed (GGGGS)3, length-matched template,
   nearest-neighbour, and geometry-only controls under one scoring protocol.
   Do not build or claim a generative advantage until the retrieval test is
   complete; the current library alone lacks the labelled flanking-domain
   records needed for that comparison.

## First implemented step

`scripts/predict_dfl_frozen.py` is a verified-checkpoint inference adapter.
It runs on one sequence, returns raw per-residue scores and abstains from span
calls by default. Explicit threshold calls are provisional. It does **not**
unlock large-scale mining, a new benchmark result, or a superiority claim.
See `CLASSIFIER_INFERENCE.md` for the command and validation boundaries.

The next blocker to resolve is a versioned DFL training/calibration source
with 1/0/x semantics and a family-disjoint split that passes all nominated
benchmark registries. The classifier and design workflows remain distinct
scientific tasks; DLD structural linker labels are not substituted for DFL.

The first-stage classifier handoff and its tracked, synthetic-tested data gate
are in `CLASSIFIER_DATA_GATE.md`. This does not check off B1: the real split,
source semantics and family evidence are still missing.

## Software status and scientific gates (19 October 2026)

1. **Classifier and mining:** The three-layer CNN, preflights, domain gate and mining scripts exist. The historical B1 V2 training split and the reported 27,766-row mixed candidate/template/annotation output are now downloadable from [`datasets/`](datasets/README.md) and byte-verified against their original manifests. Publication resolves the clean-clone data-availability gap, **not** the biological validation gap: the calibration unit, independent no-linker panel and claimed high-precision mining rate remain unverified. Do not use the mined calls as biological ground truth or as new classifier training positives. See `reports/PAPER_CLAIMS_AUDIT_2026-10-19.md` and `CLASSIFIER_DATA_GATE.md`.
2. **Geometry, templates and retrieval:** Code and internal evaluations exist, but the X2 retrieval result was computed on the mixed candidate pool, not a qualified held-out family benchmark. It does not establish that generated linkers work better than a fixed control. See `reports/PART2_GEOMETRY_TEMPLATE_DESIGN_AND_X2_RETRIEVAL_2026-10-19.md`.
3. **Attachment sites:** Two scorer implementations and geometry reranking have software tests. A reported near-perfect site score reflects a constructed terminal-versus-interior task with a positional feature; it is not independent port-adjudication performance. See `reports/PAPER_CLAIMS_AUDIT_2026-10-19.md`.
4. **Compatibility ranking and visualization:** The ranker discriminated natural/candidate records from six generated corruption types and internal heuristics. It has no matched published-method or experimental-fusion benchmark. Exported sfGFP–mCherry coordinates are geometric illustrations, not validated full-fusion structures. See `reports/PART4_END_TO_END_RANKER_AND_SFGFP_MCHERRY_DEMO_2026-10-19.md` and the claims audit.
5. **Interfaces:** The browser constructs labelled template fusions and loads sequence-matched predicted PDB files; a Python API script exists separately. The optional desktop shell can launch a separately installed ColabFold process, but neither ColabFold nor a verified 6 GB fold is bundled. See `docs/FULL_FUSION_LOCAL_WORKFLOW.md` and `docs/DESKTOP_LOCAL_FOLDING.md`.
