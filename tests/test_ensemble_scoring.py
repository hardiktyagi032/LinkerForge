"""numpy-only tests for ensemble scoring and the encoder hook (unittest)."""

import tempfile
import unittest
from pathlib import Path

import numpy as np

from linkerforge.ensemble import (EncoderHookError, EnsembleError, PrecomputedEmbeddingStore,
                                  evaluate_ensemble, metrics, save_embeddings, save_member,
                                  stream_ensemble)

LABELS = ["0011100x10", "0000000000", "1111x00000", "000x000000"]


def make_scores(rng, noise):
    out = []
    for text in LABELS:
        base = np.array([0.8 if c == "1" else 0.2 for c in text])
        out.append(np.clip(base + rng.normal(0, noise, len(text)), 0.001, 0.999))
    return out


def write_members(folder, seeds=(7, 17, 31), split="protected_development", labels=LABELS):
    paths = []
    for seed in seeds:
        rng = np.random.default_rng(seed)
        path = Path(folder) / f"m{seed}.npz"
        save_member(path, protein_ids=[f"P{i}" for i in range(len(labels))], labels=labels,
                    scores=make_scores(rng, 0.2), seed=seed, arch="samlike", split=split,
                    checkpoint_sha256=f"h{seed}")
        paths.append(path)
    return paths


def brute(labels, scores):
    lab = np.array(list(labels))
    k = lab != "x"
    y = (lab[k] == "1")
    s = np.asarray(scores)[k]
    p, n = s[y], s[~y]
    auc = np.mean([(a > b) + 0.5 * (a == b) for a in p for b in n])
    # APS at distinct thresholds
    aps, prev_recall = 0.0, 0.0
    for t in sorted(set(s), reverse=True):
        sel = s >= t
        prec = y[sel].mean()
        rec = y[sel].sum() / y.sum()
        aps += (rec - prev_recall) * prec
        prev_recall = rec
    return auc, aps


class EnsembleTests(unittest.TestCase):
    def test_metrics_match_bruteforce(self):
        rng = np.random.default_rng(0)
        text = "".join(rng.choice(list("01x"), 300, p=[.6, .3, .1]))
        scores = np.round(rng.random(300), 1)  # many ties
        result = metrics(text, [300], scores, min_tp=1)
        auc, aps = brute(text, scores)
        self.assertAlmostEqual(result["auroc"], auc, places=10)
        self.assertAlmostEqual(result["aps"], aps, places=10)
        self.assertEqual(result["positive_residues"] + result["negative_residues"], text.count("0") + text.count("1"))

    def test_perfect_and_threshold_rules(self):
        text = "1" * 60 + "0" * 60
        scores = np.r_[np.full(60, .9), np.full(60, .1)]
        r = metrics(text, [120], scores)
        self.assertEqual((r["aps"], r["auroc"], r["fmax"]), (1.0, 1.0, 1.0))
        self.assertEqual(r["recall_at_precision_99"]["recall"], 1.0)
        # fewer than 50 TP -> no operating point, recall 0
        r = metrics("1" * 10 + "0" * 10, [20], np.r_[np.full(10, .9), np.full(10, .1)])
        self.assertIsNone(r["recall_at_precision_90"]["threshold"])

    def test_sequential_equals_in_memory(self):
        with tempfile.TemporaryDirectory() as d:
            paths = write_members(d)
            ens = stream_ensemble(paths)
            stack = np.stack([np.load(p)["probs"] for p in paths])
            np.testing.assert_allclose(ens["mean_prob"], stack.mean(0), atol=1e-12)
            np.testing.assert_allclose(ens["variance"], stack.var(0), atol=1e-12)
            lg = np.log(np.clip(stack, 1e-7, 1 - 1e-7) / (1 - np.clip(stack, 1e-7, 1 - 1e-7)))
            np.testing.assert_allclose(ens["mean_logit_prob"], 1 / (1 + np.exp(-lg.mean(0))), atol=1e-12)
            result = evaluate_ensemble(paths, min_tp=1)
            for key in ("mean_probability", "mean_logit", "uncertainty", "seeds"):
                self.assertIn(key, result)
            self.assertEqual(result["mean_probability"]["no_positive_proxy"]["proteins"], 2)

    def test_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            paths = write_members(d)
            with self.assertRaises(EnsembleError):
                stream_ensemble(paths[:2])  # fewer than 3 members
            with self.assertRaises(EnsembleError):
                stream_ensemble([paths[0], paths[0], paths[1]])  # duplicate seed
        with tempfile.TemporaryDirectory() as d:
            paths = write_members(d, split="caid3_common27")
            with self.assertRaises(EnsembleError):
                stream_ensemble(paths)
        with tempfile.TemporaryDirectory() as d:
            paths = write_members(d)
            other = Path(d) / "other.npz"
            changed = ["0011100x11"] + LABELS[1:]
            save_member(other, protein_ids=[f"P{i}" for i in range(4)], labels=changed,
                        scores=make_scores(np.random.default_rng(1), .2), seed=99, arch="samlike")
            with self.assertRaises(EnsembleError):
                stream_ensemble(paths[:2] + [other])  # label mismatch

    def test_bad_probabilities_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.npz"
            save_member(p, protein_ids=["a"], labels=["01"], scores=[np.array([0.5, 1.5])], seed=1, arch="x")
            with self.assertRaises(EnsembleError):
                stream_ensemble([p, p, p])


class EncoderHookTests(unittest.TestCase):
    ENC, SEQ = "esm2_t33_650M_UR50D", "MKTAY"

    def store(self, d, **override):
        args = dict(protein_id="P1", sequence=self.SEQ, encoder=self.ENC, revision="r1",
                    embeddings=np.zeros((5, 1280), dtype=np.float32))
        args.update(override)
        save_embeddings(Path(d) / f"{args['protein_id']}.{self.ENC}.npz", **args)
        return PrecomputedEmbeddingStore(d, self.ENC, "r1")

    def test_ok_and_refusals(self):
        with tempfile.TemporaryDirectory() as d:
            store = self.store(d)
            self.assertEqual(store.get("P1", self.SEQ).shape, (5, 1280))
            with self.assertRaises(EncoderHookError):
                store.get("P2", self.SEQ)  # missing
            with self.assertRaises(EncoderHookError):
                store.get("P1", "MKTAW")  # sequence mismatch
            with self.assertRaises(EncoderHookError):
                store.batch([("P1", self.SEQ), ("P2", self.SEQ)])  # all-or-nothing
            with self.assertRaises(EncoderHookError):
                store.get("../P1", self.SEQ)
            with self.assertRaises(EncoderHookError):
                PrecomputedEmbeddingStore(d, "unknown_encoder")
            with self.assertRaises(EncoderHookError):
                PrecomputedEmbeddingStore(d + "/nope", self.ENC)

    def test_shape_dim_value_revision(self):
        for bad in (np.zeros((4, 1280), np.float32), np.zeros((5, 1024), np.float32),
                    np.full((5, 1280), np.nan, np.float32)):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(EncoderHookError):
                    self.store(d, embeddings=bad).get("P1", self.SEQ)
        with tempfile.TemporaryDirectory() as d:
            self.store(d)
            with self.assertRaises(EncoderHookError):
                PrecomputedEmbeddingStore(d, self.ENC, "other").get("P1", self.SEQ)


if __name__ == "__main__":
    unittest.main()
