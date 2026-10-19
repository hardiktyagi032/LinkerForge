"""Invented sequences/vectors/labels and coordinates: software tests only."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch

from linkerforge.attachment.benchmark import binary_metrics, compare, family_components, summarize
from linkerforge.attachment.cli import make_smoke_dataset, peer_predictions, smoke
from linkerforge.attachment.data import SiteExample, collate, load_embedding, preflight, save_embedding, sequence_sha256
from linkerforge.attachment.engine import SiteTrainConfig, score_domain, train
from linkerforge.attachment.features import asset_bundle_sha256, extract_residues, load_local_encoder
from linkerforge.attachment.model import SiteModel, SiteModelConfig, TASKS, allowed_positions
from linkerforge.attachment.plans import AttachmentPlan, evaluate_geometry, rank_plans
from linkerforge.generation.contracts import canonical_hash
from linkerforge.generation.data import file_sha256, load_json
from linkerforge.generation.engine import write_json
from linkerforge.geometry.structure import Atom, Chain, Residue


class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        torch.manual_seed(17)
        self.manifest = make_smoke_dataset(self.root / "data")
        self.data = preflight(self.manifest, True)
        self.config = SiteTrainConfig(SiteModelConfig(8, 16), max_steps=3, batch_size=6, checkpoint_every=1, cpu_threads=1, max_wall_seconds=120)

    def tearDown(self):
        self.tmp.cleanup()

    def mutate_rows(self, split, mutate):
        value = load_json(self.manifest)
        path = self.manifest.parent / value["splits"][split]["path"]
        rows = [json.loads(x) for x in path.read_text().splitlines()]
        mutate(rows)
        path.write_text("".join(json.dumps(x) + "\n" for x in rows), encoding="utf-8")
        value["splits"][split]["sha256"] = file_sha256(path)
        write_json(self.manifest, value)

    def test_frozen_feature_gradient_and_query_balanced_masked_loss(self):
        model = SiteModel(self.config.model)
        rows = self.data["records"]["train"][:2]
        features, labels, tasks = collate(rows, self.data["embeddings"])
        features.requires_grad_(True)
        result = model.loss(features, labels, tasks)
        individual = [model.loss(features[i:i+1], labels[i:i+1], tasks[i:i+1])["loss"] for i in range(2)]
        torch.testing.assert_close(result["loss"], torch.stack(individual).mean())
        result["loss"].backward()
        self.assertIsNone(features.grad)
        self.assertGreater(float(model.tower[0].weight.grad.abs().sum()), 0)
        self.assertEqual(int(result["known_sites"]), 3)

    def test_unknown_and_padding_have_no_target_gradient(self):
        model = SiteModel(self.config.model)
        x = torch.randn(1, 4, 8)
        labels, task = torch.tensor([[1, 0, -1, -1]]), torch.tensor([0])
        first = model.loss(x, labels, task)["loss"]
        other = x.clone()
        other[:, 2:] += 100
        torch.testing.assert_close(first, model.loss(other, labels, task)["loss"], rtol=0, atol=0)
        with self.assertRaises(ValueError):
            model.loss(x, labels.fill_(-1), task)

    def test_towers_do_not_consume_partner_or_linker_properties(self):
        model = SiteModel(self.config.model).eval()
        a, b = torch.randn(1, 4, 8), torch.randn(1, 4, 8)
        torch.testing.assert_close(model(a)[0], model(torch.cat([a, b]))[0], rtol=0, atol=0)
        with self.assertRaises(TypeError):
            model(a, cleavage="cleavable")

    def test_operation_positions_and_label_validation(self):
        self.assertEqual(allowed_positions("internal_insertion", 4), [1, 2, 3])
        self.assertEqual(allowed_positions("n_terminal_extension", 4), [1])
        self.assertEqual(allowed_positions("c_terminal_extension", 4), [4])
        row = self.data["records"]["train"][0]
        with self.assertRaises(ValueError):
            replace(row, labels=[1, 0, -1, 1])
        with self.assertRaises(ValueError):
            replace(row, evidence_tier="natural_linker_flank")
        with self.assertRaises(ValueError):
            replace(row, evidence_tier="natural_interruption")
        with self.assertRaises(ValueError):
            replace(row, evidence_tier="measured_terminal_extension")
        with self.assertRaises(ValueError):
            replace(row, labels=[True, 0, -1, -1])

    def test_natural_positives_do_not_create_negative_labels(self):
        row = replace(self.data["records"]["train"][0], evidence_tier="natural_interruption", labels=[1, -1, -1, -1])
        self.assertEqual(row.labels.count(-1), 3)

    def test_feature_cache_hash_alignment_and_mode(self):
        row = self.data["records"]["train"][0]
        path = self.manifest.parent / row.embedding["path"]
        with self.assertRaises(ValueError):
            load_embedding(path, "AAAA", self.data["manifest"]["encoder"], True)
        with self.assertRaises(ValueError):
            load_embedding(path, row.sequence, self.data["manifest"]["encoder"], False)
        with self.assertRaises(ValueError):
            save_embedding(self.root / "bad.safetensors", row.sequence, torch.zeros(5, 8), self.data["manifest"]["encoder"], True)
        with path.open("ab") as stream:
            stream.write(b"changed")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            preflight(self.manifest, True)

    def test_family_and_exact_sequence_leakage_are_blocked(self):
        self.mutate_rows("development", lambda rows: rows[0].update(family_ids=["SYNTHETIC-train-0"]))
        with self.assertRaisesRegex(ValueError, "leakage"):
            preflight(self.manifest, True)

    def test_unknown_as_negative_or_positive_only_bce_fail(self):
        self.mutate_rows("train", lambda rows: [row.update(labels=[1 if y == 0 else y for y in row["labels"]]) for row in rows])
        with self.assertRaisesRegex(ValueError, "known positive and negative"):
            preflight(self.manifest, True)

    def test_scientific_mode_and_missing_inputs_fail_before_construction(self):
        with patch("linkerforge.attachment.engine.SiteModel") as model:
            with self.assertRaises(ValueError):
                train(self.manifest, self.config, self.root / "fit")
            with self.assertRaises(FileNotFoundError):
                train(self.root / "missing", self.config, self.root / "fit")
            model.assert_not_called()

    def test_scientific_execution_requires_audited_inputs(self):
        fake = {**self.data, "synthetic": False}
        with patch("linkerforge.attachment.engine.preflight", return_value=fake), patch("linkerforge.attachment.engine.SiteModel") as constructor:
            with self.assertRaisesRegex(ValueError, "execution receipt"):
                train(self.manifest, self.config, self.root / "fit")
            constructor.assert_not_called()

    def scientific_interface_fixture(self):
        # Invented Boolean/vector fixture for gate validation only; never fitted.
        value = load_json(self.manifest)
        encoder = {"model_id": "NONBIOLOGICAL-interface-fixture", "revision": "a"*40, "weights_sha256": "b"*64, "layer": 1, "embedding_dim": 8}
        rewritten = {}
        for split in ("train", "development"):
            def convert(rows):
                for row in rows:
                    old = row["embedding"]["path"]
                    if old not in rewritten:
                        destination = self.manifest.parent / ("interface-" + old)
                        save_embedding(destination, row["sequence"], self.data["embeddings"][row["record_id"]], encoder, False)
                        rewritten[old] = {"path": destination.name, "sha256": file_sha256(destination)}
                    row["embedding"] = rewritten[old]
                    row["evidence_tier"] = "measured_insertion" if row["task"] == "internal_insertion" else "measured_terminal_extension"
            self.mutate_rows(split, convert)
        value = load_json(self.manifest)
        value.update(kind="scientific_dataset", encoder=encoder,
                     review={"approved": True, "reviewer": "fixture", "reference": "fixture-no-real-data"},
                     task_definitions={task: {"review_reference": "fixture", "endpoint": "NONBIOLOGICAL-fixture",
                         "label_scope": "donor_aggregated", "aggregation_protocol": "fixture-only", "negative_evidence_policy": "fixture-Booleans"} for task in TASKS})
        registry = self.manifest.parent / "registry.json"
        write_json(registry, {"format": "sequence-exclusion-registry.v1", "records": [{"source_id": "protected-fixture", "sequence_sha256": "f"*64, "family_ids": ["protected-fixture"]}]})
        value["benchmark_registries"] = [{"name": "protected", "path": registry.name, "sha256": file_sha256(registry)}]
        audit = self.manifest.parent / "audit.json"
        write_json(audit, {"passed": True, "method": "fixture-not-real-homology", "review_reference": "fixture",
            "split_sha256s": {k: v["sha256"] for k, v in value["splits"].items()}, "benchmark_registry_sha256s": {"protected": file_sha256(registry)}})
        value["split_audit"] = {"path": audit.name, "sha256": file_sha256(audit)}
        write_json(self.manifest, value)
        return value

    def test_full_scientific_interface_requires_reviewed_aggregation(self):
        value = self.scientific_interface_fixture()
        self.assertEqual(preflight(self.manifest)["supported_tasks"], list(TASKS))
        value["task_definitions"]["internal_insertion"]["label_scope"] = "individual_donor_variant"
        write_json(self.manifest, value)
        with self.assertRaisesRegex(ValueError, "donor aggregation"):
            preflight(self.manifest)

    def test_protected_registry_and_stale_audit_fail_closed(self):
        value = self.scientific_interface_fixture()
        registry = self.manifest.parent / "registry.json"
        for family in ("SYNTHETIC-train-0", "another-unprotected-fixture"):
            write_json(registry, {"format": "sequence-exclusion-registry.v1", "records": [{"source_id": "protected-fixture", "sequence_sha256": "f"*64, "family_ids": [family]}]})
            value["benchmark_registries"][0]["sha256"] = file_sha256(registry)
            write_json(self.manifest, value)
            with self.assertRaises(ValueError):
                preflight(self.manifest)

    def test_binary_metrics_known_values_and_ties(self):
        self.assertEqual(binary_metrics([0, 1], [0., 1.])["auroc"], 1)
        self.assertEqual(binary_metrics([0, 1], [1., 0.])["auroc"], 0)
        result = binary_metrics([0, 1], [0., 0.])
        self.assertEqual(result["auroc"], .5)
        self.assertEqual(result["average_precision"], .5)
        self.assertIsNone(binary_metrics([0, 0], [0., 1.])["average_precision"])
        self.assertIsNone(binary_metrics([1, 1], [0., 1.])["auroc"])

    def test_precision_coverage_ties_and_unknown_selected(self):
        row = self.data["records"]["train"][0]
        tied = summarize([row], {row.record_id: [0., 0., 0., 0.]}, .5)
        self.assertEqual(tied["selection_budget"], 1)
        self.assertEqual(tied["selected_sites"], 0)
        self.assertIsNone(tied["precision"])
        unknown = summarize([row], {row.record_id: [0., 0., 1., 0.]}, .5)
        self.assertEqual(unknown["selected_unknown"], 1)
        self.assertIsNone(unknown["precision"])
        self.assertEqual(unknown["reference_unknown"], 2)

    def test_missing_failed_and_malformed_outputs_retain_denominators(self):
        rows = [row for row in self.data["records"]["development"] if row.task == "internal_insertion"]
        for missing in (None, [], [float("nan")]*4):
            result = summarize(rows, {rows[0].record_id: [0., 1., 0., 0.], rows[1].record_id: missing}, .5)
            self.assertEqual(result["attempted_records"], 2)
            self.assertEqual(result["valid_records"], 1)
            self.assertEqual(result["expected_known_sites"], 4)
            self.assertIsNone(result["auroc"])
            self.assertIsNone(result["precision"])

    def test_family_components_use_transitive_overlaps(self):
        row = self.data["records"]["train"][0]
        rows = [replace(row, record_id=str(i), family_ids=families) for i, families in enumerate((["a"], ["c"], ["a", "b"], ["b", "c"], ["d"]))]
        self.assertEqual(sorted(map(len, family_components(rows))), [1, 4])

    def test_paired_bootstrap_and_common_coverage_are_reproducible(self):
        rows = [r for r in self.data["records"]["development"] if r.task == "internal_insertion"]
        good = {r.record_id: [float(y if y != -1 else 0) for y in r.labels] for r in rows}
        bad = {r.record_id: [-v for v in values] for r, values in ((r, good[r.record_id]) for r in rows)}
        first = compare(rows, {"good": good, "bad": bad}, .5, 20, 17)
        self.assertEqual(first, compare(rows, {"good": good, "bad": bad}, .5, 20, 17))
        task = first["tasks"]["internal_insertion"]
        self.assertEqual(task["common_records"], 2)
        self.assertEqual(task["paired_family_uncertainty"]["bad"]["independent_family_components"], 2)
        bad.pop(rows[0].record_id)
        self.assertEqual(compare(rows, {"good": good, "bad": bad}, .5, 0)["tasks"]["internal_insertion"]["common_records"], 1)

    def test_untrained_heads_are_unknown_not_fake_scores(self):
        model = SiteModel(self.config.model)
        row = self.data["records"]["train"][0]
        meta = {"identity": {"supported_tasks": list(TASKS), "synthetic_software_fixture": True}, "trained_tasks": ["internal_insertion"]}
        result = score_domain(model, row.sequence, self.data["embeddings"][row.record_id], meta)
        self.assertEqual(result["tasks"]["n_terminal_extension"]["status"], "untrained_no_score")
        self.assertIsNone(result["tasks"]["n_terminal_extension"]["sites"][0]["logit"])

    def test_checkpoint_marks_only_actually_supervised_tasks(self):
        partial = train(self.manifest, replace(self.config, batch_size=1), self.root / "partial", True, stop_after=1)
        _, meta = SiteModel.load(partial["checkpoint"])
        self.assertLess(len(meta["trained_tasks"]), 3)
        self.assertEqual(meta["completed_steps"], 1)

    def test_exact_dropout_resume_and_checkpoint_integrity(self):
        config = replace(self.config, model=replace(self.config.model, dropout=.2), max_steps=4)
        full = train(self.manifest, config, self.root / "full", True)
        partial = train(self.manifest, config, self.root / "partial", True, stop_after=2)
        resumed = train(self.manifest, config, self.root / "resume", True, resume=partial["checkpoint"])
        left, _ = SiteModel.load(full["checkpoint"])
        right, _ = SiteModel.load(resumed["checkpoint"])
        for name, value in left.state_dict().items():
            torch.testing.assert_close(value, right.state_dict()[name], rtol=0, atol=0)
        self.assertEqual(load_json(self.root / "full/history.json"), load_json(self.root / "resume/history.json"))
        path = Path(resumed["checkpoint"]) / "model.safetensors"
        with path.open("ab") as handle:
            handle.write(b"tamper")
        with self.assertRaises(ValueError):
            SiteModel.load(resumed["checkpoint"])

    def test_resume_mismatch_retains_failure_and_budgets_fail_closed(self):
        partial = train(self.manifest, self.config, self.root / "partial", True, stop_after=1)
        with self.assertRaisesRegex(ValueError, "Resume"):
            train(self.manifest, replace(self.config, seed=31), self.root / "failed", True, resume=partial["checkpoint"])
        self.assertEqual(load_json(self.root / "failed/run.json")["status"], "failed")
        with self.assertRaisesRegex(ValueError, "Synthetic"):
            train(self.manifest, replace(self.config, max_steps=9), self.root / "ceiling", True)

    def test_checkpoint_training_task_metadata_is_hash_bound(self):
        job = train(self.manifest, self.config, self.root / "fit", True, stop_after=1)
        path = Path(job["checkpoint"]) / "model.json"
        value = load_json(path)
        value["training"]["trained_tasks"] = []
        write_json(path, value)
        with self.assertRaisesRegex(ValueError, "metadata binding"):
            SiteModel.load(job["checkpoint"])

    def test_source_peer_interface_preserves_alignment_and_missing_coverage(self):
        row = self.data["records"]["development"][0]
        value = {"format": "attachment-peer-predictions.v0", "method_id": "synthetic-peer", "version": "fixture", "review_reference": "fixture",
                 "exposure_audit": "fixture", "position_mapping_reference": "fixture", "input_modality": "sequence",
                 "records": [{"record_id": row.record_id, "task": row.task, "sequence_sha256": sequence_sha256(row.sequence), "scores": None}]}
        path = self.root / "peer.json"
        write_json(path, value)
        predictions, meta = peer_predictions(path, self.data)
        self.assertIsNone(predictions[row.record_id])
        self.assertEqual(meta["file_sha256"], file_sha256(path))
        value["records"][0]["sequence_sha256"] = "f"*64
        write_json(path, value)
        with self.assertRaises(ValueError):
            peer_predictions(path, self.data)

    def test_tandem_and_insertion_have_distinct_contact_topologies(self):
        tandem = AttachmentPlan("one", "a", "b", "ACDE", "FGHI", linker_lengths=(15,))
        inserted = AttachmentPlan("two", "a", "b", "ACDE", "FGHI", topology="insertion", insertion_after=2, linker_lengths=(5, 6))
        self.assertEqual(tandem.contacts(), [(4, 1, "flexible", 15)])
        self.assertEqual(inserted.contacts(), [(2, 1, "flexible", 5), (3, 4, "flexible", 6)])
        self.assertEqual(inserted.required_scores()[0], ("a", "internal_insertion", 2))
        with self.assertRaises(ValueError):
            replace(inserted, linker_lengths=(5,))
        with self.assertRaises(ValueError):
            replace(inserted, insertion_after=4)

    def chain(self, identifier, sequence, coordinates):
        three = {"A": "ALA", "C": "CYS", "D": "ASP", "E": "GLU", "F": "PHE", "G": "GLY", "H": "HIS", "I": "ILE"}
        return Chain(identifier, tuple(Residue(identifier, i*10, " ", three[aa], (Atom("CA", "C", point, 1.7),)) for i, (aa, point) in enumerate(zip(sequence, coordinates), 1)))

    def test_geometry_adapter_maps_sequence_anchors_and_checks_resources(self):
        plan = AttachmentPlan("plan", "a", "b", "AC", "FG", topology="insertion", insertion_after=1, linker_lengths=(0, 0))
        a = self.chain("A", "AC", [(0., 0., 0.), (30., 0., 0.)])
        b = self.chain("B", "FG", [(0., 0., 0.), (2., 0., 0.)])
        result = evaluate_geometry(plan, a, b, {1: 10, 2: 20}, {1: 10, 2: 20})
        self.assertEqual(result["geometry"]["verdict"], "certified_infeasible")
        self.assertEqual(result["number_of_peptide_connections"], 2)
        with self.assertRaises(ValueError):
            evaluate_geometry(plan, a, b, {1: 20, 2: 10}, {1: 10, 2: 20})
        with self.assertRaises(ValueError):
            evaluate_geometry(plan, a, b, {1: 10, 2: 20}, {1: 10, 2: 20}, restarts=100)

    def test_ranker_does_not_promote_missing_head_or_geometry_certificate(self):
        plan = AttachmentPlan("plan", "a", "b", "AC", "FG")
        result = rank_plans([plan], {}, {})
        self.assertIsNone(result["plans"][0]["mean_operation_logit"])
        self.assertEqual(result["plans"][0]["status"], "unassessed_site_tasks")
        geometry = {"verdict": "certified_infeasible"}
        evidence = {"plan": {"plan_id": "plan", "plan_sha256": canonical_hash(plan.__dict__), "geometry": geometry, "geometry_sha256": canonical_hash(geometry)}}
        self.assertEqual(rank_plans([plan], {}, evidence)["plans"][0]["status"], "rejected_geometry")
        evidence["plan"]["geometry"]["verdict"] = "feasible_with_witness"
        with self.assertRaises(ValueError):
            rank_plans([plan], {}, evidence)

    def test_actual_frozen_esm_interface_with_tiny_local_random_model(self):
        from transformers import EsmConfig, EsmModel, EsmTokenizer
        vocab = ["<cls>", "<pad>", "<eos>", "<unk>"] + list("ACDEFGHIKLMNPQRSTVWY") + ["<mask>"]
        path = self.root / "vocab.txt"
        path.write_text("\n".join(vocab) + "\n")
        tokenizer = EsmTokenizer(vocab_file=str(path))
        model = EsmModel(EsmConfig(vocab_size=len(vocab), hidden_size=8, num_hidden_layers=1,
            num_attention_heads=2, intermediate_size=16, pad_token_id=1, mask_token_id=24,
            token_dropout=False, max_position_embeddings=32))
        values = extract_residues(model, tokenizer, "ACDE", 1)
        self.assertEqual(values.shape, (4, 8))
        self.assertFalse(model.training)
        self.assertTrue(all(not p.requires_grad for p in model.parameters()))
        self.assertFalse(values.requires_grad)
        assets = self.root / "tiny-local-encoder"
        model.save_pretrained(assets)
        tokenizer.save_pretrained(assets)
        identity = {"model_id": "random-interface-fixture", "revision": "a"*40, "weights_sha256": asset_bundle_sha256(assets), "layer": 1, "embedding_dim": 8}
        loaded, tok = load_local_encoder(assets, identity)
        torch.testing.assert_close(values, extract_residues(loaded, tok, "ACDE", 1))
        (assets / "unexpected-change.txt").write_text("tamper")
        with self.assertRaisesRegex(ValueError, "asset bundle hash"):
            load_local_encoder(assets, identity)
        with self.assertRaises(ValueError):
            extract_residues(model, tokenizer, "A"*40, 1)

    def test_end_to_end_software_smoke(self):
        result = smoke(self.root / "smoke")
        self.assertTrue(result["synthetic_software_fixture"])
        self.assertIsNone(result["biological_performance"])
        self.assertEqual(result["run"]["completed_steps"], 3)
        self.assertEqual(result["trained_tasks"], list(TASKS))
        benchmark = load_json(self.root / "smoke/benchmark-software-only.json")
        self.assertEqual(set(benchmark["tasks"]), set(TASKS))
        self.assertTrue(all("uniform" in value["full_attempted_coverage"] for value in benchmark["tasks"].values()))


if __name__ == "__main__":
    unittest.main()
