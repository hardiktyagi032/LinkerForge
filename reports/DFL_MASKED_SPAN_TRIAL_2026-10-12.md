# DFL span-head trial — development-only result

The second bounded trial completed on the published TransDFL TR166 training / TE82 development contract, with `x` residues masked. It used the same frozen ESM2-35M encoder, seed 7 and six epochs as the matched CNN residue baseline, adding start/end heads and a complete-interval objective. Both checkpoint selection and thresholds used TE82, so this is **not** an independent-test or state-of-the-art result. TE64 and CAID3 were not used for selection.

| TE82 metric | Matched CNN | Span head | Interpretation |
| --- | ---: | ---: | --- |
| Masked residue APS at best epoch | 0.4501 | 0.4549 | +0.0047 absolute; marginal, one seed |
| Masked residue AUROC | 0.7734 | 0.7488 | Worse |
| Recall at empirical precision >=0.90, >=50 TP | No eligible point | 195/2,223 = 8.77% at 90.70% precision | Better on this dev criterion, but low recall |
| Region recall, IoU >=0.5, at per-model dev F1 threshold | 29/46 = 63.0% | 26/46 = 56.5% | Worse |
| Region precision, same thresholding rule | 29/139 = 20.9% | 26/144 = 18.1% | Worse |
| No-positive scored-residue specificity, same thresholding rule | 19/44 = 43.2% | 24/44 = 54.5% | Better, but not the high-precision guardrail |

At the span model's high-precision point there were 195 true-positive and 20 false-positive residues. The subsequent region audit found no scored-residue prediction on 40/44 no-positive proteins (90.9% specificity), but only 4/46 true linker regions matched at IoU >=0.5 (8.7% region recall), with 4/27 region precision (14.8%). The CNN has no eligible >=90% precision point with >=50 true-positive residues, so there is no matched CNN specificity value at that operating-point rule. The high-precision point was selected and measured on the same development split; it may not transfer. The interval recovery loss despite the boundary objective argues against treating the result as a validated span-detection improvement.

Provenance: training data SHA-256 `8fbfa1a503857131b8e485f511f5c84d9fbea24b9d5bbac2aa003508cb4f716c`; TE82 SHA-256 `f15ac3eef1edc45b95bc600d661dab348a0cb0bee11e47febeac356ef93db916`; config SHA-256 `4da3727a6d93ef252695f47b8de3631d1174a1e76126030f3f719b8b00c4d485`; source SHA-256 `72cd712e3dad2682a4a6ed1956711e67f67eba788fd22ebdaf0029b49aaeb6ae`; checkpoint SHA-256 `40c148b7eef61e820c203345f2cc5ffb03521f1fb4fb2efa512881e6c816d1d9`; pipeline commit `4519cab377c531e0dc3131a8136654b2a98844c3`. Training took 112.406 seconds and peak PyTorch GPU allocation was 242,933,760 bytes. See `artifacts/dfl-span-seed7-001/manifest.json`, `artifacts/dfl-span-seed7-001/epochs.jsonl`, and `reports/dfl_span_te82_region_audit_2026-10-12.json`.

The trial is currently classified **mixed/inconclusive**, not promoted. The data remain retrospectively published, CAID3 independence is not established, and this head alone is not a defensible breakthrough claim. A protein-level diagnostic found the 195 high-confidence true-positive residues across 18 proteins; 105/195 (53.8%) came from the top five. The 4/46 recovered regions remain the more important limitation for the intended start/end output. Several top protein IDs are numerically adjacent, which is not evidence of homology by itself; a family-level audit is needed before interpreting their apparent breadth.
