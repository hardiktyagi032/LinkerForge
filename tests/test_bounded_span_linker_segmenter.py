import torch

from linkerforge.models.bounded_span_linker_segmenter import (
    BoundedSpanLinkerSegmenter, bounded_span_loss,
)
from linkerforge.models.coupled_bounded_span_segmenter import CoupledBoundedSpanSegmenter
from linkerforge.models.global_context_span_segmenter import GlobalContextSpanSegmenter


def test_bounded_span_shapes_and_backward():
    model = BoundedSpanLinkerSegmenter(8, width=12, max_span=4)
    embeddings = torch.randn(2, 7, 8)
    valid = torch.tensor([[True] * 7, [True] * 5 + [False] * 2])
    labels = torch.tensor([[0, 0, 1, 1, 0, -1, -1], [0, 0, 0, 0, 0, -1, -1]])
    output = model(embeddings, valid)
    assert output["semantic_logits"].shape == (2, 7)
    assert [value.shape for value in output["span_logits"]] == [(2, 7), (2, 6), (2, 5), (2, 4)]
    loss = bounded_span_loss(output, valid, labels, [[(2, 4)], []])
    assert torch.isfinite(loss)
    loss.backward()
    assert model.span_score[0].weight.grad is not None


def test_unknown_regions_are_not_span_negatives():
    model = BoundedSpanLinkerSegmenter(4, width=8, max_span=3)
    valid = torch.ones((1, 5), dtype=torch.bool)
    output = model(torch.randn(1, 5, 4), valid)
    loss = bounded_span_loss(output, valid, torch.tensor([[1, 1, -1, -1, -1]]), [[(0, 2)]])
    assert torch.isfinite(loss)


def test_all_unknown_window_has_zero_differentiable_loss():
    model = BoundedSpanLinkerSegmenter(4, width=8, max_span=3)
    valid = torch.ones((1, 5), dtype=torch.bool)
    output = model(torch.randn(1, 5, 4), valid)
    loss = bounded_span_loss(output, valid, torch.full((1, 5), -1), [[]])
    assert loss.item() == 0
    loss.backward()
    assert model.semantic.weight.grad is not None


def test_coupled_span_scores_reach_residue_predictions():
    model = CoupledBoundedSpanSegmenter(4, width=8, max_span=3)
    embeddings = torch.randn(1, 5, 4)
    valid = torch.ones((1, 5), dtype=torch.bool)
    output = model(embeddings, valid)
    assert output["semantic_logits"].shape == (1, 5)
    output["semantic_logits"].sum().backward()
    assert model.span_score[0].weight.grad is not None
    assert model.span_score[0].weight.grad.abs().sum() > 0


def test_global_context_span_mask_and_gradients():
    model = GlobalContextSpanSegmenter(8, width=16, max_span=5, layers=1)
    embeddings = torch.randn(2, 9, 8)
    valid = torch.tensor([[True] * 9, [True] * 6 + [False] * 3])
    output = model(embeddings, valid)
    assert output["semantic_logits"].shape == (2, 9)
    assert (output["semantic_logits"][1, 6:] == -1e4).all()
    output["semantic_logits"][valid].sum().backward()
    assert model.global_encoder.layers[0].self_attn.in_proj_weight.grad is not None
    assert model.interval_head.span_score[0].weight.grad is not None
