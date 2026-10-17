# DLD detector transfer to CAID3 DFL — exploratory negative result

The official CAID3 Linker reference was downloaded from
<https://caid.idpcentral.org/assets/sections/challenge/static/references/3/linker.fasta>
(SHA-256 `4c204ef49ffa12fe166883e6b2cff0012cabee21260b8f32f997081d0e2fa0f8`).
The existing frozen ESM-2 35M/DLD residue-head checkpoint
(`artifacts/esm2-35m-linker-run-001/best.pt`, SHA-256
`1dac5c4097eb96acdc6de237bae28af7e1f067cfd72857898fc208a551331ec0`)
produced residue scores for all 31 proteins. The first inference attempt
finished scoring but failed while writing its manifest because a relative
output path was compared against an absolute repository root; the path
handling was fixed and an isolated second inference completed. Both attempts
and their logs are retained under ignored `artifacts/caid3-dld-transfer-00{1,2}`.

The official [CAID evaluator](https://github.com/BioComputingUP/CAID) at
commit `7bab7e8880d7f949e480fdb377c5a5c8546ae336` completed on the second
score file. Its full-reference output reports **APS 0.164**, AUC-ROC 0.756,
Fmax 0.266 (threshold 0.077), for 31 proteins and 1,379 positive residues.
Direct unrounded scikit-learn calculations gave APS 0.164435 and AUC-ROC
0.757940; the official implementation rounds scores to its own thresholds,
so use the official numbers for CAID-format reporting. Excluding the three
targets flagged by the preliminary DLD sequence-overlap screen gives a
*non-official* 28-protein subset APS 0.157070 and AUC-ROC 0.743901; that
subset is still not certified independent.

This is **not** a clean leaderboard comparison or evidence of a new model.
DLD IDL/DDL and CAID3 DisProt DFL are different labels. The initial audit
flags DP04066 and DP04255 against DLD training and DP04392 against DLD
validation; a top-5 k-mer/local screen can miss further homology. Every one
of the 31 CAID3 proteins is also present in the local DisProt 2026_06
extract, so that entire extract cannot be training data for a CAID3 test.
CAID3 has no no-linker proteins, so no-linker specificity is not measurable.
The official evaluator output and full per-residue predictions are in ignored
`artifacts/caid3-official-eval-001/` and `artifacts/caid3-dld-transfer-002/`;
the scored JSON manifest records hashes, code revision, and versions.

Conclusion: direct reuse of the existing DLD model is a poor DFL-transfer
baseline and not a plausible frontier claim. The next eligible research work
is a separately sourced DFL training/development set with verified negatives,
CAID3 overlap removal, matched published baselines, and a predeclared
span-aware trial. Do not tune on CAID3 merely because its labels are public.
