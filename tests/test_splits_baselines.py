import unittest

from linkerforge.splits import audit_split, grouped_split
from linkerforge.candidates import candidate_pool
from linkerforge.baselines import score_candidates


def record(ident, cluster, uniprot, family_a, family_b, linker):
    return {"example_id": ident, "homology_cluster_id": cluster,
            "source": {"uniprot_id": uniprot},
            "domain_a": {"family_ids": [family_a]},
            "domain_b": {"family_ids": [family_b]},
            "linker": {"sequence": linker, "length": len(linker)}}


class SplitTests(unittest.TestCase):
    def setUp(self):
        self.records = [record("a", "h1", "u1", "A", "B", "GGGGS"),
                        record("b", "h1", "u1", "A", "B", "GSGGS"),
                        record("c", "h2", "u2", "C", "D", "GSGSG"),
                        record("d", "h3", "u3", "E", "F", "GGSGG")]

    def test_deterministic_whole_clusters(self):
        first = grouped_split(self.records, seed=17)
        self.assertEqual(first, grouped_split(list(reversed(self.records)), seed=17))
        self.assertEqual(first["a"], first["b"])
        self.assertEqual(sum(audit_split(self.records, first).values()), 4)

    def test_rejects_missing_cluster_and_leakage(self):
        records = [dict(r) for r in self.records]
        del records[0]["homology_cluster_id"]
        with self.assertRaisesRegex(ValueError, "homology_cluster_id"):
            grouped_split(records)
        with self.assertRaisesRegex(ValueError, "Leakage"):
            audit_split(self.records, {"a": "train", "b": "blind", "c": "train", "d": "validation"})


class CandidateBaselineTests(unittest.TestCase):
    def setUp(self):
        self.train = [record("training", "h1", "u1", "A", "B", "GGSGG")]
        self.query = record("query", "h2", "u2", "C", "D", "GSGSG")

    def test_reference_only_on_explicit_evaluation_request(self):
        production = candidate_pool("query", self.train)
        self.assertNotIn("GSGSG", {c["linker_sequence"] for c in production})
        benchmark = candidate_pool("query", self.train, reference_sequence="GSGSG")
        self.assertEqual({c["generation_method"] for c in benchmark}, {"fixed_candidate_pool"})
        self.assertIn("GGGGSGGGGSGGGGS", {c["linker_sequence"] for c in benchmark})

    def test_duplicate_reference_does_not_change_pool_or_metadata(self):
        plain = candidate_pool("query", self.train)
        duplicate = candidate_pool("query", self.train, reference_sequence="GGSGG")
        self.assertEqual(plain, duplicate)

    def test_methods_score_identical_candidate_ids(self):
        pool = candidate_pool("query", self.train, reference_sequence="GSGSG")
        ids = {c["candidate_id"] for c in pool}
        for method in ("fixed_gs", "length_heuristic", "nearest_training", "hand_features"):
            output = score_candidates(self.query, pool, self.train, method)
            self.assertEqual({row["candidate_id"] for row in output}, ids)
        with self.assertRaisesRegex(ValueError, "training"):
            score_candidates(self.train[0], pool, self.train, "fixed_gs")


if __name__ == "__main__":
    unittest.main()
