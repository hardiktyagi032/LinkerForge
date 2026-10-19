"""CPU smoke and fail-closed tests; runnable without pytest."""

import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from linkerforge.models.competitor_gap_segmenter import CompetitorGapSegmenter


def run():
    embedding = torch.randn(2, 11, 16)
    valid = torch.tensor([[1] * 11, [1] * 7 + [0] * 4], dtype=torch.bool)
    concept = torch.zeros(2, dtype=torch.long)
    for variant in ("global_context", "dilated_local", "predicted_disorder_gate"):
        model = CompetitorGapSegmenter(16, variant).eval()
        output = model(embedding, valid, concept)
        assert output["semantic_logits"].shape == (2, 11)
        assert torch.isfinite(output["semantic_logits"]).all()
        if variant == "predicted_disorder_gate":
            model.stage = "auxiliary_idr"
            aux = model(embedding, valid, concept)
            assert torch.equal(aux["semantic_logits"], aux["predicted_disorder_logits"])
    for variant, keyword in (("external_representation", {"external_dim": 3}),
                             ("function_interaction", {"function_count": 3})):
        model = CompetitorGapSegmenter(16, variant, **keyword).eval()
        try:
            model(embedding, valid, concept)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{variant} did not refuse missing inputs")
    print("five feature modes: three forward passes and two missing-input refusals passed")


if __name__ == "__main__":
    run()
