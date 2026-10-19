# YOLO-style 1D segmenter: side-by-side exploratory result

This is an adaptation of the YOLOv5-seg pattern to a **one-dimensional amino-acid sequence**, not the Ultralytics image model and not its pretrained weights. It uses frozen ESM-2 35M residue embeddings, a multi-scale convolutional feature pyramid, per-position semantic and objectness scores, predicted left/right extents, prototype masks, and 1D overlap suppression. The implementation and trial contract are in `src/linkerforge/models/yolo1d_linker_segmenter.py` and `configs/yolo1d_dfl_round_2026-10-13.json`.

All three runs used the original published TR166 training and TE82 development masks, 510-residue windows, six epochs, batch size four, and the same masked-residue evaluation convention as the earlier CNN and SAM-like heads. `x` residues were never treated as negatives. The only supervised category was **disordered flexible linker (DFL)**. No image, structure, or functional-region label was fabricated. CAID3 and TE64 were not read by this trainer.

| Model | Seed | Best TE82 epoch | Masked-residue APS | AUROC | Recall at empirical precision >=0.90 | TP / FP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Existing CNN | 7 | previously selected | 0.450 | — | — | — |
| Existing span head | 7 | previously selected | 0.455 | — | — | — |
| YOLO-style 1D, padding-safe | 7 | 5 | 0.537 | 0.804 | 0.155 | 344 / 38 |
| YOLO-style 1D, padding-safe | 17 | 5 | 0.521 | 0.775 | 0.078 | 174 / 19 |
| YOLO-style 1D, padding-safe | 31 | 5 | 0.448 | 0.760 | 0.046 | 102 / 8 |
| SAM-like query head | 7 | 3 | 0.661 | 0.875 | 0.360 | 801 / 88 |
| SAM-like query head | 17 | 2 | 0.653 | 0.855 | 0.380 | 844 / 91 |
| SAM-like query head | 31 | 2 | 0.688 | 0.872 | 0.385 | 855 / 92 |

All entries use 13,694 scored TE82 residues (2,223 positives, 11,471 negatives). Padding-safe YOLO-style mean best-epoch APS is **0.502**, versus **0.667** for the SAM-like head. The YOLO-style model is therefore a negative architecture comparison relative to the query model in this development round; one of three seeds also failed to beat the older CNN. Its high-precision recall is especially unstable. Both new heads have development-selected epochs and different parameter counts/losses; this is not a controlled equal-capacity ablation or an independent generalization result. The earlier published CAID3 comparison remains far more demanding and cannot be numerically compared with these TE82 values.

An initial YOLO-style round without explicit padded-embedding zeroing scored APS 0.518/0.542/0.559 for seeds 7/17/31. Those runs remain archived in `artifacts/yolo1d-dfl-seed{7,17,31}-001/` with their original source hashes, but are **superseded** for model comparison because trailing padded ESM values could influence real sequence-boundary sites. The corrected implementation has a padding-invariance unit test; its separate runs are `artifacts/yolo1d-dfl-padmask-seed{7,17,31}-001/`. The shift in measured performance is another reason not to claim robustness from this small development split.

## Scope of "what part does what"

The architecture can allocate separate semantic channels to annotated region classes, but the current model has **one trained class**. It does **not** infer catalytic residues, binding sites, transmembrane segments, rigid linkers, cleavage sites, or biological function. Expanding to those categories requires an explicit ontology, source-specific residue/span coordinates, unknown-versus-negative semantics, and protein-family separation. Some properties overlap (for example, a linker may also be disordered), so a future dataset should be multi-label, not force mutually exclusive classes. Category-specific evaluation must be reported separately, with label provenance and coverage.

## Reproducibility and next decision

Each isolated run includes the six-epoch metric stream, best checkpoint, source/config/data hashes, model/version information, GPU, runtime, and failure status. Five YOLO-style unit tests pass. The current YOLO-style model is **not promoted**. Next optimization should target the demonstrated weakness (high-precision recall and late-epoch stability) on a new documented development round. No architecture may be called frontier-level until it survives a frozen, homology-audited independent comparison against obtainable current linker-detection baselines on common sequences, labels, and coverage.

Source design reference: [Ultralytics YOLOv5 segmentation tutorial](https://github.com/ultralytics/yolov5/blob/master/segment/tutorial.ipynb); [YOLOv5 segmentation usage and validation](https://github.com/ultralytics/yolov5#segmentation).
