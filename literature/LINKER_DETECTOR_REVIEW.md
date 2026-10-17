# Linker-detection methods relevant to LinkerForge

Status: targeted literature review, 8 October 2026. This is a design and
benchmarking guide, not evidence that LinkerForge has outperformed any method.

## Exact task and boundary

The detector takes a protein sequence and, when available, a separately sourced
domain map. It must decide whether an inter-domain peptide linker is present,
identify its residue interval, and distinguish independent-domain linker (IDL)
from dependent-domain linker (DDL) where the reference labels support that
distinction. This is **not** the downstream task of selecting a peptide to join
two user-supplied protein structures. A detected natural linker is an
observation or pseudo-label, not proof that its sequence is the best engineered
fusion linker. Domain annotations alone are not linker truth.

## Direct and historical comparators

| Work | Relevant contribution | Implication for our experiment |
| --- | --- | --- |
| [Shatnawi, Zaki & Yoo, BMC Bioinformatics 2014](https://doi.org/10.1186/1471-2105-15-S16-S8) | Random-forest detection of inter-domain linkers. | Reimplement or run their public method on the **same** frozen split; no cross-paper score comparison. |
| [DFLpred, Bioinformatics 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC4908364/) | Sequence-based prediction of disordered flexible linkers. | A fast established sequence baseline, subject to runnable code and task-label mapping. |
| [CAID2 linker assessment, 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC10968229/) | Evaluates linker residues against non-linker and other disordered residues, plus linker-bearing proteins. | Report residue AUPRC/MCC, disordered-negative discrimination and sequence-level `none` specificity separately. |
| [IDP-ELM, Journal of Chemical Information and Modeling 2024](https://doi.org/10.1021/acs.jcim.3c01202) | Protein-language-model ensemble includes flexible-linker prediction. | A modern direct comparator, not a novelty gap by itself. |
| [DLD, Journal of Molecular Biology 2026](https://doi.org/10.1016/j.jmb.2026.169994) | A domain-linker-domain dataset distinguishing IDL and DDL, with a PLM-embedding/CNN experiment. | Our three-class architecture overlaps this work. Acquire the reference data and honor its provenance and labels. |
| [LINKER-Pred/Lite documentation](https://pcrgwd.ucd.ie/linker_pred/help/) and [public Lite code](https://github.com/deemeng/punch_linker_light) | Contemporary linker predictor using protein representations/CNN. | Run as a current comparator where available; its server manuscript is described as submitted, so do not misstate peer-review status. |
| [CAID3 challenge results](https://caid.idpcentral.org/challenge/results) and [assessment](https://pmc.ncbi.nlm.nih.gov/articles/PMC12750029/) | Independent linker reference and community methods; the current downloadable linker set has 31 sequences. | Reserve for untouched external evaluation. It is far too small to support a million-label claim. |

## Modern ML evidence for training choices

| Work | What it actually supports | Limit |
| --- | --- | --- |
| [Fine-tuning protein language models boosts predictions across diverse tasks, Nature Communications 2024](https://doi.org/10.1038/s41467-024-51844-2) | Per-residue and other tasks often benefit from fine-tuning compared with frozen embeddings; the paper examines parameter-efficient LoRA. | Not a demonstrated gain for *our* linker labels. Test frozen ESM-2 and LoRA ESM-2 on an identical split. |
| [Democratizing protein language models with parameter-efficient fine-tuning, PNAS 2024](https://doi.org/10.1073/pnas.2405840121) | PEFT can reduce trainable-parameter/compute burden for protein tasks. | Does not establish linker-specific superiority or million-sequence inference feasibility. |
| [CAID3 assessment](https://pmc.ncbi.nlm.nih.gov/articles/PMC12750029/) | Newer high-performing disorder/linker methods commonly use protein language models. | Published leaderboard scores use their own reference and rules. Re-evaluate locally. |

## Benchmark design, before any model fitting

1. Pin source versions and resolve real residue-level labels. The DLD labels
   are systematically constructed references; DisProt/CAID annotations have
   different evidence classes. Keep them distinct. Require explicit negative
   proteins rather than treating all unannotated residues as known negatives.
2. Cluster all labeled proteins by sequence homology, then assign whole
   clusters to train, calibration, internal test, and untouched external test.
   Audit sequence identity across partitions. Do this **before** training,
   threshold selection, hard-negative mining or pseudo-labeling.
3. Fit a composition/length/domain-gap rule and the 2014 random-forest-style
   feature model, then our small GPU CNN. Evaluate DFLpred, IDP-ELM and
   LINKER-Pred/Lite on the same examples if runnable/licensed. Finally compare
   a frozen ESM-2 residue head and a LoRA-adapted ESM-2 model on the same
   reference split. Record compute, throughput and failures as well as scores.
4. Tune thresholds on calibration clusters only. Report residue AUPRC, MCC,
   precision/recall, region IoU and boundary tolerance, protein-level no-linker
   false-positive rate, calibration, and bootstrap confidence intervals over
   proteins/clusters. Score IDL and DDL separately if there are enough cases.
5. Freeze model and thresholds before the external CAID-style reference. Do not
   use external annotations to train, select thresholds, or repair mistakes.
6. Only then stream InterPro/UniProt candidates. Count accepted *unique*
   accessions per split; the detector's outputs are pseudo-labels. Test whether
   they help the separate A--linker--B ranker against a no-expansion ablation.

## Defensible claim to test

The research question is whether a provenance-aware, homology-separated
natural-linker detection and pseudo-label pipeline improves downstream
linker-choice ranking for two supplied domains, while controlling false
linker calls and compute cost. The classifier architecture itself is not
claimed as new. Improvement must be shown on the same blind examples against
the older methods and the contemporary PLM/CNN comparators; failure to improve
is a valid result. Million-scale coverage describes the **unlabeled input
stream or pseudo-labeled expansion**, not a million independent verified
linker labels.

## Current evidence and blockers

The local InterPro 110.0 streaming probe inspected 100,000 accession groups;
14,154 had at least one candidate 5--30-residue domain gap. These are windows,
not truth labels. The first-accession prefix is not a random sample. No GPU
detector has been trained, no modern baseline has been run on a common split,
and no cloud job has been launched. The public DLD download endpoint was not
retrievable during this review; the CAID3 31-sequence linker reference is
accessible but should be an external test, not a training set. A valid training
run requires mapped reference labels, negative examples, cluster IDs, CUDA
PyTorch on the intended host, and an immutable input manifest.
