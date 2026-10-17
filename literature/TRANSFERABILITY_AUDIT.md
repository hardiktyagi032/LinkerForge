# Transferability audit of the initial 50-paper pool

Status: first-pass method screening, 9 October 2026. Paper numbers refer to
`FIFTY_PAPER_METHODS_SHORTLIST.md`. **This is not 50 trained models.** A paper
is eligible for a detector experiment only if its mechanism can operate on
per-residue sequence labels without reference-label leakage or a change of
biological task. A transfer experiment is an adaptation, not a claim that the
paper itself solved protein linker detection.

| Paper # | Mechanism to test or disposition | Detector experiment |
|---:|---|---|
| 1 | Suppress easy negatives | Weighted focal loss; running gamma=2 versus original weighted BCE. |
| 2 | Asymmetric positive/negative gradients | Adapt binary asymmetric loss; pending. |
| 3 | Positive-unlabeled risk | **Not valid on DLD explicit negatives**; future expansion-only protocol. |
| 4 | Model-assisted label-error triage | Out-of-fold disagreement audit; pending independent review, not automatic correction. |
| 5 | Test-label error audit | Review a sample of high-impact fold-4 discrepancies; not a model architecture. |
| 6 | Peer-network noisy-label filtering | Conditional on demonstrated high label-noise rate; otherwise over-complex. |
| 7 | Variable-length segment decoding | Semi-Markov/span head; pending. |
| 8 | Direct average-precision optimization | AP-loss ablation; pending, same batch/split. |
| 9 | Reject low-confidence calls | Precision/coverage reporting; evaluation policy, not a new encoder. |
| 10 | Noise-robust loss | Conditional on label-noise audit. |
| 11 | Linker classes | Inform class-aware targets; no runnable algorithm. |
| 12 | HMM region decoding | Reimplement only after feature/input match. |
| 13 | Nonstationary HMM | Reimplement only after feature/input match. |
| 14 | Historical neural predictor | Benchmark if code/features can be reproduced. |
| 15 | SVM plus selected features | Benchmark if original feature contract can be reproduced. |
| 16 | Random forest | Feature-matched baseline; pending. |
| 17 | DFLpred | Published comparator; check runnable weights/licence. |
| 18 | Protein-level context | Add whole-protein features as a separate ablation; pending. |
| 19 | Disorder-to-linker transfer | Separate staged-training experiment; pending overlap audit. |
| 20 | Evaluate against other IDR classes | Required evaluation slice; no model transfer. |
| 21 | Community benchmark | External evaluation resource, not training method. |
| 22 | DLD class distinctions | Five/six-way label ablation; pending. |
| 23 | Current linker predictor | External comparator; DLD fold5 contaminated by its training source. |
| 24 | Encoder fine-tuning | LoRA versus frozen ESM-2; pending GPU budget. |
| 25 | Disorder-adapted encoder | Candidate initialization; training-overlap audit first. |
| 26 | Parameter-efficient tuning | Same mechanism family as #24; not an independent method. |
| 27 | Candidate sequence generation | Downstream task, not detector. |
| 28 | Fusion assembly | Downstream task, not detector. |
| 29 | Circular permutation | Different topology; no detector transfer. |
| 30 | Domain insertion loop design | Different topology; no detector transfer. |
| 31 | Insertion-site prediction | Different target; possible future port-selection branch. |
| 32 | Experimental flexibility library | No supervised detector method. |
| 33 | Fixed-pair linker optimization | Downstream task, not detector. |
| 34 | Fusion workflow | Downstream software comparison. |
| 35 | Multimodal fusion design | Downstream ranker comparison, not current detector. |
| 36 | Linker review | Background; no independent method. |
| 37 | Fusion-structure review | Background; no independent method. |
| 38 | Fusion-structure case study | Downstream structural evaluation. |
| 39 | Flexible domain pose uncertainty | Downstream validation caveat. |
| 40 | Domain-linker propensity | Potential auxiliary boundary feature; independent-domain-map requirement. |
| 41 | Domain-linker propensity | Same strategy family as #40. |
| 42 | Evolutionary boundary signals | Auxiliary feature; MSA cost and leakage audit first. |
| 43 | Boundary regression | External-domain-map ablation, not linker truth. |
| 44 | Residual/BiLSTM boundary model | External-domain-map ablation, not linker truth. |
| 45 | BERT domain boundaries | External-domain-map ablation, not linker truth. |
| 46 | Loop-length features | Region-length feature/decoder ablation. |
| 47 | Composition index | Cheap feature baseline. |
| 48 | Discontinuous-domain handling | Data-quality edge-case audit. |
| 49 | Threading-based boundaries | Optional external-domain-map comparison; expensive. |
| 50 | Domain insertion architectures | Different topology; family-split context only. |

## Interpretation

The first 50-paper pool does **not** contain 50 independent compatible
solutions to the same classification problem. Twenty-plus records describe
downstream linker choice, reviews, benchmarks, or different topologies. A
valid 50-method transfer study therefore requires replacing those records
with newly screened imbalance, incomplete-label, noisy-label, and
sequence-segmentation papers. We must not claim that all 50 were tested by
running the same focal-loss experiment repeatedly.

## Controlled experiment contract

1. Same DLD train folds 1–3, validation fold 4, tokenizer, ESM-2 revision,
   CNN head, seed, residue masking, and 10-epoch budget for loss ablations.
2. One mechanism changes per run. Select checkpoint by validation AUPRC.
3. Also report maximum validation recall at empirical precision >= 0.90,
   no-linker protein specificity, and region-level metrics when available.
4. Only combine individually beneficial, mechanistically compatible changes;
   rerun the combined system against each constituent, rather than assuming
   effects add.
5. DLD fold 5 was previously viewed. It is not a new untouched blind set for
   selection of these adaptations. A new independent, homology-audited set
   is required for a confirmatory claim.
