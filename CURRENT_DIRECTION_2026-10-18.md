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
