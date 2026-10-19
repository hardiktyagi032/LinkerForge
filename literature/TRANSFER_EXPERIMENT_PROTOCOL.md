# Cross-domain strategy transfer: experimental protocol

Status: active methods study, 9 October 2026. This protocol addresses the
linker-residue **detector**, not the downstream two-domain linker-choice
ranker. Its purpose is to find a reproducible improvement over frozen ESM-2
35M + residue CNN, not to claim novelty from reproducing an existing loss.

## Paper-screening gate

For each candidate paper, record the original task, exact data pathology,
mechanism, required labels/features, code/weights, and adaptation needed for
our binary per-residue task. Assign one disposition:

- `independent_ablation`: runnable mechanism with DLD training labels;
- `shared_mechanism`: adds evidence to an existing ablation, not a duplicate job;
- `needs_new_evidence`: requires verified label noise, truly unlabeled data,
  independent domain maps, or other absent input;
- `benchmark_only`: published comparator, dataset, or evaluation rule;
- `different_task`: fusion design, domain insertion, or other non-detector task.

The existing first 50-paper pool is mixed and must not be reported as 50
eligible ablations. Replace nonmatching entries before claiming a 50-paper
same-problem screen. Never fabricate a method-specific model where a paper
contains no runnable ML mechanism.

### Cross-domain replacement candidates (not yet full-text adapted)

These primary papers address a data pathology closer to ours than the
downstream fusion papers in the first pool. They are screening candidates,
not completed trials:

| Problem | Candidate papers | Proposed adaptation gate |
|---|---|---|
| Class imbalance | [Class-Balanced Loss](https://openaccess.thecvf.com/content_CVPR_2019/html/Cui_Class-Balanced_Loss_Based_on_Effective_Number_of_Samples_CVPR_2019_paper.html), [LDAM](https://papers.neurips.cc/paper_files/paper/2019/hash/621461af90cadfdaf0e8d4cc25129f91-Abstract.html), [Balanced Softmax](https://proceedings.neurips.cc/paper/2020/hash/2ba61cc3a8f44143e1f2f13b2b729ab3-Abstract.html), [Equalization Loss](https://openaccess.thecvf.com/content_CVPR_2020/html/Tan_Equalization_Loss_for_Long-Tailed_Object_Recognition_CVPR_2020_paper.html), [Seesaw Loss](https://openaccess.thecvf.com/content/CVPR2021/html/Wang_Seesaw_Loss_for_Long-Tailed_Instance_Segmentation_CVPR_2021_paper.html) | Confirm binary-label formulation and whether assumed balanced test priors fit DLD. |
| Rare-region segmentation | [Tversky loss](https://arxiv.org/abs/1706.05721), [Boundary loss](https://proceedings.mlr.press/v102/kervadec19a.html), [Lovasz-Softmax](https://openaccess.thecvf.com/content_cvpr_2018/papers/Berman_The_LovaSz-Softmax_Loss_CVPR_2018_paper.pdf), [Online Hard Example Mining](https://www.cv-foundation.org/openaccess/content_cvpr_2016/papers/Shrivastava_Training_Region-Based_Object_CVPR_2016_paper.pdf) | Translate pixels/voxels to residues while preserving contiguous segments. |
| Label noise | [Generalized Cross Entropy](https://papers.neurips.cc/paper_files/paper/2018/hash/f2925f97bc13ad2852a7a551802feea0-Abstract.html), [Symmetric Cross Entropy](https://openaccess.thecvf.com/content_ICCV_2019/html/Wang_Symmetric_Cross_Entropy_for_Robust_Learning_With_Noisy_Labels_ICCV_2019_paper.html), [Early-Learning Regularization](https://proceedings.neurips.cc/paper_files/paper/2020/hash/ea89621bee7c88b2c5be6681c8ef4906-Abstract.html), [DivideMix](https://iclr.cc/virtual_2020/poster_HJgExaVtwr.html), [MentorNet](https://proceedings.mlr.press/v80/jiang18c), [JoCoR](https://openaccess.thecvf.com/content_CVPR_2020/papers/Wei_Combating_Noisy_Labels_by_Agreement_A_Joint_Training_Method_with_CVPR_2020_paper.pdf) | First demonstrate label noise and review flagged examples; otherwise no justification. |
| Unlabeled expansion | [Learning under Selected-At-Random PU](https://proceedings.mlr.press/v94/bekker18a.html), [Noisy Student](https://openaccess.thecvf.com/content_CVPR_2020/html/Xie_Self-Training_With_Noisy_Student_Improves_ImageNet_Classification_CVPR_2020_paper.html) | Needs a separately identified unlabeled corpus and a contamination-safe test. |
| Sequence spans | [BiLSTM-CNN-CRF](https://aclanthology.org/P16-1101/), [Neural Architectures for NER](https://aclanthology.org/N16-1030.pdf), [Segmental RNN](https://arxiv.org/abs/1511.06018), [SpanBERT](https://aclanthology.org/2020.tacl-1.5/) | Evaluate interval recovery and boundary tolerance, not only residue accuracy. |

## Common run contract

Use DLD folds 1–3 for training and fold 4 for development. Do not select on
fold 5: its labels were examined in earlier LinkerForge work. Hold the frozen
ESM-2 35M revision, residue CNN, windowing, positive weight, seed, epochs,
optimizer and batch size constant for loss ablations. Save a separate run
directory with manifest, epochs, checkpoint, and exact source/data hashes.

For each ablation, compare validation AUPRC, maximum recall at empirical
precision >= 0.90 with at least 50 true-positive residues, no-linker-protein
specificity, region overlap, and runtime. The current trainer logs AUPRC and
F1; `score_esm2_validation_checkpoint.py` supplies the high-precision
operating point after a run. Region-level evaluation remains to be built.

## Active and next trials

| Mechanism | Source | Change from baseline | State |
|---|---|---|---|
| Weighted BCE | Original LinkerForge run | Reference | completed previously |
| Focal loss | Lin et al., ICCV 2017 | gamma=2, all else fixed | completed; 35M validation AUPRC 0.399293 vs weighted-BCE 0.399801; not promoted |
| Asymmetric focusing | Ridnik et al., ICCV 2021 | binary-adapted negative focusing, gamma=2 | implementation and unit tests; training not run |
| BCE plus Tversky | Salehi et al., 2017 | soft segment overlap with FP penalty | implementation and unit tests; training not run |
| Online hard-negative mining | Shrivastava et al., CVPR 2016 | retain all positives and highest-loss negatives | implementation and unit tests; training not run |
| Positive-unlabeled risk | Kiryo et al., NeurIPS 2017 | requires unlabeled corpus plus class prior | ineligible on DLD explicit negatives |
| Confident learning | Northcutt et al., JAIR 2021 | out-of-fold review queue | design only; do not relabel by prediction |
| Semi-Markov segment model | Sarawagi & Cohen, NeurIPS 2004 | sequence-span decoder | design only |

The [prioritized label-and-span experiment](./BREAKTHROUGH_STRATEGY.md) is
the highest-chance next *hypothesis*, not a completed result. Three 8M
loss-variant screening jobs completed. Their initial automatic 35M gate
required a >=0.01 AUPRC gain, but this was misaligned with the prespecified
primary objective: 8M asymmetric focusing increased recall at >=0.90
precision from 0.043513 to 0.059790 with unchanged no-linker-protein
specificity (0.957447), while AUPRC changed only from 0.275220 to 0.275511.
One matched 35M asymmetric confirmation is in progress. Do not infer a 35M
improvement from the 8M result or select a final model on this single
development split.

The asymmetric and Tversky functions are **adaptations**, not reproductions
of the original authors' exact experiments. The Tversky adaptation is
weighted BCE + 0.5 times a soft 1-D Tversky term with FP/FN coefficients
0.7/0.3. It must be described as such in any paper.
Hard-negative mining is likewise a binary per-residue adaptation of the
[object-detection strategy](https://www.cv-foundation.org/openaccess/content_cvpr_2016/papers/Shrivastava_Training_Region-Based_Object_CVPR_2016_paper.pdf),
not a reproduction of its detector.

## Promotion and hybridization

An ablation earns a hybrid test only if it improves the prespecified main
metric beyond run-to-run noise and does not meaningfully damage the
high-precision recall or no-linker specificity. Repeat promising variants
with multiple seeds. Combine only complementary mechanisms (for example,
encoder adaptation and segment decoding), then compare the hybrid against
each component and the original baseline at matched compute. A separate
post-training-source, homology-audited test is required for a final claim.

## Execution

Current run directories are ignored `artifacts/`. Use a configured CUDA
environment and set `HF_HOME=artifacts/hf-cache` plus `HF_HUB_OFFLINE=1` when
the exact ESM revision is cached. Do not change the model revision to bypass
network failure.

```powershell
$env:HF_HOME = (Join-Path (Get-Location).Path 'artifacts\hf-cache')
$env:HF_HUB_OFFLINE = '1'
.\.venv-gpu\Scripts\python.exe scripts\train_esm2_linker_detector.py --train data\processed\dld_reference\dld_train.jsonl.gz --validation data\processed\dld_reference\dld_validation.jsonl.gz --output-dir artifacts\esm2-35m-asymmetric-run-001 --model-id facebook/esm2_t12_35M_UR50D --revision 6fbf070e65b0b7291e7bbcd451118c216cff79d8 --epochs 10 --batch-size 4 --positive-weight 6 --focal-gamma 2 --loss-name asymmetric
```

Run one large trial at a time on the local 6 GB GPU; the college cloud may
parallelize independent jobs after its environment is pinned and tested.
