"""Tests for the fail-closed PU (uPU/nnPU) residue loss.

Numpy reference tests always run; torch-parity tests skip when torch is absent.
"""

import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from linkerforge.models.pu_loss import PUConfig, pu_risk_numpy  # noqa: E402

try:
    import torch
    from linkerforge.models.pu_loss import pu_semantic_loss
except ImportError:  # pragma: no cover - environment without torch
    torch = None

GOOD = {"mode": "nnpu", "class_prior": 0.2, "beta": 0.0, "gamma": 1.0, "on_empty_class": "raise"}
ENC = {"x": -1, "0": 0, "1": 1}


def encode(labels):
    return np.array([ENC[c] for c in labels])


class TestConfig(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(PUConfig.from_dict(GOOD).class_prior, 0.2)

    def test_prior_required_no_default(self):
        bad = {k: v for k, v in GOOD.items() if k != "class_prior"}
        with self.assertRaises(ValueError):
            PUConfig.from_dict(bad)

    def test_rejects_bad_values(self):
        for key, value in [("class_prior", None), ("class_prior", 0.0), ("class_prior", 1.0),
                           ("class_prior", True), ("class_prior", float("nan")),
                           ("class_prior", "0.2"), ("mode", "bce"), ("beta", -0.1),
                           ("gamma", 0.0), ("gamma", 1.5), ("on_empty_class", "ignore")]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                PUConfig.from_dict({**GOOD, key: value})

    def test_rejects_unknown_key(self):
        with self.assertRaises(ValueError):
            PUConfig.from_dict({**GOOD, "pos_weight": 3})

    def test_shipped_config_fails_closed_until_prior_is_set(self):
        config = json.loads((ROOT / "configs/dfl_pu_loss_2026-10-17.json").read_text())
        self.assertIsNone(config["pu"]["class_prior"])
        with self.assertRaises(ValueError):
            PUConfig.from_dict(config["pu"])
        self.assertEqual(config["seeds"], [7, 17, 31])


class TestRisk(unittest.TestCase):
    cfg = PUConfig.from_dict(GOOD)

    def test_unknown_x_is_masked_not_negative(self):
        labels, logits = "1100xxxx", np.array([2.0, 1.0, -1.0, -2.0, 9.0, -9.0, 5.0, 0.0])
        valid = np.ones(8, bool)
        full = pu_risk_numpy(logits, encode(labels), valid, self.cfg)
        self.assertEqual((full["n_pos"], full["n_unlabeled"]), (2, 2))
        altered = logits.copy()
        altered[4:] = [-50.0, 50.0, -3.0, 3.0]  # change only x positions
        again = pu_risk_numpy(altered, encode(labels), valid, self.cfg)
        self.assertEqual(full["objective"], again["objective"])
        # x must differ from '0': relabeling x as 0 changes the unlabeled count.
        as_zero = pu_risk_numpy(logits, encode(labels.replace("x", "0")), valid, self.cfg)
        self.assertEqual(as_zero["n_unlabeled"], 6)

    def test_padding_ignored_and_must_be_unknown(self):
        logits = np.array([[1.0, -1.0, 7.0]])
        residue = np.array([[1, 0, -1]])
        a = pu_risk_numpy(logits, residue, np.array([[True, True, False]]), self.cfg)
        b = pu_risk_numpy(logits[:, :2], residue[:, :2], np.array([[True, True]]), self.cfg)
        self.assertAlmostEqual(a["objective"], b["objective"])
        with self.assertRaises(ValueError):
            pu_risk_numpy(logits, np.array([[1, 0, 0]]), np.array([[True, True, False]]), self.cfg)

    def test_invalid_targets_rejected(self):
        with self.assertRaises(ValueError):
            pu_risk_numpy([0.0, 0.0], np.array([2, 0]), np.ones(2, bool), self.cfg)

    def test_known_value_upu(self):
        cfg = PUConfig.from_dict({**GOOD, "mode": "upu", "class_prior": 0.5})
        out = pu_risk_numpy([0.0, 0.0], np.array([1, 0]), np.ones(2, bool), cfg)
        ln2 = np.log(2.0)
        # pi*Rp+ + (Ru- - pi*Rp-) = .5*ln2 + ln2 - .5*ln2
        self.assertAlmostEqual(out["risk"], ln2)
        self.assertAlmostEqual(out["objective"], ln2)

    def test_nnpu_clamps_negative_risk_upu_does_not(self):
        # Unlabeled confidently negative, positives confidently positive, large prior
        # drives the negative-class risk estimate below zero.
        logits = np.array([-8.0, 8.0, 8.0, 8.0])
        residue, valid = np.array([0, 1, 1, 1]), np.ones(4, bool)
        up = pu_risk_numpy(logits, residue, valid,
                           PUConfig.from_dict({**GOOD, "mode": "upu", "class_prior": 0.9}))
        nn = pu_risk_numpy(logits, residue, valid,
                           PUConfig.from_dict({**GOOD, "mode": "nnpu", "class_prior": 0.9}))
        self.assertLess(nn["neg_risk"], 0)
        self.assertTrue(nn["clamped"])
        self.assertFalse(up["clamped"])
        self.assertAlmostEqual(nn["objective"], -nn["neg_risk"])  # gamma = 1
        self.assertAlmostEqual(up["risk"], nn["risk"])

    def test_empty_class_policy(self):
        residue, logits, valid = np.array([0, 0, -1]), np.zeros(3), np.ones(3, bool)
        with self.assertRaises(ValueError):
            pu_risk_numpy(logits, residue, valid, self.cfg)
        skipped = pu_risk_numpy(logits, residue, valid,
                                PUConfig.from_dict({**GOOD, "on_empty_class": "skip"}))
        self.assertTrue(skipped["skipped"])
        self.assertEqual(skipped["objective"], 0.0)

    def test_prior_changes_value(self):
        args = (np.array([1.0, -1.0, 0.5, -0.5]), np.array([1, 0, 0, 1]), np.ones(4, bool))
        low = pu_risk_numpy(*args, PUConfig.from_dict({**GOOD, "mode": "upu", "class_prior": 0.1}))
        high = pu_risk_numpy(*args, PUConfig.from_dict({**GOOD, "mode": "upu", "class_prior": 0.6}))
        self.assertNotAlmostEqual(low["risk"], high["risk"])


@unittest.skipIf(torch is None, "torch not installed")
class TestTorchParity(unittest.TestCase):
    def test_matches_numpy_and_backprops(self):
        rng = np.random.default_rng(0)
        labels = "1101x00x0110xx00"
        residue = encode(labels)[None]
        logits_np = rng.normal(size=residue.shape)
        valid_np = np.ones_like(residue, bool)
        for mode in ("upu", "nnpu"):
            cfg = PUConfig.from_dict({**GOOD, "mode": mode, "class_prior": 0.3})
            ref = pu_risk_numpy(logits_np, residue, valid_np, cfg)
            logits = torch.tensor(logits_np, requires_grad=True)
            out = pu_semantic_loss(logits, torch.tensor(residue), torch.tensor(valid_np), cfg)
            self.assertAlmostEqual(float(out["objective"]), ref["objective"], places=6)
            out["objective"].backward()
            grad = logits.grad[0].numpy()
            self.assertTrue(np.all(grad[residue[0] == -1] == 0))  # x gets no gradient
            self.assertTrue(np.any(grad[residue[0] != -1] != 0))

    def test_empty_class_raises_or_zero(self):
        residue = torch.tensor([[0, 0, -1]])
        logits, valid = torch.zeros(1, 3, requires_grad=True), torch.ones(1, 3, dtype=torch.bool)
        with self.assertRaises(ValueError):
            pu_semantic_loss(logits, residue, valid, PUConfig.from_dict(GOOD))
        out = pu_semantic_loss(logits, residue, valid,
                               PUConfig.from_dict({**GOOD, "on_empty_class": "skip"}))
        self.assertEqual(float(out["objective"]), 0.0)
        out["objective"].backward()


if __name__ == "__main__":
    unittest.main()
