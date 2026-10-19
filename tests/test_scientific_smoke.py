"""Small cross-module smoke test; fixtures are not scientific observations."""

import json
from pathlib import Path
import unittest

from linkerforge.baselines import score_candidates
from linkerforge.candidates import candidate_pool
from linkerforge.data import (
    ChainSequence,
    DomainAssignment,
    Provenance,
    ResidueMap,
    SourceMetadata,
    extract_natural_example,
)
from linkerforge.models.context import (
    ContextQuery,
    LocalPort,
    NaturalTrainingPair,
    PairwiseHandFeatureRanker,
    UnconfiguredContextModel,
)
from linkerforge.splits import audit_split, grouped_split


ROOT = Path(__file__).resolve().parents[1]


class ScientificSmokeTests(unittest.TestCase):
    def test_schemas_are_parseable_and_versioned(self):
        for name in ("natural-example", "candidate-recommendation", "final-result"):
            schema = json.loads((ROOT / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertEqual(schema["properties"]["schema_version"]["const"], "0.1.0")

    def test_fixture_flows_across_data_split_pool_and_scoring(self):
        sequence = "A" * 10 + "GSGSG" + "C" * 10
        chain = ChainSequence(sequence, tuple(ResidueMap(i, i + 100, "", i, True) for i in range(1, 26)))
        result = extract_natural_example(
            chain,
            (DomainAssignment(1, 10, ("F1",)), DomainAssignment(16, 25, ("F2",))),
            SourceMetadata("1ABC", "A", "P00001", "2026-10-08"),
            Provenance("fixture-sha", "fixture-config", {"fixture": "1"}),
        )
        self.assertTrue(result.accepted)
        native = result.record
        self.assertEqual(native["linker"]["class"], "unknown")
        train = {**native, "homology_cluster_id": "cluster-1", "split": "train"}
        query = {
            **native,
            "example_id": "query-2",
            "homology_cluster_id": "cluster-2",
            "source": {**native["source"], "uniprot_id": "P00002"},
            "domain_a": {**native["domain_a"], "family_ids": ["F3"]},
            "domain_b": {**native["domain_b"], "family_ids": ["F4"]},
        }
        assignment = grouped_split([train, query], seed=5)
        self.assertEqual(sum(audit_split([train, query], assignment).values()), 2)
        pool = candidate_pool(query["example_id"], [train], reference_sequence="GSGSG")
        self.assertTrue(all(c["generation_method"] == "fixed_candidate_pool" for c in pool))
        scored = score_candidates(query, pool, [train], "length_heuristic")
        self.assertEqual({c["candidate_id"] for c in pool}, {s["candidate_id"] for s in scored})

        context = ContextQuery("A" * 10, "C" * 10, LocalPort(0.5, 0.2), LocalPort(0.6, 0.3))
        ranker = PairwiseHandFeatureRanker().fit([NaturalTrainingPair(context, "GSGSG", ("AAAAA",))])
        self.assertEqual(ranker.status, "fitted_baseline")
        self.assertIsInstance(ranker.score(context, "GSGSG"), float)
        with self.assertRaisesRegex(RuntimeError, "unconfigured"):
            UnconfiguredContextModel().score(context, "GSGSG")


if __name__ == "__main__":
    unittest.main()
