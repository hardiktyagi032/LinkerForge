import unittest

import torch

from linkerforge.models.yolo1d_linker_segmenter import (
    Yolo1DLinkerSegmenter, decode_yolo1d, yolo1d_loss)


class Yolo1DLinkerSegmenterTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(2)
        self.model = Yolo1DLinkerSegmenter(12, width=16, prototypes=4)
        self.embeddings = torch.randn(2, 12, 12)
        self.valid = torch.tensor([[True] * 12, [True] * 9 + [False] * 3])

    def test_shapes_and_padding(self):
        out = self.model(self.embeddings, self.valid)
        self.assertEqual(out["semantic_logits"].shape, (2, 12, 1))
        self.assertEqual(out["objectness_logits"].shape, (2, 12))
        self.assertEqual(out["extent_raw"].shape, (2, 12, 2))
        self.assertEqual(out["prototypes"].shape, (2, 4, 12))
        self.assertLess(float(out["semantic_logits"][1, 10, 0].detach()), -100)

    def test_masked_loss_has_gradients(self):
        out = self.model(self.embeddings, self.valid)
        labels = torch.tensor([[0, 0, 1, 1, 1, 1, 0, 0, -1, -1, 0, 0],
                               [0, 0, 0, 0, 0, 0, -1, -1, -1, -1, -1, -1]])
        loss = yolo1d_loss(out, self.valid, labels, [[(2, 6)], []])
        self.assertTrue(torch.isfinite(loss["total"]))
        loss["total"].backward()
        self.assertIsNotNone(self.model.stem.weight.grad)
        self.assertGreater(float(self.model.stem.weight.grad.abs().sum()), 0)

    def test_unknown_cannot_be_positive_span(self):
        out = self.model(self.embeddings, self.valid)
        labels = torch.full((2, 12), -1)
        with self.assertRaises(ValueError):
            yolo1d_loss(out, self.valid, labels, [[(2, 6)], []])

    def test_padding_values_do_not_change_real_scores(self):
        self.model.eval()
        changed = self.embeddings.clone()
        changed[1, 9:] = 1000
        original = self.model(self.embeddings, self.valid)["semantic_logits"][1, :9]
        modified = self.model(changed, self.valid)["semantic_logits"][1, :9]
        self.assertTrue(torch.allclose(original, modified, atol=1e-6))

    def test_decoder(self):
        out = self.model(self.embeddings, self.valid)
        out["semantic_logits"].fill_(-10)
        out["objectness_logits"].fill_(-10)
        out["semantic_logits"][0, 5, 0] = 10
        out["objectness_logits"][0, 5] = 10
        out["extent_raw"][0, 5] = torch.tensor([3.0, 3.0])
        result = decode_yolo1d(out, ["ACDEFGHIKLMN", "ACDEFGHIK"], self.valid)
        self.assertEqual(result[0]["status"], "proposed_spans")
        self.assertEqual(result[1]["status"], "abstained")
        span = result[0]["spans"][0]
        self.assertEqual(span["sequence"], "EFGHI")
        self.assertEqual(span["end_1based"] - span["start_1based"] + 1, span["length"])


if __name__ == "__main__":
    unittest.main()
