import math
import unittest

import numpy as np

from src.linkerforge.detector.selective import (
    apply_temperature, bootstrap_over_proteins, clopper_pearson_lower, counts_at,
    fit_temperature, select_threshold, selective_report, split_proteins)


def synth(n_prot=60, length=80, seed=0):
    rng = np.random.default_rng(seed)
    scores, labels = {}, {}
    for i in range(n_prot):
        y = (rng.random(length) < 0.2).astype(int)
        s = np.clip(0.5 * y + rng.normal(0.25, 0.15, length), 0.001, 0.999)
        y[rng.random(length) < 0.05] = -1  # unknown 'x'
        scores[f"P{i:03d}"], labels[f"P{i:03d}"] = s, y
    return scores, labels


class SelectiveTests(unittest.TestCase):
    def test_cp_known_values(self):
        self.assertAlmostEqual(clopper_pearson_lower(10, 10, 0.05), 0.05 ** 0.1, places=9)
        # 8/10 one-sided 95% exact lower bound is about 0.4931
        self.assertAlmostEqual(clopper_pearson_lower(8, 10, 0.05), 0.4931, places=3)
        self.assertEqual(clopper_pearson_lower(0, 10), 0.0)
        self.assertLess(clopper_pearson_lower(95, 100), 0.95)

    def test_split_is_by_protein_disjoint_deterministic(self):
        ids = [f"P{i}" for i in range(11)]
        a, b = split_proteins(ids, 3)
        self.assertFalse(set(a) & set(b))
        self.assertEqual(sorted(a + b), sorted(ids))
        self.assertEqual((a, b), split_proteins(ids, 3))

    def test_threshold_lowest_satisfying(self):
        s = np.array([0.9] * 400 + [0.5] * 100 + [0.1] * 100)
        y = np.array([1] * 400 + [1] * 90 + [0] * 10 + [0] * 100)
        self.assertEqual(select_threshold(s, y, 0.90)["threshold"], 0.5)
        self.assertEqual(select_threshold(s, y, 0.99)["threshold"], 0.9)

    def test_infeasible_abstains(self):
        s = np.array([0.9, 0.8, 0.7])
        y = np.array([0, 0, 1])
        sel = select_threshold(s, y, 0.99)
        self.assertFalse(sel["feasible"])
        self.assertTrue(math.isinf(sel["threshold"]))
        self.assertEqual(counts_at(s, y, math.inf)["tp"], 0)

    def test_report_masks_unknown_and_counts_consistent(self):
        scores, labels = synth()
        r = selective_report(scores, labels, seed=1, n_boot=200)
        known_ev = sum(int((np.asarray(labels[p]) != -1).sum()) for p in r["evaluation_proteins"])
        for t in r["targets"].values():
            self.assertEqual(sum(t["evaluation_counts"].values()), known_ev)
        self.assertFalse(set(r["calibration_proteins"]) & set(r["evaluation_proteins"]))
        self.assertIn("LOWER BOUND", r["note"])

    def test_precision_target_met_on_separable_data(self):
        scores, labels = synth()
        r = selective_report(scores, labels, targets=(0.90,), seed=2, n_boot=200)
        t = r["targets"]["0.9"]
        self.assertTrue(t["feasible"])
        p = t["evaluation_precision_lower_bound_on_true"]
        self.assertGreaterEqual(p, 0.88)
        lo, hi = t["bootstrap_over_proteins"]["precision_ci"]
        self.assertLessEqual(lo, p)
        self.assertGreaterEqual(hi, p)

    def test_temperature_scaling(self):
        scores, labels = synth()
        s = np.concatenate([scores[p] for p in scores])
        y = np.concatenate([labels[p] for p in labels])
        k = y != -1
        t = fit_temperature(s[k], y[k])
        self.assertGreater(t, 0)
        self.assertTrue(np.all(np.diff(apply_temperature(np.sort(s[k]), t)) >= 0))
        rng = np.random.default_rng(0)
        yy = (rng.random(5000) < 0.5).astype(int)
        raw = np.where(rng.random(5000) < 0.7, yy, 1 - yy) * 0.98 + 0.01  # overconfident
        self.assertGreater(fit_temperature(raw, yy), 1.5)
        r = selective_report(scores, labels, seed=1, temperature_scaling=True, n_boot=100)
        self.assertTrue(r["temperature_scaling"])

    def test_bootstrap_deterministic(self):
        per = {"a": {"tp": 5, "fp": 0, "fn": 5}, "b": {"tp": 4, "fp": 1, "fn": 1},
               "c": {"tp": 0, "fp": 0, "fn": 3}}
        self.assertEqual(bootstrap_over_proteins(per, 100, 1), bootstrap_over_proteins(per, 100, 1))

    def test_mismatched_ids_rejected(self):
        with self.assertRaises(ValueError):
            selective_report({"a": [0.1], "b": [0.2]}, {"a": [0]})


if __name__ == "__main__":
    unittest.main()
