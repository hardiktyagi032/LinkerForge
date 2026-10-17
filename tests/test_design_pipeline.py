"""Invented strings/vectors and mocked jobs: software verification only."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import torch

from linkerforge.attachment.data import sequence_sha256
from linkerforge.attachment.plans import AttachmentPlan, evaluate_geometry, rank_plans
from linkerforge.generation.contracts import DesignRequest, GeneratorConfig, TrainingExample, canonical_hash
from linkerforge.generation.data import file_sha256, load_json
from linkerforge.generation.engine import write_json
from linkerforge.generation.model import LinkerInfiller
from linkerforge.generation.benchmark import compare_reconstruction
from linkerforge.geometry.structure import Atom, Chain, Residue
from linkerforge.pipeline.cli import main
from linkerforge.pipeline.design import DesignBudget, design
from linkerforge.pipeline.intake import review_candidate
from linkerforge.pipeline.routes import ContactRoute, assemble, junctions, parse_plan
from linkerforge.pipeline import training


def route():
    return ContactRoute("three", "a", "b", "ACDE", "FGHI",
                        (("a", 1, 2), ("b", 1, 2), ("a", 3, 4), ("b", 3, 4)), (2, 2, 2), ("flexible",)*3)


def fixture_library():
    return {"library_id": "linker_property_library.v1", "sources": {"invented": {"citation": "SYNTHETIC software fixture; no literature evidence"}},
            "entries": [{"entry_id": str(i), "sequence": s, "source_key": "invented", "source_locator": "invented fixture",
                         "rigidity": {"label": "flexible"}, "cleavability": {"label": "non_cleavable"}} for i, s in enumerate(("GS", "SG"))]}


class RouteTests(unittest.TestCase):
    def test_three_connections_are_an_explicit_preserved_chain_route(self):
        plan = route()
        self.assertEqual(plan.contacts(), [(2, 1, "flexible", 2), (3, 2, "flexible", 2), (4, 3, "flexible", 2)])
        self.assertEqual(plan.required_scores(), [("a", "c_terminal_extension", 4), ("a", "internal_insertion", 2),
                                                ("b", "internal_insertion", 2), ("b", "n_terminal_extension", 1)])
        result = assemble(plan, ["GS", "SG", "GG"])
        self.assertEqual(result["sequence"], "ACGSFGSGDEGGHI")
        for domain, expected in (("a", "ACDE"), ("b", "FGHI")):
            extracted = "".join(result["sequence"][r["fusion_start"]-1:r["fusion_end"]] for r in result["residue_mapping"] if r.get("domain_id") == domain)
            self.assertEqual(extracted, expected)
        self.assertEqual(parse_plan(json.loads(json.dumps(asdict(plan)))), plan)

    def test_invalid_routes_do_not_silently_drop_duplicate_or_reorder_residues(self):
        invalid = [(("a", 1, 1), ("b", 1, 2), ("a", 3, 4), ("b", 3, 4)),
                   (("a", 1, 2), ("b", 1, 2), ("a", 2, 4), ("b", 3, 4)),
                   (("a", 1, 2), ("a", 3, 4), ("b", 1, 2), ("b", 3, 4)),
                   (("a", 3, 4), ("b", 1, 2), ("a", 1, 2), ("b", 3, 4))]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(route(), segments=value)
        with self.assertRaises(ValueError):
            replace(route(), linker_lengths=(2,))
        with self.assertRaises(ValueError):
            replace(route(), linker_types=("disulfide",)*3)

    def test_legacy_insertion_and_zero_length_control_assemble_without_a_generator(self):
        plan = AttachmentPlan("insert", "a", "b", "ACDE", "FGHI", topology="insertion", insertion_after=2, linker_lengths=(0, 0))
        self.assertEqual(assemble(plan, ["", ""])["sequence"], "ACFGHIDE")
        report = design([plan], {}, {})["plans"][0]
        self.assertEqual(report["admissible_sequence_assemblies"], 1)
        self.assertIsNone(report["assemblies"][0]["residue_mapping"][1]["fusion_start"])
        self.assertFalse(report["generator_topology_supported"])
        with self.assertRaises(ValueError):
            assemble(plan, ["G", ""])

    def test_multicontact_geometry_uses_all_contacts_in_a_single_placement_problem(self):
        plan = route()
        def chain(identifier, seq):
            three = {"A": "ALA", "C": "CYS", "D": "ASP", "E": "GLU", "F": "PHE", "G": "GLY", "H": "HIS", "I": "ILE"}
            return Chain(identifier, tuple(Residue(identifier, i, " ", three[aa], (Atom("CA", "C", (float(i*4), 0., 0.), 1.7),)) for i, aa in enumerate(seq, 1)))
        with patch("linkerforge.attachment.plans.evaluate_tether_set", return_value={"verdict": "undetermined"}) as solver:
            result = evaluate_geometry(plan, chain("A", plan.sequence_a), chain("B", plan.sequence_b), {i:i for i in range(1,5)}, {i:i for i in range(1,5)})
        self.assertEqual(solver.call_count, 1)
        self.assertEqual(solver.call_args.args[2], tuple(plan.contacts()))
        self.assertEqual(result["number_of_peptide_connections"], 3)
        self.assertIsNone(rank_plans([plan], {}, {plan.plan_id: result})["plans"][0]["mean_operation_logit"])

    def test_four_or_more_connections_have_no_hidden_two_linker_limit(self):
        p = ContactRoute("five", "a", "b", "ACDEFG", "HIKLMN", (("a",1,2),("b",1,2),("a",3,4),("b",3,4),("a",5,6),("b",5,6)), (1,)*5, ("flexible",)*5)
        self.assertEqual(len(p.contacts()), 5)
        self.assertEqual(len(assemble(p, ["G"]*5)["sequence"]), 17)


class DesignTests(unittest.TestCase):
    def test_templates_connect_every_edge_and_bound_cartesian_assembly(self):
        value = design([route()], {}, {}, library=fixture_library(), budget=DesignBudget(assemblies_per_plan=3))
        result = value["plans"][0]
        self.assertEqual(result["possible_assembly_combinations"], 8)
        self.assertEqual(len(result["assemblies"]), 3)
        self.assertEqual(result["status"], "unassessed_site_tasks")
        self.assertEqual(result["geometry_verdict"], "not_assessed")
        self.assertIsNone(value["scientific_performance"])

    def test_junction_transfer_is_explicit_and_default_is_not_run(self):
        fake = object()
        identity = {"synthetic_software_fixture": True, "model_metadata_sha256": "fixture"}
        with patch("linkerforge.pipeline.design.generate") as sample:
            result = design([route()], {}, {}, model=fake, model_identity=identity)
        sample.assert_not_called()
        self.assertEqual(result["plans"][0]["junction_proposals"][0]["methods"]["infiller"]["status"], "not_run_unreviewed_context_transfer")
        with patch("linkerforge.pipeline.design.generate", return_value={"candidates": [], "attempts": []}) as sample:
            result = design([route()], {}, {}, model=fake, model_identity=identity,
                            budget=DesignBudget(allow_junction_context_transfer=True))
        self.assertEqual(sample.call_count, 3)
        self.assertEqual(sample.call_args_list[1].args[1].domain_a, "FG")
        self.assertEqual(sample.call_args_list[1].args[1].domain_b, "DE")
        self.assertTrue(result["synthetic_software_fixture"])

    def test_actual_untrained_native_model_connects_tandem_proposal_to_assembly(self):
        torch.set_num_threads(1)
        torch.manual_seed(17)
        model = LinkerInfiller(GeneratorConfig(max_linker_length=8, max_positions=64, flank_residues=8, hidden_size=16, layers=1, heads=2, dropout=0))
        plan = AttachmentPlan("tandem", "a", "b", "ACDE", "FGHI", linker_lengths=(2,))
        value = design([plan], {}, {}, model=model, model_identity={"synthetic_software_fixture": True, "model_metadata_sha256": "random-untrained-fixture"},
                       budget=DesignBudget(candidates_per_junction=1, attempts_per_junction=1))
        result = value["plans"][0]
        self.assertEqual(len(result["assemblies"]), 1)
        self.assertTrue(result["assemblies"][0]["sequence"].startswith("ACDE"))
        self.assertTrue(result["assemblies"][0]["sequence"].endswith("FGHI"))
        self.assertEqual(len(result["assemblies"][0]["sequence"]), 10)
        self.assertFalse(result["assemblies"][0]["fusion_function_validated"])

    def test_geometry_rejection_and_plan_budget_preserve_unattempted_plans(self):
        a = AttachmentPlan("one", "a", "b", "AC", "FG", linker_lengths=(2,))
        b = replace(a, plan_id="two")
        geometry = {"verdict": "certified_infeasible"}
        evidence = {a.plan_id: {"geometry": geometry, "geometry_sha256": canonical_hash(geometry), "plan_sha256": canonical_hash(a.__dict__)}}
        result = design([a, b], {}, evidence, library=fixture_library(), budget=DesignBudget(max_plans=1))
        self.assertEqual(len(result["plans"]), 2)
        self.assertEqual(result["plans"][0]["plan_id"], "two")
        self.assertEqual(result["plans"][1]["assemblies"], [])

    def test_forbidden_motif_across_two_linkers_and_a_tiny_fragment_is_rejected(self):
        plan = AttachmentPlan("insert", "a", "b", "AC", "F", topology="insertion", insertion_after=1, linker_lengths=(2,2))
        controls = {"insert": [{"forbidden_motifs": ["GSFSG"]}, {"forbidden_motifs": ["GSFSG"]}]}
        result = design([plan], {}, {}, library=fixture_library(), controls=controls)["plans"][0]
        rejected = [a for a in result["assemblies"] if a["sequence"] == "AGSFSGC"]
        self.assertEqual(rejected[0]["status"], "rejected_sequence_rule")
        self.assertIn("known_forbidden_motif_in_assembled_junctions", rejected[0]["reasons"])

    def test_controls_cannot_override_sites_or_contradict_geometry_type(self):
        for controls in ({"three": [{"length": 2}, {}, {}]}, {"three": [{"rigidity": "rigid"}, {}, {}]}):
            with self.assertRaises(ValueError):
                design([route()], {}, {}, library=fixture_library(), controls=controls)
        with self.assertRaises(ValueError):
            DesignBudget(candidates_per_junction=8, attempts_per_junction=2)


class ComparisonTests(unittest.TestCase):
    def records(self):
        return [TrainingExample(f"r{i}", DesignRequest("AC", "FG", 2), "GS", f"source{i}", "a"*64,
                                families, "synthetic_software_fixture", True)
                for i, families in enumerate((("x",), ("x", "y"), ("y",), ("z",)))]

    def test_failures_remain_in_full_denominators_and_family_draws_are_paired(self):
        result = compare_reconstruction(self.records(), {"a": {"r0":"GS","r1":"GS","r2":None,"r3":"GG"},
                                                        "b": {"r0":"GS","r1":"SG","r2":"GS","r3":"GS"}}, bootstrap_draws=20)
        self.assertEqual(result["full_attempted_coverage"]["a"]["attempted_records"], 4)
        self.assertEqual(result["full_attempted_coverage"]["a"]["exact_match_fraction_all_attempts"], .5)
        self.assertEqual(result["common_records"], 3)
        self.assertEqual(result["paired_family_uncertainty"]["full_attempted_coverage"]["b"]["family_components"], 2)
        self.assertEqual(result, compare_reconstruction(self.records(), {"a": {"r0":"GS","r1":"GS","r2":None,"r3":"GG"},
                                                                       "b": {"r0":"GS","r1":"SG","r2":"GS","r3":"GS"}}, bootstrap_draws=20))

    def test_invalid_extra_or_constrained_calls_do_not_improve_coverage(self):
        result = compare_reconstruction(self.records(), {"bad": {"r0":"G","r1":"xx","r2":3}}, bootstrap_draws=0)
        self.assertEqual(result["full_attempted_coverage"]["bad"]["valid_calls"], 0)
        self.assertIsNone(result["full_attempted_coverage"]["bad"]["edit_distance_valid_calls_mean"])
        self.assertEqual(result["full_attempted_coverage"]["bad"]["exact_match_fraction_all_attempts"], 0)
        with self.assertRaises(ValueError):
            compare_reconstruction(self.records(), {"extra": {"outside":"GS"}})

    def test_single_family_does_not_produce_an_uncertainty_interval(self):
        rows = self.records()[:3]
        result = compare_reconstruction(rows, {"a": {}, "b": {}})
        self.assertIsNone(result["paired_family_uncertainty"]["full_attempted_coverage"]["b"]["paired_percentile_95_interval"])


class IntakeTests(unittest.TestCase):
    def packet(self):
        seq = "ACDEFGHIKLMNPQRSTVWY"
        return {"format":"mined-linker-candidate.v0", "source_id":"SYNTHETIC", "source_release":"fixture", "source_sequence":seq,
                "source_sha256":sequence_sha256(seq), "start":8,"end":12,"residues":seq[7:12],"flank_before":seq[:7],"flank_after":seq[12:],
                "score":.999,"threshold_id":"fixture-threshold", "abstained":False,"classifier_sha256":"a"*64,"calibration_sha256":"b"*64,
                "config_sha256":"c"*64,"pipeline_commit":"d"*40,"family_ids":["fixture-family"]}

    def test_high_score_does_not_make_training_or_tolerance_evidence(self):
        report = review_candidate(self.packet())
        self.assertFalse(report["training_eligible"])
        self.assertIsNone(report["site_tolerance_labels"])
        self.assertEqual(report["evidence_tier"], "predicted_span")
        self.assertEqual(review_candidate({**self.packet(),"abstained":True})["status"], "abstained_do_not_use")

    def test_mapping_provenance_and_abstention_are_not_optional(self):
        for changes in ({"start":7},{"flank_before":"AC"},{"source_sha256":"a"*64},{"score":float("nan")},{"abstained":0},{"family_ids":[]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                review_candidate({**self.packet(), **changes})


class TrainingPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = Path(__file__).resolve().parents[1]
        self.recipe = load_json(self.repo / "configs/design-training-round.json")
        for variant in self.recipe["variants"]:
            variant["config"] = str(self.repo / "configs" / variant["config"])
        self.recipe_path = self.root / "recipe.json"
        write_json(self.recipe_path, self.recipe)

    def test_missing_data_produces_nine_blocked_jobs_and_unsigned_receipts_without_fitting(self):
        with patch("subprocess.Popen") as spawn:
            report = training.prepare(self.recipe_path, self.root / "prepared")
        spawn.assert_not_called()
        self.assertEqual(len(report["jobs"]), 9)
        self.assertEqual(report["reserved_wall_seconds"], 16200)
        self.assertFalse(report["training_authorized"])
        self.assertEqual({j["seed"] for j in report["jobs"]}, {7,17,31})
        self.assertTrue(all(j["preparation_status"] == "blocked" for j in report["jobs"]))
        receipt = load_json(next((self.root / "prepared/jobs").glob("*/execution-receipt.UNSIGNED.json")))
        self.assertFalse(receipt["approved"])
        self.assertEqual(training.checked_preparation(self.root / "prepared"), report)
        with self.assertRaisesRegex(ValueError, "blocked"):
            training.launch(self.root / "prepared", report["jobs"][0]["job_id"], "missing-receipt")

    def test_round_budget_duplicate_variants_and_seed_cherry_picking_fail_before_outputs(self):
        variants = [dict(v) for v in self.recipe["variants"]]
        bad_recipes = [{**self.recipe,"max_total_wall_seconds":100}, {**self.recipe,"seeds":[17]},
                       {**self.recipe,"variants":[variants[0],variants[0]]}]
        for index, value in enumerate(bad_recipes):
            write_json(self.recipe_path, value)
            with self.assertRaises(ValueError):
                training.prepare(self.recipe_path, self.root / f"bad{index}")
            self.assertFalse((self.root / f"bad{index}").exists())

    def test_component_baselines_cannot_use_different_fitting_or_development_inputs(self):
        for variant in self.recipe["variants"]:
            variant["manifest"] = "SYNTHETIC-not-a-real-manifest"
        write_json(self.recipe_path, self.recipe)
        with patch("linkerforge.pipeline.training._preflight", side_effect=[{"input_hashes":{"a":"1"}}, {"input_hashes":{"b":"2"}}]):
            with self.assertRaisesRegex(ValueError, "matched"):
                training.prepare(self.recipe_path, self.root / "mismatched")
        self.assertFalse((self.root / "mismatched").exists())

    def test_changed_source_or_job_config_invalidates_prepared_plan(self):
        report = training.prepare(self.recipe_path, self.root / "prepared")
        config = self.root / "prepared" / report["jobs"][0]["config_path"]
        config.write_text("{}")
        with self.assertRaisesRegex(ValueError, "configuration"):
            training.checked_preparation(self.root / "prepared")
        with patch("linkerforge.pipeline.training.source_identity", return_value={}):
            with self.assertRaisesRegex(ValueError, "source identity"):
                training.checked_preparation(self.root / "prepared")

    def ready(self):
        self.recipe["review_reference"] = "SYNTHETIC mock review only"
        self.recipe["variants"] = [self.recipe["variants"][0]]
        self.recipe["variants"][0]["manifest"] = "not-a-real-dataset"
        write_json(self.recipe_path, self.recipe)
        fake = {"input_hashes":{"SYNTHETIC":"fixture-hash"}}
        with patch("linkerforge.pipeline.training._preflight", return_value=fake):
            prepared = training.prepare(self.recipe_path, self.root / "prepared")
        job = prepared["jobs"][0]
        receipt = self.root / "receipt.json"
        write_json(receipt, {"approved":True,"institution":"SYNTHETIC mock", "review_reference":"SYNTHETIC", "host":training.platform.node(),
                             "environment":training.environment(), "config_sha256":job["config_sha256"], "input_hashes":fake["input_hashes"]})
        return prepared, job, receipt, fake

    def test_mock_dispatch_failure_retains_logs_and_cannot_silently_retry(self):
        prepared, job, receipt, fake = self.ready()
        lock = self.root / "host-lock"
        class Child:
            pid, returncode = 12345, 2
            def wait(self, timeout=None): return self.returncode
            def poll(self): return self.returncode
        with patch("linkerforge.pipeline.training._preflight", return_value=fake), patch("linkerforge.pipeline.training.lock_path", return_value=lock), patch("subprocess.Popen", return_value=Child()) as spawn:
            result = training.launch(self.root / "prepared", job["job_id"], receipt, "cpu")
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["child_pid"], 12345)
            self.assertGreaterEqual(result["measured_wall_seconds"], 0)
            self.assertTrue((self.root / "prepared" / job["output"] / "stdout.log").exists())
            self.assertFalse(lock.exists())
            self.assertEqual(spawn.call_args.args[0][0], training.sys.executable)
            with self.assertRaisesRegex(ValueError, "already attempted"):
                training.launch(self.root / "prepared", job["job_id"], receipt, "cpu")

    def test_host_lock_and_unsigned_or_changed_receipt_prevent_spawn(self):
        _, job, receipt, fake = self.ready()
        lock = self.root / "host-lock"
        lock.write_text("another actual job must be investigated")
        with patch("linkerforge.pipeline.training._preflight", return_value=fake), patch("linkerforge.pipeline.training.lock_path", return_value=lock), patch("subprocess.Popen") as spawn:
            with self.assertRaises(FileExistsError):
                training.launch(self.root / "prepared", job["job_id"], receipt, "cpu")
            spawn.assert_not_called()
            value = load_json(receipt)
            value["approved"] = False
            write_json(receipt, value)
            with self.assertRaisesRegex(ValueError, "receipt"):
                training.launch(self.root / "prepared", job["job_id"], receipt, "cpu")
            spawn.assert_not_called()
            self.assertTrue(lock.exists())

    def test_timeout_kills_only_owned_child_and_records_failed_attempt(self):
        _, job, receipt, fake = self.ready()
        class Child:
            pid, returncode, killed = 12345, None, False
            def wait(self, timeout=None):
                if timeout is not None: raise subprocess.TimeoutExpired("mock",timeout)
                self.returncode = -9
                return self.returncode
            def poll(self): return self.returncode
            def kill(self): self.killed = True
        child = Child()
        with patch("linkerforge.pipeline.training._preflight", return_value=fake), patch("linkerforge.pipeline.training.lock_path", return_value=self.root / "lock"), patch("subprocess.Popen", return_value=child):
            result = training.launch(self.root / "prepared", job["job_id"], receipt, "cpu")
        self.assertTrue(child.killed)
        self.assertEqual(result["failure"], "hard_wall_ceiling_reached")
        self.assertEqual(result["exit_code"], -9)

    def test_race_with_an_existing_output_cannot_overwrite_another_attempt(self):
        _, job, receipt, fake = self.ready()
        target = self.root / "prepared" / job["output"]
        actual_open = training.os.open
        def racing_open(*args):
            target.mkdir(parents=True)
            write_json(target / "dispatch.json", {"status":"SYNTHETIC-existing-attempt"})
            return actual_open(*args)
        with patch("linkerforge.pipeline.training._preflight", return_value=fake), patch("linkerforge.pipeline.training.lock_path", return_value=self.root / "lock"), patch("linkerforge.pipeline.training.os.open", side_effect=racing_open):
            with self.assertRaises(FileExistsError):
                training.launch(self.root / "prepared", job["job_id"], receipt, "cpu")
        self.assertEqual(load_json(target / "dispatch.json"), {"status":"SYNTHETIC-existing-attempt"})

    def test_development_command_plan_keeps_failed_or_pending_seeds_explicit(self):
        prepared, _, _, _ = self.ready()
        result = training.benchmark_commands(self.root / "prepared", .25)
        self.assertEqual(len(result["blockers"]), 3)
        self.assertEqual(result["commands"], [])
        for job in prepared["jobs"]:
            target = self.root / "prepared" / job["output"]
            checkpoint = target / "training" / "step-001000"
            checkpoint.mkdir(parents=True)
            (checkpoint / "model.safetensors").write_bytes(b"SYNTHETIC mocked checkpoint bytes, not weights")
            write_json(checkpoint / "model.json", {"state_sha256":file_sha256(checkpoint / "model.safetensors")})
            write_json(checkpoint / "training.json", {"model_metadata_sha256":file_sha256(checkpoint / "model.json"),
                "identity":{"config_sha256":job["config_sha256"],"input_hashes":job["input_hashes"]}})
            write_json(target / "training" / "run.json", {"status":"completed","checkpoint":str(checkpoint),"completed_steps":1000,
                "config_sha256":job["config_sha256"],"input_hashes":job["input_hashes"]})
            write_json(target / "dispatch.json", {"status":"completed"})
        result = training.benchmark_commands(self.root / "prepared", .25)
        self.assertEqual(result["status"], "prepared_not_executed")
        self.assertEqual(len(result["commands"]), 1)
        argv = result["commands"][0]["argv"]
        self.assertEqual(argv.count("--checkpoint"), 3)
        self.assertIn("benchmark-development", argv)
        self.assertFalse(result["benchmark_executed"])
        (checkpoint / "model.safetensors").write_bytes(b"tampered")
        self.assertEqual(training.benchmark_commands(self.root / "prepared", .25)["status"], "blocked")

    def test_source_cli_writes_real_template_workflow_report_and_refuses_overwrite(self):
        request, library, output = self.root / "request.json", self.root / "library.json", self.root / "output.json"
        write_json(request, {"format":"fusion-design-input.v0", "kind":"synthetic_software_fixture", "plans":[asdict(route())]})
        write_json(library, fixture_library())
        with patch("builtins.print"):
            self.assertEqual(main(["design","--input",str(request),"--library",str(library),"--output",str(output)]), 0)
        self.assertEqual(load_json(output)["input_sha256"], file_sha256(request))
        self.assertTrue(load_json(output)["synthetic_software_fixture"])
        with self.assertRaisesRegex(ValueError, "overwrite"):
            main(["design","--input",str(request),"--library",str(library),"--output",str(output)])


if __name__ == "__main__":
    unittest.main()
