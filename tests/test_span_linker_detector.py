"""CPU-only contract tests for the bounded span-aware detector trial."""

import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from train_span_linker_detector import SpanHead, boundary_targets, span_loss


def test_boundaries_and_padding():
    targets = torch.tensor([[0, 1, 1, 0, 1, 0], [1, 1, 0, 0, 0, 0]], dtype=torch.float32)
    mask = torch.tensor([[1, 1, 1, 1, 1, 1], [1, 1, 1, 0, 0, 0]], dtype=torch.bool)
    observed = boundary_targets(targets, mask).int().tolist()
    assert observed[0] == [[0, 0], [1, 0], [0, 1], [0, 0], [1, 1], [0, 0]]
    assert observed[1] == [[1, 0], [0, 1], [0, 0], [0, 0], [0, 0], [0, 0]]


def test_span_head_loss_backpropagates():
    head = SpanHead(8, width=4)
    residue, boundary = head(torch.randn(2, 6, 8))
    assert residue.shape == (2, 6)
    assert boundary.shape == (2, 6, 2)
    targets = torch.tensor([[0, 1, 1, 0, 0, 0], [0, 0, 0, 0, 0, 0]], dtype=torch.float32)
    mask = torch.tensor([[1, 1, 1, 1, 1, 1], [1, 1, 1, 0, 0, 0]], dtype=torch.bool)
    loss = span_loss(residue, boundary, targets, mask, 6.0, 0.25)
    assert torch.isfinite(loss)
    loss.backward()
    assert any(parameter.grad is not None for parameter in head.parameters())
