"""Small deterministic checks for the focal-loss ablation."""

import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np
import torch
from torch.nn import functional as F


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "train_esm2_linker_detector.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("esm2_linker_training", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TestFocalLoss(unittest.TestCase):
    def test_gamma_zero_matches_existing_weighted_bce(self):
        logits = torch.tensor([-2.0, -0.2, 0.4, 2.0])
        targets = torch.tensor([0.0, 1.0, 0.0, 1.0])
        previous = F.binary_cross_entropy_with_logits(
            logits, targets, pos_weight=torch.tensor(6.0))
        current = MODULE.classification_loss(logits, targets, 6.0, 0.0)
        self.assertTrue(torch.allclose(previous, current))

    def test_focal_suppresses_easy_correct_examples(self):
        logits = torch.tensor([-5.0, 5.0], requires_grad=True)
        targets = torch.tensor([0.0, 1.0])
        baseline = MODULE.classification_loss(logits, targets, 6.0, 0.0)
        focal = MODULE.classification_loss(logits, targets, 6.0, 2.0)
        self.assertLess(float(focal.detach()), float(baseline.detach()))
        focal.backward()
        self.assertTrue(torch.isfinite(logits.grad).all())

    def test_negative_gamma_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.classification_loss(torch.tensor([0.0]),
                                       torch.tensor([1.0]), 6.0, -1.0)

    def test_additional_loss_variants_have_finite_gradients(self):
        targets = torch.tensor([0.0, 0.0, 1.0, 1.0])
        for name in ("asymmetric", "bce_tversky", "hard_negative"):
            logits = torch.tensor([-2.0, 0.5, -0.5, 2.0], requires_grad=True)
            loss = MODULE.classification_loss(logits, targets, 6.0, 2.0, name)
            loss.backward()
            self.assertTrue(torch.isfinite(loss))
            self.assertTrue(torch.isfinite(logits.grad).all())

    def test_high_precision_uses_complete_score_ties(self):
        truth = np.asarray([1, 0, 1, 0], dtype=np.uint8)
        scores = np.asarray([0.9, 0.9, 0.7, 0.1], dtype=np.float32)
        point = MODULE.high_precision_operating_point(truth, scores, 0.9, 1)
        self.assertIsNone(point["threshold"])
        self.assertEqual(point["true_positives"], 0)

    def test_hard_negative_mining_keeps_positive_gradient(self):
        logits = torch.full((100,), -1.0, requires_grad=True)
        targets = torch.zeros(100)
        targets[0] = 1.0
        loss = MODULE.classification_loss(logits, targets, 6.0, 0.0,
                                          "hard_negative")
        loss.backward()
        self.assertNotEqual(float(logits.grad[0]), 0.0)
        self.assertLessEqual(int(torch.count_nonzero(logits.grad)), 65)


if __name__ == "__main__":
    unittest.main()
