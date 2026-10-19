# LinkerForge: linker-detection research charter

Status: active research plan, **not** a performance or novelty claim. Updated
11 October 2026. This charter supersedes the earlier fusion-linker-design
objective for new work; it does not rewrite or discard existing records.

## Scientific question and deliverable

Given **only an amino-acid sequence**, can a model return calibrated linker
residue scores and explicit start/end intervals, including an abstention when
there is insufficient evidence, with materially better precision–recall and
interval recovery than current linker-specific predictors on a common,
leakage-audited benchmark?

The **primary target** is DisProt-style disordered flexible linker (DFL)
annotation, the task evaluated by CAID. A secondary, explicitly separate
target is DLD's structural independent/dependent domain linkers (IDL/DDL).
Do not pool the labels or call one benchmark a test of the other. A DLD-trained
model is not automatically a DFL predictor. Neither predicts that an
unannotated residue is certainly a true negative.

For each sequence, output: per-residue score, 1-based inclusive start/end
coordinates, linker amino-acid subsequence, model/version, confidence or
abstention, and provenance. A predicted interval is not experimental proof.

## Verified competitive landscape

| Source | Target/approach | Benchmark implication |
| --- | --- | --- |
| [DFLpred](https://doi.org/10.1093/bioinformatics/btw280) | Disordered flexible linkers; logistic-regression-style local predictor | Historical minimum comparator, not state of the art. |
| [APOD](https://pmc.ncbi.nlm.nih.gov/articles/PMC7773485/) | DFL; SVM with local and protein-level features | Its paper reports an independent low-similarity test; reproduce on common data rather than transplanting its numbers. |
| [TransDFL](https://doi.org/10.1016/j.gpb.2022.10.004) | DFL transfer from disorder-related supervision | Transfer learning alone is not novel. |
| [DisoFLAG](https://pmc.ncbi.nlm.nih.gov/articles/PMC10762911/) | pLM-based disorder-function/linker prediction | A protein-language-model linker head is not novel. |
| [LINKER-Pred2](https://pcrgwd.ucd.ie/linker_pred/help/) | DFL; ProtTrans/MSA-based deep model trained with DLD and DisProt sources | CNN plus protein embeddings and mixed-source training already exist. |
| [IDPFunNet](https://doi.org/10.1093/bib/bbag126) | 2026 dual-path ProtT5/CNN/BiLSTM model with dedicated DFL path | BiLSTM, ProtT5, and multitask specialization alone are not new contributions. Open standalone implementation is a required comparator if licensing permits. |
| [DLD source study](https://www.sciencedirect.com/science/article/pii/S0022283626003670) | Structural linker/loop/domain dataset assembly and pLM-CNN classification | Automated PDB linker extraction plus pLM/CNN is not an original claim. DLD labels differ from CAID DFL labels. |
| [CAID2 linker assessment](https://pmc.ncbi.nlm.nih.gov/articles/PMC10968229/) | Independent DFL challenge analysis | Establishes earlier comparator behavior and label limitations. |
| [CAID3 assessment](https://pmc.ncbi.nlm.nih.gov/articles/PMC12750029/) | Blind DFL evaluation across submitted methods | Primary published common benchmark; reproduce evaluator and coverage accounting. |

CAID3's linker reference contains **31 linker-positive proteins and 1,379
positive residues (6.7%)**. Its Table 5 reports IPA-AF2-Linker AUC 0.897,
average precision (APS) 0.474 at 90.3% coverage; LINKER-Pred2 AUC 0.875,
APS 0.365 at full coverage. These are **published CAID3 results**, not
LinkerForge scores, and should never be compared numerically with DLD fold-4
metrics. CAID3's reference contains only proteins with a DFL annotation, so
it cannot alone measure rejection of no-linker proteins. Its reference is the
December 2023 public to June 2025 private DisProt delta; DisProt 2026 data
may overlap and is not automatically a fresh external test.

Reproducibility sources: [CAID reference builder](https://github.com/BioComputingUP/caid-reference),
[CAID evaluator](https://github.com/BioComputingUP/CAID), and
[complete CAID results](https://caid.idpcentral.org/challenge/results).
Before choosing a leaderboard number, record predictor coverage, available
scores, input modalities, version, and common-target subset. In CAID3, the
official metrics are AUC, APS, and Fmax; these are not interchangeable with
our high-precision recall or interval score.

Related but **not same-task** comparators include protein domain-boundary
methods [DeepDom](https://pmc.ncbi.nlm.nih.gov/articles/PMC6417825/),
[Merizo](https://www.nature.com/articles/s41467-023-43934-4),
[Chainsaw](https://pmc.ncbi.nlm.nih.gov/articles/PMC11256964/), and
[DPAM-AI](https://pmc.ncbi.nlm.nih.gov/articles/PMC11723527/). Their domain
maps can be predeclared auxiliary features in a separate input track, but
their domain accuracy is not linker-detection leaderboard performance.

## Benchmark contract before any frontier claim

1. Freeze the ontology: DFL primary, DLD IDL/DDL secondary. Verify DLD raw
   codes, especially code `0`, against official source definitions. Preserve
   source labels; unknown does not silently become negative.
2. Establish three explicitly named sets: training, calibration/development,
   and **untouched** test. Cluster entire proteins/families across all source
   datasets and prior model training sources. DLD fold 5 was viewed and is
   not fresh blind. Audit CAID3 membership against every candidate training
   source before calling it independent; if contaminated, use it only as a
   public benchmark and obtain a new prospective, adjudicated test.
3. Add adjudicated no-linker proteins and nonlinker disordered regions. Do not
   claim no-linker specificity from CAID3 linker-positive sequences.
4. Run DFLpred, APOD, LINKER-Pred2, IDPFunNet, CAID3 leaders with obtainable
   implementations/predictions, and simple ESM-2/ProtT5 residue heads on the
   **same target sequences**. Distinguish exact released models from faithful
   reimplementations; no apples-to-oranges published-number comparison.
5. Publish full-coverage and common-coverage results separately. Primary
   CAID-compatible measures: APS, AUC, Fmax with the official evaluator.
   Proposed extra endpoint: residue recall at calibrated precision >=0.90,
   exact ties and raw counts. Report region precision/recall at IoU >=0.5,
   start/end error, protein-level false-positive rate, abstention coverage,
   per-family confidence intervals, inference cost, and failed predictions.
6. Preregister a **material** win criterion before model selection. The
   provisional target is at least **+0.05 absolute APS** over the strongest
   same-input baseline on an untouched, common-target test, with a paired
   protein/family-cluster 95% confidence interval for the difference excluding
   zero; also require either **+10 percentage points** in IoU-0.5 region
   recall at matched region precision or **+10 percentage points** in residue
   recall at a calibrated >=0.90 precision operating point. No-linker-protein
   specificity may fall by no more than 0.02 absolute. Report all three
   seeds, coverage, raw counts, uncertainty, and negative results. These are
   demanding design targets, not power calculations or promises; if the test
   is too small, state that the criterion is inconclusive.

## Ranked experiment program

Each experiment keeps data, encoder, splits, selection metric, and compute
matched to its ablation. One local 6 GB GPU job at a time; college cloud can
parallelize only after environment and data contracts are pinned. Every run
has an isolated directory, seed, hashes, logs, runtime, memory, and failure
status. A frozen reference model is always rerun on the same task labels.

1. **Span-aware prediction (first hypothesis).** Adapt
   [segmental recurrent networks](https://arxiv.org/abs/1511.06018) or a
   bounded semi-Markov interval scorer to frozen per-residue protein-language
   embeddings. Score complete candidate segments and boundaries, not only
   independent residues. Ablate against the identical residue head and its
   predeclared minimum-span decoder. Failure modes: noisy boundaries,
   quadratic interval costs, and no gain at high precision. A sequence-span
   mechanism is a hypothesis, not itself an original ML invention.
2. **Protein boundary context.** Test a separate boundary head and/or
   precomputed, independent domain-boundary signal, motivated by
   [zero-shot pLM segmentation](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1012929).
   Compare sequence-only and domain-feature tracks explicitly; no target or
   native structural annotation may leak into inputs.
3. **Partial-label learning, only after an annotation audit.** Preserve
   verified negatives and mask genuinely unknown residues; compare a
   non-negative positive–unlabeled objective from
   [Kiryo et al.](https://papers.nips.cc/paper/2017/file/7cce53cf90577442771720a370c3c723-Paper.pdf)
   with matched BCE. The selected-at-random assumption may fail badly for
   curated linkers, so this cannot be used until source semantics and class
   prior are defensible.

Do not combine mechanisms until each improves the same development contract
independently, then repeat across seeds and evaluate once on an untouched
test. A larger backbone without a mechanism and a label-cleaning claim based
only on model disagreement are lower-priority controls, not breakthrough
strategies.

## Current evidence and next gate

Current local DLD fold-4 results are development-only: weighted-BCE recovers
475/6,205 linker residues at 90.13% precision (7.66% recall); asymmetric
head 525/6,205 (8.46%); a development-informed minimum-span decoder gives
540/6,205 (8.70%). BiLSTM and dilated-head trials did not improve the frozen
high-precision objective. The 2026 DisProt review queue contains four
annotation records but only three unique domain gaps, none adjudicated as
independent. See the detector ledgers in `reports/`. No publishable superior
model exists yet.

**Immediate gate:** reconstruct a contamination-audited CAID-compatible DFL
task and acquire matched baseline predictions/implementations; then specify
and launch the span experiment. Do not treat DLD fold-4 search as evidence of
CAID superiority. If a fresh, sufficiently powered adjudicated test cannot
be obtained, the honest paper scope is methods/benchmark analysis rather
than a claim to beat all existing detectors.
