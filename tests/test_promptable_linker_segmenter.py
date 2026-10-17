"""Shape, partial-label, and abstention contracts for the untrained head."""
import unittest

import torch

from src.linkerforge.models.promptable_linker_segmenter import (
    PromptableLinkerSegmenter, decode_spans, segmenter_loss,
)


class PromptableSegmenterTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(7)
        self.model = PromptableLinkerSegmenter(embedding_dim=12, width=24, heads=4,
                                               layers=1, queries=3, dropout=0)
        self.model.eval()
        self.embeddings = torch.randn(2, 12, 12)
        self.mask = torch.tensor([[True] * 12, [True] * 8 + [False] * 4])
        self.concepts = torch.tensor([0, 0])

    def test_shapes_and_padding(self):
        output = self.model(self.embeddings, self.mask, self.concepts)
        self.assertEqual(tuple(output["presence_logits"].shape), (2,))
        self.assertEqual(tuple(output["semantic_logits"].shape), (2, 12))
        self.assertEqual(tuple(output["start_logits"].shape), (2, 3, 12))
        self.assertEqual(tuple(output["instance_mask_logits"].shape), (2, 3, 12))
        self.assertTrue((output["start_logits"][1, :, 8:] < -1000).all())

    def test_exemplar_prompt_changes_output_and_padding_is_forbidden(self):
        original = self.model(self.embeddings, self.mask, self.concepts)
        labels = torch.zeros(2, 12, dtype=torch.long)
        labels[0, 3:5] = 1
        labels[0, 1] = -1
        prompted = self.model(self.embeddings, self.mask, self.concepts,
                              exemplar_labels=labels)
        self.assertFalse(torch.allclose(original["presence_logits"],
                                        prompted["presence_logits"]))
        labels[1, 10] = 1
        with self.assertRaises(ValueError):
            self.model(self.embeddings, self.mask, self.concepts,
                       exemplar_labels=labels)

    def test_partial_labels_do_not_become_negatives(self):
        output = self.model(self.embeddings, self.mask, self.concepts)
        labels = torch.full((2, 12), -1, dtype=torch.long)
        labels[0, 3:6] = 1
        presence = torch.tensor([1, -1])
        exhaustive = torch.tensor([False, False])
        loss = segmenter_loss(output, self.mask, labels, presence,
                              [[(3, 6)], []], exhaustive)
        self.assertTrue(torch.isfinite(loss["total"]))
        loss["total"].backward()
        self.assertIsNotNone(self.model.query_embedding.grad)
        self.assertGreater(float(self.model.query_embedding.grad.abs().sum()), 0)

    def test_absence_requires_exhaustive_labels(self):
        output = self.model(self.embeddings, self.mask, self.concepts)
        labels = torch.full((2, 12), -1, dtype=torch.long)
        labels[0, :12] = 0
        with self.assertRaises(ValueError):
            segmenter_loss(output, self.mask, labels, torch.tensor([0, -1]),
                           [[], []], torch.tensor([False, False]))
        result = segmenter_loss(output, self.mask, labels, torch.tensor([0, -1]),
                                [[], []], torch.tensor([True, False]))
        self.assertTrue(torch.isfinite(result["total"]))

    def test_decoder_returns_one_based_spans_or_abstains(self):
        output = {"presence_logits": torch.tensor([8.0, -8.0]),
                  "semantic_logits": torch.zeros(2, 12),
                  "query_match_logits": torch.tensor([[8.0, -8.0], [8.0, 8.0]]),
                  "start_logits": torch.full((2, 2, 12), -8.0),
                  "end_logits": torch.full((2, 2, 12), -8.0)}
        output["start_logits"][0, 0, 3] = 8
        output["end_logits"][0, 0, 5] = 8
        result = decode_spans(output, ["A" * 12, "A" * 8], self.mask,
                              self.concepts, min_length=3)
        self.assertEqual((result[0]["spans"][0]["start_1based"],
                          result[0]["spans"][0]["end_1based"]), (4, 6))
        self.assertEqual(result[1]["status"], "abstained")


if __name__ == "__main__":
    unittest.main()
