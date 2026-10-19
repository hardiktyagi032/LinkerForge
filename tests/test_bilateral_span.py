"""CPU contract tests for the untrained bilateral interval module."""

import torch

from linkerforge.models.bilateral_span import BilateralSpanScorer, propose_intervals


def test_proposer_retains_forced_reference_only_when_explicit():
    starts = torch.zeros(60)
    ends = torch.zeros(60)
    starts[10] = 5
    ends[19] = 5
    ordinary = propose_intervals(starts, ends, min_length=8, max_length=30,
                                 top_boundaries=1, max_candidates=1)
    assert ordinary.tolist() == [[10, 20]]
    forced = propose_intervals(starts, ends, min_length=8, max_length=30,
                               top_boundaries=1, max_candidates=1,
                               forced_intervals=((30, 45),))
    assert forced.tolist() == [[10, 20], [30, 45]]


def test_bilateral_scorer_shapes_gradients_and_terminal_guard():
    torch.manual_seed(3)
    model = BilateralSpanScorer(embedding_dim=12, width=8, flank_width=10, min_flank=4)
    embeddings = torch.randn(48, 12)
    intervals = torch.tensor([[10, 20], [0, 12], [35, 45]])
    out = model(embeddings, intervals)
    assert out["interval_logits"].shape == (3,)
    assert out["eligible"].tolist() == [True, False, False]
    assert out["start_logits"].shape == (48,)
    assert out["end_logits"].shape == (48,)
    (out["interval_logits"][0] - out["null_logit"]).backward()
    assert model.project.weight.grad is not None


def test_empty_and_invalid_intervals():
    model = BilateralSpanScorer(embedding_dim=4, width=4)
    empty = model(torch.randn(20, 4), torch.empty((0, 2), dtype=torch.long))
    assert empty["interval_logits"].numel() == 0
    try:
        model(torch.randn(20, 4), torch.tensor([[10, 21]]))
    except ValueError:
        pass
    else:
        raise AssertionError("Out-of-range interval accepted")
