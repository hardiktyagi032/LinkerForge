# Part 1 Completion: Two-Stage Domain-Gated Conformal Calling (`B1`–`B3`) and Provenance-Stratified Mined & Natural Linker Dataset (`v1`)

**Date:** 2026-10-19  
**Branch:** `codex/classifier-foundation`  
**Dataset Manifest (`data/processed/mined_and_natural_linkers_v1/manifest.json`) SHA-256:** `009ea585050efe9c6af0b94b9224401a3cc026a6ddba9bb3c59e44c5bd078658`  
**Tracked Summary Artifact:** `reports/mined_and_natural_linkers_v1_summary_2026-10-19.json`

---

## 1. Executive Summary

This milestone completes **Part 1** of the LinkerForge workflow defined in `CURRENT_DIRECTION_2026-10-18.md` and `CHECKLIST.md` (`B1`, `B2`, `B3`) and delivers the hash-pinned, provenance-stratified **Mined and Natural Linker Dataset (`mined_and_natural_linkers_v1`)** for **Part 2** (Geometry-Guided Design + Template Retrieval Baseline `X2`):

1. **Why Sequence-Only Residue Scoring Alone Cannot Mine Proteomes (`B2`/`B3` Diagnosis):**
   - On the family-disjoint `B1 V2` `development` split (`28` proteins, `547` known `1` residues, `518` known `0` residues), the 3-seed `ThreeLayerDFLCNN` over frozen `esm2_t12_35M_UR50D` achieved `0.7611 ± 0.0110` APS and `0.8583 ± 0.0080` AUROC (`reports/DFL_B1_V2_THREE_LAYER_CNN_BASELINE_2026-10-18.md`).
   - However, when the frozen Seed-31 checkpoint (`c0d356c55ed83807353e66b875501c61b17f0b9b83f2910c0f1147f6409fdf6f`, threshold `0.7351981997489929`) was applied across all windows of the 9-protein `auxiliary` experimental-order panel (`reports/DFL_B1_V2_SEED31_FROZEN_ORDER_PANEL_VALIDATION_2026-10-18.md`), it produced `14 / 194` false-positive order residues (`92.78%` residue specificity) across `3 / 9` proteins. At a proteome-wide inter-domain linker base rate of $\pi \approx 1\text{--}2\%$, a $7.22\%$ per-residue false-positive rate yields a false discovery rate $>80\%$ if applied to unsegmented full-length proteins.
2. **Resolution via Two-Stage Domain-Boundary Gating + Conformal Risk Control (`src/linkerforge/detector/domain_gate.py` & `src/linkerforge/detector/conformal_mining.py`):**
   - **Stage 1 (`domain_gap_candidates`):** Restricts candidate spans to $5\text{--}60\text{ aa}$ inter-domain gaps between adjacent, non-overlapping, distinct structural domain calls (`left.accession != right.accession`), deterministically eliminating single-domain interiors, N/C-terminal disordered tails, overlapping domain annotations, and homo-repeat loops (`PF00001`–`PF00001`).
   - **Stage 2 (`calibrate_conformal_threshold` & `call_two_stage_interdomain_spans`):** Applies Learn-Then-Test (LTT) / exact one-sided Clopper–Pearson upper risk bounds (`alpha = 0.05`) on top of Stage 1 candidate spans using frozen Seed-31 `ThreeLayerDFLCNN` probabilities.
   - **Empirical Improvement (`B2` & `B3`):**
     - On `development` (`B2`), two-stage domain-gated calibration reduces empirical false positives on known labels from `12` (`6.09%` empirical FDR, `9.68%` 95%-UCB FDR ungated) to **`1` false positive against `93` true positives** (**`1.06%` empirical FDR / `98.94%` empirical precision**, and **`4.95%` 95%-UCB FDR / `95.05%` guaranteed lower-bound precision** at calibrated threshold `0.639120`).
     - On the 40-protein benchmark-disjoint **No-Linker Specificity Panel (`B3`)** (`9` `auxiliary` experimental-order proteins + `31` single-domain / homo-domain non-linker proteins), two-stage calling achieves **`100.0%` specificity (`0 / 31` false positives)** on single-domain/homo-repeat proteins and **`97.50%` protein-level specificity (`39 / 40` proteins with zero high-confidence calls)** overall.
3. **Provenance-Stratified Dataset for Part 2 (`data/processed/mined_and_natural_linkers_v1/`):**
   - Contains **`509` sequence-verified linker records** ($5\text{--}60\text{ aa}$) across **four explicit authority tiers** plus **`40` `B3` specificity panel controls**, all screened against `CAID3` (`4c204ef4...`) and `DP94` (`fe64e7c6...`) under `RULE_V2` and annotated with frozen Seed-31 CNN scores and `linkerforge.properties` biophysical calls (`rigidity`, `cleavability`, `composition_features`).

---

## 2. Part 1 Validation Summary (`B1`, `B2`, `B3`)

| Validation Gate | Scope | Metric / Operating Point | Result | Status |
| :--- | :--- | :--- | :--- | :--- |
| **`B1` Family-Disjoint Split** | `97` proteins across `91` transitive `Pfam`/`Gene3D`/`UniRef50` + `RULE_V2` components | Cross-split & benchmark leakage (`CAID3`, `DP94`) | `0` shared components, `0` `RULE_V2` homolog hits (`0.000%` residue-shuffle null) | **Completed** (`d62136ce...`) |
| **`B2` Conformal Calibration (Ungated Residue Baseline)** | `28` `development` proteins (`547` pos, `518` neg known residues) | LTT / Clopper–Pearson 95% UCB $\text{FDR} \le 0.10$ | $\tau = 0.730042$: `185` TP, `12` FP, empirical FDR `6.09%`, 95%-UCB FDR `9.68%`, recall `33.82%` | **Completed** |
| **`B2` Conformal Calibration (Two-Stage Domain-Gated)** | `28` `development` proteins (`Stage 1` hetero-Pfam $5\text{--}60\text{ aa}$ gate + `Stage 2` Seed-31 CNN) | LTT / Clopper–Pearson 95% UCB $\text{FDR} \le 0.10$ | $\tau = 0.639120$: `93` TP, `1` FP, **empirical FDR `1.06%` (`98.94%` precision)**, **95%-UCB FDR `4.95%`** | **Completed** |
| **`B3` No-Linker Specificity Panel** | `40` benchmark-disjoint negative controls (`9` `auxiliary` order + `31` single/homo-domain non-linker) | Two-stage high-confidence span calls ($\tau_{\text{high}} = 0.735198$) | `0 / 31` (`100.0%` spec.) on single/homo-domain; `1 / 40` (`97.50%` protein spec.) overall | **Completed** |

---

## 3. Dataset Inventory (`mined_and_natural_linkers_v1`)

All records are stored under `data/processed/mined_and_natural_linkers_v1/`, validated against `schemas/mined_and_natural_linker_dataset_v1.schema.json`, and loaded via `src/linkerforge/dataset_v1.py` (`load_dataset_manifest`, `load_linker_records`).

| Authority Tier | File | Records ($5\text{--}60\text{ aa}$) | Evidence Grade & Role in Part 2 |
| :--- | :--- | ---: | :--- |
| **`natural_cath_pdb_verified`** | `natural_authorities.jsonl` / `all_records.jsonl` | `91` | **Ground-Truth 3D Natural Authority:** Coordinate-complete CATH v4.4.0 two-domain linkers ($5\text{--}30\text{ aa}$, `57` superfamily-pair clusters) with 3D attachment port $\text{C}\alpha$ distances (`inter_port_ca_distance_A`), `physical_3p8A_feasible` flags (`89 / 91` feasible at $3.8\,\text{\AA}/\text{res}$), port accessibility proxies, Seed-31 CNN scores, and biophysical calls. |
| **`natural_disprot_curated_dfl`** | `natural_authorities.jsonl` / `all_records.jsonl` | `57` | **Ground-Truth Sequence Natural Authority:** Curator-validated `DisProt_2026_06` `IDPO:0000033` flexible linker spans ($5\text{--}60\text{ aa}$; `8` additional spans $>60\text{ aa}$ documented in manifest) from the benchmark-disjoint `B1 V2` `train` and `development` splits, with $\pm 80\text{ aa}$ flanking context and flanking Pfam domain IDs. |
| **`mined_high_confidence_dfl_call`** | `mined_candidates.jsonl` / `all_records.jsonl` | `88` | **High-Confidence Mined Inter-Domain Spans:** Benchmark-disjoint hetero-Pfam (`left != right`) inter-domain gaps ($5\text{--}60\text{ aa}$) from proteins without curated `IDPO:0000033` labels that pass Stage 1 and achieve frozen Seed-31 CNN `mean >= 0.735198` (or `max >= 0.735198` with `mean >= 0.50`). Strictly segregated from ground-truth training labels. |
| **`mined_provisional_dfl_candidate`** | `mined_candidates.jsonl` / `all_records.jsonl` | `250` | **Provisional Mined Inter-Domain Spans:** Benchmark-disjoint hetero-Pfam gaps ($5\text{--}60\text{ aa}$) with frozen Seed-31 CNN `0.50 <= mean < 0.735198`. |
| **`literature_engineered_template`** | `template_authorities.jsonl` / `all_records.jsonl` | `23` | **Literature Template Authority:** Cited engineered flexible, rigid, and cleavable linker templates ($5\text{--}60\text{ aa}$) from Chen et al. (2013) *Adv. Drug Deliv. Rev.* 65:1357–1369. |
| **Total Linker Records** | `all_records.jsonl` | **`509`** | **`148` natural authorities + `338` domain-gated mined candidates + `23` literature templates** |
| **`b3_no_linker_specificity_panel`** | `b3_no_linker_specificity_panel.jsonl` | `40` | Benchmark-disjoint negative control panel (`9` experimental-order + `31` single/homo-domain proteins). |

### File Integrity Digests (`data/processed/mined_and_natural_linkers_v1/`)

- `manifest.json`: `009ea585050efe9c6af0b94b9224401a3cc026a6ddba9bb3c59e44c5bd078658`
- `all_records.jsonl` (`509` records): `ecf5e8d1108a205f2fe0fcf5205c4526f4c6b1ba37f4f6fccdf959d295cd3bd9`
- `natural_authorities.jsonl` (`148` records): `c4fd1280f25a58f0036b837ffd2bd0595869d934e0ff2446a835d6d2a409310e`
- `mined_candidates.jsonl` (`338` records): `ec125f92772dd2a50518288061522f0e86498f42889673f9b44e54c8c2e3a033`
- `template_authorities_jsonl` (`23` records): `c7af81e765e7b153bde5ed0f5f0f11767e9e860aad54ec5da78658302a6514ca`
- `b3_no_linker_specificity_panel.jsonl` (`40` records): `a55a516750a0b5055a8f624712cc331db66fbd979f19183359a8b94d544b5ee7`

---

## 4. Verification & Reproducibility Commands

```powershell
# 1. Run unit tests for Stage 1 domain gating, Stage 2 conformal mining, and dataset_v1 loader
python -m unittest tests/test_domain_gate.py tests/test_conformal_mining.py -v

# 2. Rebuild and verify the complete dataset and summary report
python scripts/build_mined_and_natural_linker_dataset.py
```
