# LinkerForge Current Citation List

**Scope:** This is the deduplicated bibliography for the current **LinkerForge** project: a general, structure-conditioned workflow for ranking and computationally validating peptide linkers for a supplied pair of protein domains. `sfGFP—linker—mCherry` is only the final worked example; it is not the core project, the training target, or the intended limit of the method.

**Not included:** Literature collected for the earlier ProtCompose/unrestricted whole-protein-generation concept (for example, text-to-protein generation, general de novo protein diffusion, catalytic-motif scaffolding, protein “splicing,” and universal function-conditioned protein generation) is intentionally excluded unless the source is directly used by the present LinkerForge methodology.

The list contains **23 current-project sources**. References 1–20 support the general research problem, dataset, model, and validation workflow. Reference 21 documents the implemented Mol* viewer. References 22–23 document only the two proteins/PDB structures selected for the final example and should not be presented as the basis of the general model.

## A. Research problem, linker biology, and existing linker-design work

1. **Chen, X., Zaro, J. L., & Shen, W.-C. (2013).** Fusion protein linkers: Property, design and functionality. *Advanced Drug Delivery Reviews, 65*(10), 1357–1369. [DOI](https://doi.org/10.1016/j.addr.2012.09.039) · [Open access](https://pmc.ncbi.nlm.nih.gov/articles/PMC3726540/)  
   **Used for:** linker classes, linker length/composition effects, flexible GS-rich linkers, and the empirical/context-dependent nature of fusion-linker selection.

2. **George, R. A., & Heringa, J. (2002).** An analysis of protein domain linkers: Their classification and role in protein folding. *Protein Engineering, 15*(11), 871–879. [DOI](https://doi.org/10.1093/protein/15.11.871)  
   **Used for:** natural interdomain-linker analysis, linker classification, and the rationale for learning from naturally occurring multidomain proteins.

3. **Liu, C., Chin, J. X., & Lee, D.-Y. (2015).** SynLinker: An integrated system for designing linkers and synthetic fusion proteins. *Bioinformatics, 31*(22), 3700–3702. [DOI](https://doi.org/10.1093/bioinformatics/btv447)  
   **Used for:** prior linker-retrieval/design systems and the limitation of largely database/rule-oriented linker selection.

4. **Nagamune, T. (2017).** Biomolecular engineering for nanobio/bionanotechnology. *Nano Convergence, 4*, 9. [DOI](https://doi.org/10.1186/s40580-017-0103-4) · [Open access](https://pmc.ncbi.nlm.nih.gov/articles/PMC5404043/)  
   **Used for:** broader biomolecular-engineering context, including domain fusion and engineered multifunctional biomolecules.

5. **Kumar, H., & Kim, P. (2024).** Artificial intelligence in fusion protein three-dimensional structure prediction: Review and perspective. *Clinical and Translational Medicine, 14*(8), e1789. [DOI](https://doi.org/10.1002/ctm2.1789) · [Open access](https://pmc.ncbi.nlm.nih.gov/articles/PMC11294035/)  
   **Used for:** the difficulty of predicting novel fusion-protein structures, limited fusion-specific experimental data, conformational uncertainty, and the need for careful validation.

6. **Wuyun, Q., Chen, Y., Shen, Y., et al. (2024).** Recent progress of protein tertiary structure prediction. *Molecules, 29*(4), 832. [DOI](https://doi.org/10.3390/molecules29040832) · [Open access](https://pmc.ncbi.nlm.nih.gov/articles/PMC10893003/)  
   **Used for:** current structure-prediction capabilities and remaining challenges for multidomain proteins and relative domain orientation.

7. **Vymětal, J., Mertová, K., Boušová, K., Šulc, J., Tripsianes, K., & Vondrášek, J. (2022).** Fusion of two unrelated protein domains in a chimera protein and its 3D prediction: Justification of the X-ray reference structures as a prediction benchmark. *Proteins: Structure, Function, and Bioinformatics, 90*(12), 2067–2079. [DOI](https://doi.org/10.1002/prot.26398) · [Open access](https://pmc.ncbi.nlm.nih.gov/articles/PMC9796088/)  
   **Used for:** fusion-protein structural benchmarking and evidence that modelling domains separately does not resolve the complete-fusion/domain-orientation problem.

## B. Learning architecture and structural-prediction methods

8. **Lin, Z., Akin, H., Rao, R., et al. (2023).** Evolutionary-scale prediction of atomic-level protein structure with a language model. *Science, 379*(6637), 1123–1130. [DOI](https://doi.org/10.1126/science.ade2574)  
   **Used for:** the ESM protein-language-model family; LinkerForge proposes frozen ESM-2 sequence embeddings rather than training a protein language model from scratch.

9. **Jing, B., Eismann, S., Suriana, P., Townshend, R. J. L., & Dror, R. O. (2021).** Learning from protein structure with geometric vector perceptrons. *International Conference on Learning Representations*. [OpenReview](https://openreview.net/forum?id=1YLJDvSx6J4)  
   **Used for:** rotation-aware geometric graph encoding around the two attachment points.

10. **Jumper, J., Evans, R., Pritzel, A., et al. (2021).** Highly accurate protein structure prediction with AlphaFold. *Nature, 596*, 583–589. [DOI](https://doi.org/10.1038/s41586-021-03819-2)  
    **Used for:** complete-fusion structure prediction and interpretation of confidence outputs; not treated as experimental validation.

11. **Mirdita, M., Schütze, K., Moriwaki, Y., et al. (2022).** ColabFold: Making protein folding accessible to all. *Nature Methods, 19*, 679–682. [DOI](https://doi.org/10.1038/s41592-022-01488-1)  
    **Used for:** the practical AlphaFold/ColabFold stage in the proposed structural-validation funnel.

12. **Steinegger, M., & Söding, J. (2017).** MMseqs2 enables sensitive protein sequence searching for the analysis of massive data sets. *Nature Biotechnology, 35*, 1026–1028. [DOI](https://doi.org/10.1038/nbt.3988)  
    **Used for:** sequence clustering, deduplication, and homology-aware train/validation/blind splitting.

13. **Stein, A., & Kortemme, T. (2013).** Improvements to robotics-inspired conformational sampling in Rosetta. *PLoS ONE, 8*(5), e63090. [DOI](https://doi.org/10.1371/journal.pone.0063090) · [Open access](https://pmc.ncbi.nlm.nih.gov/articles/PMC3646924/)  
    **Used for:** Rosetta loop/linker conformational sampling and chain-closure testing.

14. **Eastman, P., Galvelis, R., Peláez, R. P., et al. (2024).** OpenMM 8: Molecular dynamics simulation with machine learning potentials. *The Journal of Physical Chemistry B, 128*(1), 109–116. [DOI](https://doi.org/10.1021/acs.jpcb.3c06662)  
    **Used for:** energy minimisation and optional lightweight molecular-dynamics evaluation of only the final shortlisted candidates.

## C. Data sources, annotations, and provenance

15. **Burley, S. K., Bhikadiya, C., Bi, C., et al. (2022).** RCSB Protein Data Bank: Celebrating 50 years of the PDB with new tools for understanding and visualizing biological macromolecules in 3D. *Protein Science, 31*(1), 187–208. [DOI](https://doi.org/10.1002/pro.4213)  
    **Used for:** experimentally determined structures, chains, coordinate completeness, and experimental metadata.

16. **Dana, J. M., Gutmanas, A., Tyagi, N., et al. (2019).** SIFTS: Updated Structure Integration with Function, Taxonomy and Sequences resource allows 40-fold increase in coverage of structure-based annotations for proteins. *Nucleic Acids Research, 47*(D1), D482–D489. [DOI](https://doi.org/10.1093/nar/gky1114)  
    **Used for:** residue-level reconciliation of PDB coordinates with UniProt and domain annotations.

17. **The UniProt Consortium. (2025).** UniProt: The Universal Protein Knowledgebase in 2025. *Nucleic Acids Research, 53*(D1), D609–D617. [DOI](https://doi.org/10.1093/nar/gkae1010)  
    **Used for:** canonical sequences, protein identifiers, and curated protein annotations.

18. **Waman, V. P., Bordin, N., Lau, A., et al. (2025).** CATH v4.4: Major expansion of CATH by experimental and predicted structural data. *Nucleic Acids Research, 53*(D1), D348–D355. [DOI](https://doi.org/10.1093/nar/gkae1087)  
    **Used for:** structural-domain boundaries, families, and family-aware dataset splitting.

19. **Blum, M., Andreeva, A., Florentino, L. C., et al. (2025).** InterPro: The protein sequence classification resource in 2025. *Nucleic Acids Research, 53*(D1), D444–D456. [DOI](https://doi.org/10.1093/nar/gkae1082)  
    **Used for:** integrated protein-family and domain annotations, including Pfam-linked evidence.

20. **Varadi, M., Anyango, S., Deshpande, M., et al. (2022).** AlphaFold Protein Structure Database: Massively expanding the structural coverage of protein-sequence space with high-accuracy models. *Nucleic Acids Research, 50*(D1), D439–D444. [DOI](https://doi.org/10.1093/nar/gkab1061)  
    **Used for:** a separately labelled predicted-structure supplement; predicted records must not be mixed silently with experimental PDB records.

## D. Implemented viewer and final example only

21. **Sehnal, D., Bittrich, S., Deshpande, M., et al. (2021).** Mol* Viewer: Modern web app for 3D visualization and analysis of large biomolecular structures. *Nucleic Acids Research, 49*(W1), W431–W437. [DOI](https://doi.org/10.1093/nar/gkab314)  
    **Used for:** the implemented browser-native 3D structure viewer. Mol* is a visualization component, not a simulation or prediction engine.

22. **Pédelacq, J.-D., Cabantous, S., Tran, T., Terwilliger, T. C., & Waldo, G. S. (2006).** Engineering and characterization of a superfolder green fluorescent protein. *Nature Biotechnology, 24*(1), 79–88. [DOI](https://doi.org/10.1038/nbt1172) · [PDB 2B3P](https://www.rcsb.org/structure/2B3P)  
    **Used for:** the sfGFP domain and experimental reference structure in the final worked example only; not a core-model or training-data citation.

23. **Shu, X., Shaner, N. C., Yarbrough, C. A., Tsien, R. Y., & Remington, S. J. (2006).** Novel chromophores and buried charges control color in mFruits. *Biochemistry, 45*(32), 9639–9647. [DOI](https://doi.org/10.1021/bi060773l) · [PDB 2H5Q](https://www.rcsb.org/structure/2H5Q)  
    **Used for:** the mCherry domain and experimental reference structure in the final worked example only; not a core-model or training-data citation.

## Citation-use rules for the project

1. Cite the exact database release/publication actually used in the final dataset, and record its access date.
2. Cite software methods only when that software or model is actually run; record the version, model weights, parameters, and licence in the reproducibility supplement.
3. Cite PDB entries individually for every experimental structure used in a figure, benchmark, or demonstration.
4. Keep experimental PDB structures and predicted AlphaFold DB structures in distinct evidence tiers.
5. Do not use AlphaFold/ColabFold, Rosetta, OpenMM, PyMOL, or Mol* output as evidence of experimental success.
6. Update this list when a planned component is replaced; do not retain a method citation merely because it appeared in an earlier project plan.

## Explicitly excluded earlier-project literature

The following literature groups belong to the previous ProtCompose/general-protein-generation direction and are not part of the present LinkerForge bibliography unless the LinkerForge scope is formally changed:

- text-description-to-protein generation;
- unrestricted whole-protein or semantic protein generation;
- RFdiffusion, Chroma, and other de novo protein diffusion systems;
- catalytic-motif or enzyme-scaffold generation;
- general modular “Frankenstein” protein assembly and novel genome encoding;
- environment-conditioned binder generation;
- universal mixture-of-experts model-family generation.

This exclusion does **not** mean those papers are scientifically unimportant. It means they do not support the frozen LinkerForge MVP and should not blur its narrower research question.
