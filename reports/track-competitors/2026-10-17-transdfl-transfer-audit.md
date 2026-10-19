# TransDFL transfer-method audit — 2026-10-17

Primary source: [Pang and Liu, *TransDFL*, Genomics, Proteomics & Bioinformatics](https://gpb.big.ac.cn/articles/download/1041), DOI 10.1016/j.gpb.2022.10.004. The paper lists its [source release](https://ngdc.cncb.ac.cn/biocode/tools/BT007312); availability is a publication statement, not a verified successful execution in our environment.

## Documented method

TransDFL transfers an RFPR-IDP residue-sequence labeller from intrinsic-disorder pretraining to DFL fine-tuning. The paper's Figure 3 specifies a **52-dimensional per-residue representation** generated with sequence/profile and predicted-structure tools including PSI-BLAST, SPIDER, SABLE and SEVEN. Figure 4 and §Methods specify a BiLSTM followed by CNN and fully connected per-residue output. The IDR stage uses binary cross-entropy; DFL fine-tuning uses weighted binary cross-entropy with the positive weight chosen on a DFL validation set. This is not simply “use a disorder-pretrained protein language model.”

## What LinkerForge matches and does not match

Our protected disorder-transfer runner does stage an auxiliary IDR task then DFL fine-tuning, so the **training-task order** is analogous. It uses frozen ESM2-35M embeddings, a SAM-like or other experimental head, 510-residue chunks, and its own loss; it does **not** reproduce RFPR-IDP's 52-dimensional profile, BiLSTM-CNN parameters, whole-protein sequence handling, or the paper's exact weighted-loss selection. The auxiliary source also differs. Therefore neither its results nor its failure can be interpreted as a faithful TransDFL reproduction.

The protected-data audit found 72 auxiliary records fully labelled for their source task, versus only 28.9% known DFL training residues. This is a real difference in supervision density and task semantics. It does not establish whether the discrepancy causes external transfer failure. The no-positive proxy is not a true no-linker set: 13/17 proxy proteins contain unknown regions.

## Actionable fair test

Before attributing any gain to TransDFL's architecture, preregister a **same-data** BiLSTM-CNN versus current head ablation using the same protected split, frozen ESM2 representation, masks, auxiliary records, seeds and scoring. This isolates the sequence head, but must be labelled an adaptation, not TransDFL reproduction. A true reproduction would require the released feature-generation pipeline, checkpoint/dependency verification, source-label mapping and equal-coverage evaluation. Do not tune on the spent CAID3 retrospective. The ML track's completed global-context repeat should be reconciled first; its observed seed-to-seed variation makes another one-seed verdict unsafe.

Local provenance: `scripts/run_dfl_disorder_transfer.py` SHA-256 `43c529dd72cc42f4ff1a5ade38a5d5601a6e4c7ecdce6501c162219a8128a4d4`; protected baseline config SHA-256 `e49780fa6917a446a73d8fb93ae9303151268617fe482cd357c0fa1db69035a1`; transfer audits `reports/track-transfer/2026-10-17-protected-label-coverage.json` and `reports/track-transfer/2026-10-17-no-positive-proxy-coverage.json`. No GPU job or CAID3 comparison was run.
