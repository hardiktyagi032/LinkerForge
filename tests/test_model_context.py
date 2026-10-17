"""Focused M6 contract tests using only the Python standard library."""

import unittest

from linkerforge.models import (
    ContextQuery,
    LocalPort,
    NaturalTrainingPair,
    PairwiseHandFeatureRanker,
    UnconfiguredContextModel,
    candidate_features,
)


class ContextModelTests(unittest.TestCase):
    def setUp(self):
        self.query = ContextQuery(
            domain_a_sequence="ACDEFGHIK",
            domain_b_sequence="LMNPQRSTV",
            port_a=LocalPort(accessibility=0.8, contact_density=0.2),
            port_b=LocalPort(accessibility=0.4, contact_density=0.6),
        )

    def test_features_are_deterministic_and_local(self):
        first = candidate_features(self.query, "GGGGS")
        self.assertEqual(first, candidate_features(self.query, "GGGGS"))
        self.assertEqual(first["glycine_fraction"], 0.8)
        self.assertEqual(first["port_a_accessibility"], 0.8)
        self.assertEqual(first["port_b_accessibility"], 0.4)
        self.assertNotIn("interdomain_distance", first)

    def test_invalid_sequences_and_ports_rejected(self):
        with self.assertRaises(ValueError):
            candidate_features(self.query, "GSXGS")
        with self.assertRaises(ValueError):
            candidate_features(self.query, "GS")
        with self.assertRaises(ValueError):
            LocalPort(accessibility=float("nan"), contact_density=0.2)
        with self.assertRaises(ValueError):
            ContextQuery("abc", "ACDEG", self.query.port_a, self.query.port_b)

    def test_unconfigured_neural_model_does_not_fake_score(self):
        model = UnconfiguredContextModel()
        self.assertEqual(model.status, "unconfigured")
        with self.assertRaisesRegex(RuntimeError, "unconfigured"):
            model.score(self.query, "GGGGS")

    def test_baseline_requires_training_and_reproduces_scores(self):
        pair = NaturalTrainingPair(self.query, "GGGGS", ("AAAAA", "VVVVV"))
        model = PairwiseHandFeatureRanker()
        self.assertEqual(model.status, "untrained")
        with self.assertRaisesRegex(RuntimeError, "untrained"):
            model.score(self.query, "GGGGS")
        model.fit([pair])
        replica = PairwiseHandFeatureRanker().fit([pair])
        self.assertEqual(model.status, "fitted_baseline")
        self.assertEqual(model.weights, replica.weights)
        self.assertEqual(model.training_pairs, 2)
        self.assertEqual(model.score(self.query, "GGGGS"), replica.score(self.query, "GGGGS"))
        self.assertGreater(model.score(self.query, "GGGGS"), model.score(self.query, "AAAAA"))

    def test_synthetic_alternative_is_not_observed(self):
        with self.assertRaises(ValueError):
            NaturalTrainingPair(self.query, "GGGGS", ("GGGGS",))
        with self.assertRaisesRegex(ValueError, "distinct feature pair"):
            PairwiseHandFeatureRanker().fit([NaturalTrainingPair(self.query, "GGGGS", ("SGGGG",))])


if __name__ == "__main__":
    unittest.main()
