# Exact-sequence annotated-linker count and 50,000 extension gate

Date: 12 October 2026. The user clarified that an annotated linker observed or inferred in a real protein is eligible; an individual wet-lab linker-function assay is **not** required. This supersedes the stricter inclusion criterion in `EXPERIMENTALLY_TESTED_LINKER_SOURCE_SEARCH_2026-10-12.md` for the **annotation catalog only**. Functional assay evidence remains a separate tier.

## Reproduced 10,000 threshold

Run `python scripts/audit_annotated_linker_10k.py`. The script reads the existing local exact-sequence catalog and streams the clean NRPS inter-modular-linker CSV from a pinned source commit; it does not save a copy of that CSV.

| Source | Exact unique standard-amino-acid strings | Evidence |
|---|---:|---|
| Current LinkerForge DLD/DisProt/CAID3 annotation index | 2,621 | Mixed structural, curated-disorder, and protected benchmark annotations; not independent function tests. |
| Farag et al. NRPS inter-modular-linker clean genomic file | 8,133 | Parser-extracted inter-modular linker annotations from genomic NRPS clusters. 17,445 CSV rows; 17,435 have standard amino acids plus cluster/assembly accessions. |
| Exact intersection | 0 | Case-normalized exact amino-acid string match. |
| **Exact union** | **10,754** | Numerical 10,000 annotation-index target met. |

Input identities: LinkerForge catalog SHA-256 `20490e189c36a6405169a6eb21142d8c6d873be44d5ed4cee84ac3bf547db2c4`; NRPS clean CSV SHA-256 `31bd21eca1764c04ed25ebc668aad44856d15bd4053fa83f14c3487bb085e210`; source Git commit `199d3284f76a2a8aa2fc0c5205b9240571ea8115`. The NRPS paper is [Farag et al., *Bioinformatics* 2019](https://doi.org/10.1093/bioinformatics/btz127), and its [source repository](https://github.com/SWFarag/nrps-linker) exposes the row-level CSV.

## What this number does and does not mean

The count is of unique strings in a **mixed discovery index**, not 10,754 functionally validated fusion linkers, not 10,754 independent proteins, and not a train-ready detector dataset. The new 8,133 sequences are NRPS *inter-modular* linkers, a specialized class. Many originate from putative biosynthetic clusters, and their boundaries were computationally parsed. CAID3 sequences in the existing index are protected benchmark examples; they must not be moved into training. Exact deduplication does not remove homologous biological examples or fix domain/linker ontology differences. Source-specific coordinates, provenance, license, homology and benchmark-overlap audits remain mandatory before any training use.

## 50,000 target

The clean NRPS file alone cannot provide the additional 39,246 exact strings. A read-only check of the same repository's `NCBI_webapp_not_clean2.csv` found 38,902 rows and 17,192 exact unique standard-amino-acid strings; even **replacing** the clean file with that looser file yields only 19,813 unique strings after union with the existing catalog. Do not add clean and not-clean counts: they are versions of the same source, and the latter's quality needs review. A scalable next source is [InterPro's UniProtKB domain-match export/API](https://www.ebi.ac.uk/training/online/courses/interpro-quick-tour/getting-data-from-interpro/), paired with the corresponding protein sequences. However, an interval between two InterPro hits is only a **candidate linker**, not an annotated linker by default. Before counting any such interval, freeze a boundary policy (adjacent non-overlapping domain matches, same protein chain, confidence/coverage constraints, gap-length bounds, exclusion of nested/repeat/terminal cases), manually audit a stratified sample, and retain `inferred_interdomain_candidate` as its own evidence tier. Until those gates and an exact row-level deduplicated count exist, **50,000 has not been reached**.
