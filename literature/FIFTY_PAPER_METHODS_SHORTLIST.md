# LinkerForge: initial mixed 50-paper screening pool

Status: title/abstract-level methods triage, 9 October 2026. This is **not**
a claim that 50 full texts were critically read or that all methods were
implemented, nor are all 50 detector-method papers. The first ten are cross-domain ML ideas; the rest establish
linker/domain/disorder baselines, datasets, and validation hazards. DOI/primary
publisher links identify the source. This list is a screening artifact;
before formal citation in a paper, verify the full text, exact method,
publication status, and relevance to our task.

## Cross-domain ML methods to ablate

| # | Paper | Link | Transfer hypothesis |
|---:|---|---|---|
| 1 | Focal Loss for Dense Object Detection | https://openaccess.thecvf.com/content_iccv_2017/html/Lin_Focal_Loss_for_ICCV_2017_paper.html | Rare positive residues versus easy background; focal-loss ablation implemented. |
| 2 | Asymmetric Loss for Multi-Label Classification | https://openaccess.thecvf.com/content/ICCV2021/html/Ridnik_Asymmetric_Loss_for_Multi-Label_Classification_ICCV_2021_paper.html | Differential treatment of easy negatives; requires binary adaptation. |
| 3 | Positive-Unlabeled Learning with Non-Negative Risk Estimator | https://papers.nips.cc/paper/2017/hash/7cce53cf90577442771720a370c3c723-Abstract.html | Only for genuinely unlabeled expansion, not curated DLD negatives. |
| 4 | Confident Learning: Estimating Uncertainty in Dataset Labels | https://research.google/pubs/confident-learning-estimating-uncertainty-in-dataset-labels/ | Out-of-fold label-error triage; never automatic relabeling. |
| 5 | Pervasive Label Errors in Test Sets Destabilize Machine Learning Benchmarks | https://datasets-benchmarks-proceedings.neurips.cc/paper_files/paper/2021/hash/f2217062e9a397a1dca429e7d70bc6ca-Abstract-round1.html | Audit high-impact reference discrepancies before performance claims. |
| 6 | Co-teaching: Robust Training of Deep Neural Networks with Extremely Noisy Labels | https://papers.neurips.cc/paper_files/paper/2018/hash/a19744e268754fb0148b017647355b7b-Abstract.html | Two-model filtering only if audited label noise warrants compute. |
| 7 | Semi-Markov Conditional Random Fields for Information Extraction | https://papers.neurips.cc/paper/2648-semi-markov-conditional-random-fields-for-information-extraction.pdf | Region-level decoding instead of independent residues. |
| 8 | Stochastic Optimization of Areas Under Precision-Recall Curves with Provable Convergence | https://proceedings.nips.cc/paper_files/paper/2021/hash/0dd1bc593a91620daecf7723d2235624-Abstract.html | Optimize AP under imbalance; more complex than focal loss. |
| 9 | Selective Classification for Deep Neural Networks | https://proceedings.neurips.cc/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html | Formalize high-confidence calls versus abstention. |
| 10 | Asymmetric Loss Functions for Learning with Noisy Labels | https://proceedings.mlr.press/v139/zhou21f.html | Robust loss if systematic annotation errors are demonstrated. |

## Direct linker detection and benchmark evidence

| # | Paper | Link | Screening note |
|---:|---|---|---|
| 11 | An analysis of protein domain linkers: their classification and role in protein folding | https://doi.org/10.1093/protein/15.11.871 | Natural linker categories. |
| 12 | Prediction of protein interdomain linker regions by a hidden Markov model | https://doi.org/10.1093/bioinformatics/bti363 | Historical segmentation comparator. |
| 13 | Prediction of Protein Interdomain Linker Regions by a Nonstationary Hidden Markov Model | https://doi.org/10.1198/016214508000000661 | Sequence-dependent transitions. |
| 14 | Identification of putative domain linkers by a neural network | https://doi.org/10.1186/1471-2105-7-323 | Historical neural comparator. |
| 15 | DROP: an SVM domain linker predictor trained with optimal features selected by random forest | https://doi.org/10.1093/bioinformatics/btq700 | Feature-based comparator. |
| 16 | Protein inter-domain linker prediction using Random Forest and amino acid physiochemical properties | https://doi.org/10.1186/1471-2105-15-S16-S8 | Classical ML comparator. |
| 17 | DFLpred: High-throughput prediction of disordered flexible linker regions in protein sequences | https://doi.org/10.1093/bioinformatics/btw280 | Direct flexible-linker comparator. |
| 18 | APOD: accurate sequence-based predictor of disordered flexible linkers | https://doi.org/10.1093/bioinformatics/btaa808 | Local and protein-level context. |
| 19 | TransDFL: Identification of Disordered Flexible Linkers in Proteins by Transfer Learning | https://doi.org/10.1016/j.gpb.2022.10.004 | Disorder-to-linker transfer. |
| 20 | Assessment of Disordered Linker Predictions in the CAID2 Experiment | https://pmc.ncbi.nlm.nih.gov/articles/PMC10968229/ | Non-linker disorder evaluation. |
| 21 | Critical Assessment of Protein Intrinsic Disorder Round 3 | https://pmc.ncbi.nlm.nih.gov/articles/PMC12750029/ | External assessment; avoid cross-dataset score comparison. |
| 22 | Expanding the Landscape of Disordered Flexible Linkers: A Structural and Computational Framework for DLD Dataset Assembly | https://doi.org/10.1016/j.jmb.2026.169994 | Current dataset and direct pLM/CNN overlap. |
| 23 | LINKER-Pred: A Deep Learning Method and Web-Server for the Prediction of Disordered Flexible Linkers in Proteins | https://doi.org/10.1101/2025.10.29.685455 | Preprint/current direct comparator; check peer-review status. |
| 24 | Fine-tuning protein language models boosts predictions across diverse tasks | https://doi.org/10.1038/s41467-024-51844-2 | Frozen versus adapted protein encoder. |
| 25 | LoRA-DR-suite: adapted embeddings predict intrinsic and soft disorder from protein sequences | https://pmc.ncbi.nlm.nih.gov/articles/PMC12261480/ | Disorder-adapted ESM; audit data overlap. |
| 26 | Democratizing protein language models with parameter-efficient fine-tuning | https://doi.org/10.1073/pnas.2405840121 | Compute-efficient adaptation. |

## Domain boundaries, fusion context, and downstream task

| # | Paper | Link | Screening note |
|---:|---|---|---|
| 27 | LINKER: a program to generate linker sequences for fusion proteins | https://doi.org/10.1093/protein/13.5.309 | Historical linker generator. |
| 28 | SynLinker: an integrated system for designing linkers and synthetic fusion proteins | https://doi.org/10.1093/bioinformatics/btv447 | Closest integrated prior system. |
| 29 | CirPred, the first structure modeling and linker design system for circularly permuted proteins | https://doi.org/10.1186/s12859-021-04403-1 | Different fusion topology. |
| 30 | A computational method for the design of nested proteins by loop-directed domain insertion | https://doi.org/10.1002/prot.25445 | Loop/interface design precedent. |
| 31 | Rational engineering of allosteric protein switches by in silico prediction of domain insertion sites | https://doi.org/10.1038/s41592-025-02741-z | Site-prediction precedent. |
| 32 | Construction of a linker library with widely controllable flexibility for fusion protein design | https://doi.org/10.1007/s00253-015-6985-3 | Experimental linker property diversity. |
| 33 | Design and optimization of a linker for fusion protein construction | https://doi.org/10.1016/j.pnsc.2008.12.007 | Fixed-pair design precedent. |
| 34 | An open source in silico workflow to assist in the design of fusion proteins | https://doi.org/10.1016/j.compbiolchem.2024.108209 | Software workflow comparator. |
| 35 | Functional customization of peptide linkers in fusion proteins through multimodal deep learning approach | https://doi.org/10.1016/j.synbio.2026.02.003 | Newer ML fusion-linker design comparator. |
| 36 | Fusion Protein Linkers: Property, Design and Functionality | https://doi.org/10.1016/j.addr.2012.09.039 | Design/background review. |
| 37 | Artificial intelligence in fusion protein three-dimensional structure prediction | https://doi.org/10.1002/ctm2.1789 | Structure-prediction limitations. |
| 38 | Fusion of Two Unrelated Protein Domains in a Chimera Protein and Its 3D Prediction | https://doi.org/10.1002/prot.26398 | Unrelated-domain fusion context. |
| 39 | Predicting Pose Distribution of Protein Domains Connected by Flexible Linkers Is an Unsolved Problem | https://doi.org/10.1002/prot.70062 | Single predicted pose is insufficient. |
| 40 | An Improved Profile-Level Domain Linker Propensity Index for Protein Domain Boundary Prediction | https://doi.org/10.2174/092986611794328717 | Domain-boundary features. |
| 41 | Domain boundary prediction based on profile domain linker propensity index | https://doi.org/10.1016/j.compbiolchem.2006.01.001 | Domain-boundary features. |
| 42 | DoBo: Protein domain boundary prediction by integrating evolutionary signals and machine learning | https://doi.org/10.1186/1471-2105-12-43 | Boundary model comparator. |
| 43 | DomNet: Protein Domain Boundary Prediction Using Enhanced General Regression Network and New Profiles | https://doi.org/10.1109/tnb.2008.2000747 | Boundary model comparator. |
| 44 | Res-Dom: predicting protein domain boundary from sequence using deep residual network and Bi-LSTM | https://doi.org/10.1093/bioadv/vbac060 | Modern boundary model. |
| 45 | BERTDom: Protein Domain Boundary Prediction Using BERT | https://doi.org/10.31577/cai_2023_3_667 | Transformer boundary model. |
| 46 | Improvement of domain linker prediction by incorporating loop-length-dependent characteristics | https://doi.org/10.1002/bip.20361 | Region-length features. |
| 47 | Inter-domain linker prediction using amino acid compositional index | https://doi.org/10.1016/j.compbiolchem.2015.01.006 | Composition comparator. |
| 48 | Extending Protein Domain Boundary Predictors to Detect Discontinuous Domains | https://doi.org/10.1371/journal.pone.0141541 | Annotation edge cases. |
| 49 | ThreaDom: extracting protein domain boundary information from multiple threading alignments | https://doi.org/10.1093/bioinformatics/btt209 | External domain-map sensitivity. |
| 50 | Family-level specialization in protein domain insertion architectures | https://doi.org/10.1002/pro.70586 | Domain-family generalization. |

## Decision rule

We do **not** implement 50 papers as 50 model components. Methods 1, 3, 4,
7, and 8 yield separable experiments, contingent on the proper label type.
Methods 11–50 constrain the task and baselines. Each experiment must hold
DLD folds, architecture, seed, and validation metric fixed where possible.
Select on validation only. DLD fold 5 has already been examined in earlier
work and is not a fresh blind set for selecting new methods.
