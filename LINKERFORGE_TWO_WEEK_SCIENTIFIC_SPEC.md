# LinkerForge scientific MVP: two-domain peptide-linker recommendation

Status: proposed implementation specification, 8 October 2026. Nothing in
this document is a completed scientific result. The repository README remains
the canonical long-range specification; this file narrows execution to a
two-week computational study with four contributors.

## 1. Question and claim boundary

**Input:** two soluble protein-domain sequences with experimental PDB/mmCIF
structures, a specified connection topology (Domain A C-terminus to Domain B
N-terminus), and optional protected residues. Domains may be homologous or
unrelated. A "complex" means associated chains and is not assumed here.

**Output:** a ranked list of 5–30-residue peptide linkers, complete fusion
FASTA sequences, reason codes, provenance, and optional structural scorecards.
The prototype may abstain if inputs violate the contract.

**Primary falsifiable research hypothesis:** a small context-aware ranker using
frozen protein-language-model features and local attachment-site geometry ranks
the observed linker in homology-held-out natural two-domain proteins better
than context-free natural-linker retrieval and hand-feature ranking, under the
same candidate sets and evaluation rules. This is a hypothesis, not a claimed
gap or result. An improvement is not guaranteed.

**Scientific limits:** natural observations establish existence in a native
context, not optimality. Native-linker reconstruction is a proxy for natural
compatibility, not an assay of engineered fusion function. An unrelated pair
assembled from two separate proteins has no known positive linker unless an
independent engineered-fusion dataset supplies one. Therefore unrelated-pair
examples are demonstrations and structural plausibility checks, not ground
truth success tests. Do not claim universal success or biological optimality.

## 2. Component boundaries

Every scientific output uses a versioned JSON Schema derived from README
Section 7 before bulk processing. Each record carries source IDs, source
type, evidence quality, retrieval date, code commit, config hash, tool versions,
and input/output checksums. Raw inputs are immutable. No mock scores enter
scientific records.

| ID | Module | Input | Output | Acceptance test |
|---|---|---|---|---|
| M0 | Contracts and runner | Config and manifest | Versioned schemas, deterministic run IDs, logs | Invalid or incomplete records fail schema; rerun with same seed reproduces IDs and splits. |
| M1 | Source ingestion | RCSB IDs, mmCIF, CATH/InterPro annotations | Chain-to-sequence mapping and source records | 10 manually chosen structures map author/label residue numbers to canonical sequence without off-by-one error. |
| M2 | Domain/linker adjudication | M1 records | Accepted natural `A-linker-B` examples and rejected/uncertain log | Two domain annotations on one continuous chain, ordered nonoverlapping, gap of 5–30 residues, residues resolved or flagged; manual audit of at least 30 examples with boundary disagreements recorded. |
| M3 | Leakage control | M2 examples | Deduplicated cluster and split manifests | Same UniProt, high sequence identity, homologous domain families, and same architecture do not cross train/validation/test; blind manifest hashed before model tuning. |
| M4 | Candidate pool | Training examples plus query ports | Identical per-query candidate lists for all methods | Includes hidden native (evaluation only), length-matched transplanted natural linkers, GS controls, and constrained variants; generator never retrieves from validation/test. |
| M5 | Baselines | M3/M4 | Scores per candidate | Fixed GS, length heuristic, nearest training linker, and hand-feature ranker evaluated on exactly M4 lists. Report missing baseline implementations rather than imply SynLinker or DROP was reproduced. |
| M6 | Context model | Domain sequences/structures and M4 candidate sequences | Candidate score and model manifest | Frozen ESM-2 embeddings plus local-port graph encoder and small linker-sequence encoder; no native linker coordinates or hidden sequence enter query features. |
| M7 | Blind evaluation | Frozen M4–M6 predictions | Per-example ranks, aggregate metrics, uncertainty | Predictions are written before held-out reference exposure; bootstrap by family cluster; report raw N, MRR, top-1/top-5, length error, and failure/abstention. |
| M8 | User-facing recommendation | Two user domains and trained M5/M6 | Ranked FASTA/JSON with applicability flag | Works for homologous and unrelated inputs in software; unrelated outputs explicitly lack empirical success validation. |
| M9 | Structural assessment (stretch) | Top candidates plus domain structures | Closure/clash/domain-preservation reports | Same frozen rules for all methods; structure prediction is supplementary, never labeled functional proof. |

## 3. M1–M2: what counts as a natural linker

Use RCSB PDB experimental protein chains and CATH domain boundaries as the
primary source. InterPro/Pfam may corroborate but must not silently override
CATH. The PDB is not itself a labeled linker dataset. Start with a small
verified subset, then scale only if adjudication precision is acceptable.

An accepted example must have one chain with two consecutive, continuous,
nonoverlapping domain assignments; exactly one intervening amino-acid segment
of length 5–30; unambiguous sequence mapping; no unresolved domain junction;
and an experimentally determined structure. Reject circular permutations,
domain insertions/noncontiguous domains, chain breaks, engineered constructs
not labeled as such, protease-cleaved linkers, and ambiguous overlaps from the
primary training tier. Keep rejection reasons. A gap in domain annotation is
only a **candidate linker** until manual/algorithmic evidence supports that it
is not an unannotated structured domain, terminal tail, or missing residue run.

The hybrid adjudicator combines annotation agreement, DSSP secondary
structure, solvent accessibility, local contacts, resolved-residue fraction,
and simple sequence indicators. Start with explicit rules. A learned
classifier is optional only after a reviewed label set exists; do not train it
on its own pseudo-labels and call the result ground truth. Report manual audit
precision and recall where an independently labeled sample supports both.

## 4. M3: split before training or feature selection

Group all PDB variants of the same UniProt protein. Cluster homologous
sequences and domain families; group equivalent ordered domain-pair
architectures. Freeze entire groups into train/validation/blind partitions
before fitting any scaler, classifier, model, or candidate-retrieval index.
Two test slices:

1. **Related-pair slice:** held-out chains within a known architecture, but
   no near-duplicate sequence. Tests extrapolation within architecture.
2. **Unseen-family/architecture slice:** neither domain-pair architecture nor
   close homologues occur in training. Tests harder transfer. If too few
   examples survive, report that fact and do not conflate the slices.

The user-requested "unrelated proteins" use case means domains drawn from
different source proteins at inference. It is not validated by either natural
slice. Use a separate engineered-fusion evidence set if obtainable; otherwise
present only a feasibility demonstration and mark out-of-distribution risk.

## 5. M4–M6: generation, scoring, and geometry

MVP candidate generation is natural-linker retrieval from training only,
constrained GS-rich enumeration/mutation, and fixed controls. Candidate lists
are created once per query and passed unchanged to every scorer. Mutated and
transplanted sequences are **synthetic alternatives**, not measured failures;
pairwise training labels mean "observed native versus constructed alternative"
only. Exact sequence recovery is secondary: natural linkers can have many
viable alternatives.

The context model has three encoders:

- **Domain context:** frozen ESM-2 embeddings for A and B. Cache by sequence
  checksum; no full fine-tuning in the two-week build.
- **Attachment-port graph:** separate residue graphs around A's C-terminal
  port and B's N-terminal port, using within-domain distances, local
  orientation, accessibility, secondary structure, and protected-site distance.
  A small GNN is optional after a simpler pooled geometric-feature baseline
  works. Separate uploaded PDBs do **not** share a coordinate frame; never
  compute cross-domain distances before an assembled pose exists.
- **Candidate linker:** length/composition and a small sequence encoder.

Concatenate/pool the three outputs and train a small pairwise ranker. Keep a
hand-feature ranker with the same candidate set as the essential baseline.
Do not attribute improvements to the GNN unless ablations show a difference:
hand features; ESM only; geometry only; full model. A non-neural model using
frozen ESM plus geometry is the fallback if sample size is small.

The optional structure stage assembles the complete chain and samples linker
conformations. It reports chain closure, clashes, domain deviation, protected
site obstruction, and uncertainty. It does not turn a synthetic negative into
a proven biological failure or a passing candidate into a proven functional
fusion. Flexible linker pose distributions are not represented by one fold.

## 6. Primary comparison and success criterion

**Task:** rank a fixed list of candidate linkers for each blinded natural
domain pair. Use group-level MRR as the primary metric; top-1/top-5 and length
error are secondary. Report per-slice counts and paired, cluster-bootstrap
confidence intervals. Compare proposed model to retrieval and hand-feature
ranker on identical examples. Fixed GS controls are reported as design
references, but a GS candidate cannot be scored as correct merely because it
is not identical to the natural linker.

The hypothesis is supported only if the blind-set MRR gain over both primary
baselines is positive with a cluster-bootstrap 95% confidence interval
excluding zero. If data are too small for a meaningful interval, report the
effect estimate and uncertainty without a significance claim. If the method
loses or ties, report that result. No test-set tuning.

Legacy tools must be compared on **matched tasks**: DROP/DFLpred/TransDFL
predict linker locations, so compare them only for M2 extraction; SynLinker
retrieves/linker-builds, so compare retrieval in M5. Do not compare a boundary
F1 score against a linker-design MRR score.

## 7. Four-owner, two-week execution

| Days | Data/labels owner | Splits/baselines owner | Model owner | Evaluation/report owner |
|---|---|---|---|---|
| 1–2 | 10 examples, residue-map tests, annotation rules | Schema and split code | ESM/cloud environment smoke test | Freeze question, metrics, and review table |
| 3–5 | Audited dataset and rejection log | Frozen groups, candidate pools, retrieval/hand-feature baseline | Cached embeddings; small ranker smoke test | Independent leakage and 30-example label audit |
| 6–9 | Repair source-specific mapping only | Baseline training and predictions | ESM/geometry ranker and ablations | Validation-only analysis; freeze configuration |
| 10–11 | Dataset provenance lock | Blind baseline predictions | Blind model predictions | Open blind references after hashes; compute paired metrics |
| 12–14 | Dataset methods and flow diagram | Baseline methods and code release | Model methods and failure analysis | Paper, limits, figures, reproduction checklist |

**Day-2 gate:** if 10 high-confidence examples and the backend environment are
not reproducible, cut the GNN. **Day-5 gate:** if the audited dataset and split
are too small or contaminated, do not claim model generalization; submit a
dataset/feasibility result or revise scope with the supervisor. **Day-9 gate:**
freeze all modeling decisions. The frontend is not on the critical path.

## 8. Definition of done

- One command regenerates a small fixture and validates JSON Schema.
- Raw source manifest, rejected records, and accepted examples are auditable.
- Family/architecture split manifest is immutable and leakage tests pass.
- Baselines and modern model score identical candidate lists.
- Blind predictions are hashed and saved before reference reveal.
- Results include N, uncertainty, failed examples, and compute/time costs.
- Two-domain inference emits ranked candidates, full FASTA, provenance, and an
  explicit `natural_reconstruction` or `unrelated_demonstration` evidence tag.
- Paper conclusion states only what the measured endpoints support.

## 9. Primary references for method selection

- RCSB PDB APIs: https://www.rcsb.org/docs/programmatic-access/web-apis-overview
- CATH downloads: https://cathdb.info/download
- SynLinker: https://doi.org/10.1093/bioinformatics/btv447
- DROP: https://doi.org/10.1093/bioinformatics/btq700
- TransDFL: https://doi.org/10.1016/j.gpb.2022.10.004
- ESM-2: https://doi.org/10.1126/science.ade2574
- Li et al. 2026 linker customization: https://doi.org/10.1016/j.synbio.2026.02.003
- McBride et al. on flexible-linker pose uncertainty: https://doi.org/10.1002/prot.70062
