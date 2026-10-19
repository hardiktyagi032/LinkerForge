"""Synthetic software fixtures only: no biological training/evaluation evidence."""
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch

from linkerforge.generation.baselines import edit_distance, template_baselines
from linkerforge.generation.cli import main, smoke_dataset
from linkerforge.generation.constraints import candidate_flags, generate
from linkerforge.generation.contracts import AMINO_ACIDS, DesignRequest, GeneratorConfig, TrainingExample, canonical_hash
from linkerforge.generation.data import file_sha256, load_json, preflight
from linkerforge.generation.engine import TrainConfig, evaluate_development, train, write_json
from linkerforge.generation.model import LinkerInfiller, LoRAProjection
from linkerforge.generation.tokenizer import FIMTokenizer
from linkerforge.generation.templates import template_candidates


def tiny(dropout=0.):
    return GeneratorConfig(max_linker_length=16, flank_residues=8, max_positions=64,
                           hidden_size=16, layers=1, heads=4, dropout=dropout)


def example(linker="GSGS", identity="one", **request):
    design = DesignRequest("ACDEF", "GHIKL", len(linker), **request)
    return TrainingExample(identity, design, linker, identity,
                           hashlib.sha256((design.domain_a + linker + design.domain_b).encode()).hexdigest(),
                           (identity,), "synthetic_software_fixture", True)


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        torch.manual_seed(123)

    def tearDown(self):
        self.temp.cleanup()

    def test_request_rejects_unknown_fields_and_topology(self):
        for change in ({"length": True}, {"attachment_b": True}, {"domain_a": "AX"},
                       {"topology": "insertion"}, {"attachment_a": 2}, {"cleavage": "noncleavable"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                DesignRequest.from_dict({"domain_a": "ACD", "domain_b": "EFG", "length": 4, **change})
        with self.assertRaises(ValueError):
            DesignRequest.from_dict({"domain_a": "ACD", "domain_b": "EFG", "length": 4, "target": "GGGG"})

    def test_composite_cassette_and_conflict(self):
        request = DesignRequest("ACD", "EFG", 12, rigidity="rigid", cleavage="cleavable",
                                motif="GS", motif_source="SYNTHETIC-test-only", cassette_flank=2)
        self.assertEqual(request.segments(), [{"start": 1, "end": 6, "design_intent": "rigid_spacer"},
                                             {"start": 7, "end": 12, "design_intent": "flexible_protease_cassette"}])
        with self.assertRaises(ValueError):
            replace(request, length=4, motif_start=None)
        with self.assertRaises(ValueError):
            replace(request, allowed_amino_acids="A")
        with self.assertRaises(ValueError):
            replace(request, motif_source="")

    def test_prompt_only_public_context_no_target_or_identity(self):
        config = tiny()
        tokenizer = FIMTokenizer(16)
        first = example("GSGS")
        other = replace(first, linker="SSGG", record_id="secret-target-id", source_id="other")
        batch = tokenizer.batch([first, other], config)
        prompt = tokenizer.prompt(first.request, config)
        self.assertTrue(torch.equal(batch["input_ids"][0, :len(prompt)], batch["input_ids"][1, :len(prompt)]))
        self.assertEqual(tokenizer.prompt(first.request, config)[-1], tokenizer.ids["<middle>"])

    def test_cropping_retains_attachment_adjacent_flanks(self):
        request = DesignRequest("A" * 50 + "CDE", "FGH" + "I" * 50, 8)
        config = replace(tiny(), max_positions=21)
        tokenizer = FIMTokenizer(16)
        tokens = [tokenizer.tokens[i] for i in tokenizer.prompt(request, config)]
        self.assertEqual(tokens[2:5], list("CDE"))
        self.assertEqual(tokens[6:9], list("FGH"))
        self.assertLessEqual(len(tokens) + request.length, config.max_positions)
        with self.assertRaises(ValueError):
            tokenizer.prompt(request, replace(config, max_positions=15))

    def test_labels_mask_prompt_padding_and_supplied_motif(self):
        config = tiny()
        tokenizer = FIMTokenizer(16)
        ex = example("AGSA", cleavage="cleavable", motif="GS", motif_start=1, motif_source="SYNTHETIC")
        batch = tokenizer.batch([ex, example("GG")], config)
        start = len(tokenizer.prompt(ex.request, config))
        self.assertTrue((batch["labels"][0, :start] == -100).all())
        self.assertEqual(batch["labels"][0, start:start+4].tolist(), [0, -100, -100, 0])
        self.assertTrue((batch["labels"][~batch["attention_mask"]] == -100).all())
        with self.assertRaises(ValueError):
            tokenizer.batch([example("GS", cleavage="cleavable", motif="GS", motif_source="SYNTHETIC")], config)

    def test_causal_mask_does_not_read_future_linker_residues(self):
        model = LinkerInfiller(tiny()).eval()
        first, other = example("GSGS"), example("GSSA")
        batch = model.tokenizer.batch([first, other], model.config)
        logits = model(**batch)["logits"]
        start = len(model.tokenizer.prompt(first.request, model.config))
        torch.testing.assert_close(logits[0, :start+2], logits[1, :start+2], rtol=0, atol=0)
        self.assertFalse(torch.equal(logits[0, -1], logits[1, -1]))

    def test_query_balanced_loss_and_padding_invariance(self):
        model = LinkerInfiller(tiny()).eval()
        examples = [example("GS"), example("SSGGSS")]
        together = model(**model.tokenizer.batch(examples, model.config))
        separate = [model(**model.tokenizer.batch([e], model.config))["loss"] for e in examples]
        torch.testing.assert_close(together["loss"], torch.stack(separate).mean())
        self.assertEqual(int(together["target_residues"]), 8)
        self.assertTrue(torch.isfinite(together["loss"]))

    def test_suffix_context_reaches_linker_logits(self):
        model = LinkerInfiller(tiny()).eval()
        first = example()
        other = replace(first, request=replace(first.request, domain_b="YYYYY"))
        batch = model.tokenizer.batch([first, other], model.config)
        index = len(model.tokenizer.prompt(first.request, model.config)) - 1
        self.assertFalse(torch.equal(model(**batch)["logits"][0, index], model(**batch)["logits"][1, index]))

    def test_generation_exact_length_alphabet_motif_and_seed(self):
        model = LinkerInfiller(tiny()).train()
        request = DesignRequest("ACD", "EFG", 6, cleavage="cleavable", motif="GS", motif_start=2,
                                motif_source="SYNTHETIC", allowed_amino_acids="AGS")
        first = generate(model, request, count=2, max_attempts=3, seed=42)
        self.assertEqual(first, generate(model, request, count=2, max_attempts=3, seed=42))
        self.assertTrue(model.training)
        for candidate in first["candidates"]:
            self.assertEqual(len(candidate["linker_sequence"]), 6)
            self.assertEqual(candidate["linker_sequence"][2:4], "GS")
            self.assertFalse(set(candidate["linker_sequence"]) - set("AGS"))
            self.assertEqual(candidate["scored_free_residues"], 4)
            self.assertFalse(candidate["folding_expression_function_validated"])

    def test_all_rejections_and_duplicates_retain_attempts(self):
        model = LinkerInfiller(tiny())
        request = DesignRequest("ACD", "EFG", 4, allowed_amino_acids="A", forbidden_motifs=["A"])
        result = generate(model, request, count=2, max_attempts=3)
        self.assertEqual(result["returned"], 0)
        self.assertEqual(len(result["attempts"]), 3)
        self.assertTrue(all(row["reasons"] == ["known_forbidden_motif_at_junction"] for row in result["attempts"]))
        result = generate(model, replace(request, forbidden_motifs=()), count=2, max_attempts=3)
        self.assertEqual(result["returned"], 1)
        self.assertEqual(result["attempts"][2]["reasons"], ["duplicate"])

    def test_new_junction_motif_screen_does_not_reject_old_domain_motif(self):
        request = DesignRequest("AAC", "EFG", 2, forbidden_motifs=("AA",))
        self.assertEqual(candidate_flags(request, "GS"), [])
        self.assertIn("known_forbidden_motif_at_junction", candidate_flags(replace(request, domain_a="ACA"), "AG"))

    def test_native_checkpoint_roundtrip_and_tampering(self):
        model = LinkerInfiller(tiny()).eval()
        batch = model.tokenizer.batch([example()], model.config)
        path = self.root / "model"
        model.save(path)
        restored = LinkerInfiller.load(path).eval()
        torch.testing.assert_close(model(**batch)["logits"], restored(**batch)["logits"], rtol=0, atol=0)
        with (path / "model.safetensors").open("ab") as handle:
            handle.write(b"tamper")
        with self.assertRaisesRegex(ValueError, "identity changed"):
            LinkerInfiller.load(path)

    def test_lora_updates_residual_with_frozen_base(self):
        layer = LoRAProjection(torch.nn.Linear(4, 5), rank=2, alpha=4)
        before = layer.base.weight.detach().clone()
        optimizer = torch.optim.AdamW([p for p in layer.parameters() if p.requires_grad], lr=.01)
        layer(torch.randn(3, 4)).square().mean().backward()
        self.assertIsNone(layer.base.weight.grad)
        self.assertGreater(float(layer.b.grad.abs().sum()), 0)
        optimizer.step()
        torch.testing.assert_close(before, layer.base.weight, rtol=0, atol=0)

    def test_no_adapters_on_random_native_backbone(self):
        with self.assertRaises(ValueError):
            LinkerInfiller(replace(tiny(), lora_rank=2))

    def test_training_only_baselines_and_property_eligibility(self):
        first, second = example("GSGS", "a", rigidity="flexible"), example("AAAA", "b", rigidity="rigid")
        result = template_baselines([first, second], first.request)
        self.assertEqual(result["length_matched_frequency"], "GSGS")
        self.assertEqual(result["eligible_training_templates"], 1)
        self.assertIsNone(template_baselines([first], replace(first.request, length=5))["training_only_context_retrieval"])
        self.assertEqual(edit_distance("GS", "GGSS"), 2)

    def mutate_split(self, manifest, split, mutate):
        data = load_json(manifest)
        path = manifest.parent / data["splits"][split]["path"]
        rows = [json.loads(row) for row in path.read_text().splitlines()]
        mutate(rows)
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        data["splits"][split]["sha256"] = file_sha256(path)
        write_json(manifest, data)

    def test_preflight_hashes_and_synthetic_mode_isolation(self):
        manifest = smoke_dataset(self.root / "data")
        self.assertEqual(preflight(manifest, True)["counts"], {"train": 2, "development": 1})
        with self.assertRaises(ValueError):
            preflight(manifest)
        (manifest.parent / "train.jsonl").write_text("changed")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            preflight(manifest, True)

    def test_family_cross_split_is_rejected(self):
        manifest = smoke_dataset(self.root / "data")
        self.mutate_split(manifest, "development", lambda rows: rows[0].update(family_ids=["SYNTHETIC-train-0"]))
        with self.assertRaisesRegex(ValueError, "crosses"):
            preflight(manifest, True)

    def test_duplicate_actual_sequence_is_rejected_despite_changed_source_hash(self):
        manifest = smoke_dataset(self.root / "data")
        rows = [json.loads(row) for row in (manifest.parent / "train.jsonl").read_text().splitlines()]
        self.mutate_split(manifest, "development", lambda target: target[0].update(request=rows[0]["request"], linker=rows[0]["linker"]))
        with self.assertRaisesRegex(ValueError, "crosses"):
            preflight(manifest, True)

    def test_manifest_path_traversal_is_rejected(self):
        manifest = smoke_dataset(self.root / "data")
        value = load_json(manifest)
        value["splits"]["train"]["path"] = "../outside.jsonl"
        (self.root / "outside.jsonl").write_text("{}"); write_json(manifest, value)
        with self.assertRaises(ValueError):
            preflight(manifest, True)

    def scientific_manifest(self):
        # Still invented records: this helper tests review-gate logic, not a dataset.
        manifest = smoke_dataset(self.root / "data")
        for split in ("train", "development"):
            self.mutate_split(manifest, split, lambda rows: [row.update(evidence_tier="natural_observation") for row in rows])
        value = load_json(manifest)
        value.update(kind="scientific_dataset", review={"approved": True, "reviewer": "fixture", "reference": "fixture-only"})
        registry = manifest.parent / "registry.json"
        write_json(registry, {"format": "sequence-exclusion-registry.v1", "records": [
            {"source_id": "protected-fixture", "sequence_sha256": "f"*64, "family_ids": ["protected-family"]}]})
        value["benchmark_registries"] = [{"name": "protected", "path": registry.name, "sha256": file_sha256(registry)}]
        audit = manifest.parent / "audit.json"
        write_json(audit, {"passed": True, "method": "fixture-not-real-homology-audit", "review_reference": "fixture",
                           "split_sha256s": {key: row["sha256"] for key, row in value["splits"].items()},
                           "benchmark_registry_sha256s": {"protected": file_sha256(registry)}})
        value["split_audit"] = {"path": audit.name, "sha256": file_sha256(audit)}
        write_json(manifest, value)
        return manifest

    def test_scientific_review_audit_and_execution_gate(self):
        manifest = self.scientific_manifest()
        self.assertFalse(preflight(manifest)["synthetic"])
        with patch("linkerforge.generation.engine.LinkerInfiller") as constructor:
            with self.assertRaisesRegex(ValueError, "execution receipt"):
                train(manifest, TrainConfig(tiny(), max_steps=1), self.root / "run")
            constructor.assert_not_called()
        value = load_json(manifest)
        value["review"]["approved"] = False
        write_json(manifest, value)
        with self.assertRaisesRegex(ValueError, "review"):
            preflight(manifest)

    def test_registry_collision_labels_and_stale_audit_fail(self):
        manifest = self.scientific_manifest()
        value = load_json(manifest)
        registry = manifest.parent / "registry.json"
        for change in ({"family_ids": ["SYNTHETIC-train-0"]}, {"labels": [1]}, {"source_id": "new-protected"}):
            with self.subTest(change=change):
                row = {"source_id": "protected-fixture", "sequence_sha256": "f"*64, "family_ids": ["protected-family"], **change}
                write_json(registry, {"format": "sequence-exclusion-registry.v1", "records": [row]})
                value["benchmark_registries"][0]["sha256"] = file_sha256(registry)
                write_json(manifest, value)
                with self.assertRaises(ValueError):
                    preflight(manifest)

    def test_missing_manifest_fails_before_model_load(self):
        with patch("linkerforge.generation.engine.LinkerInfiller") as constructor:
            with self.assertRaises(FileNotFoundError):
                train(self.root / "missing", TrainConfig(tiny()), self.root / "run")
            constructor.assert_not_called()

    def test_exact_optimizer_resume_with_dropout(self):
        manifest = smoke_dataset(self.root / "data")
        config = TrainConfig(tiny(.2), max_steps=4, batch_size=1, checkpoint_every=2, cpu_threads=1)
        continuous = train(manifest, config, self.root / "continuous", synthetic=True)
        partial = train(manifest, config, self.root / "partial", synthetic=True, stop_after=2)
        resumed = train(manifest, config, self.root / "resumed", synthetic=True, resume=partial["checkpoint"])
        full_model = LinkerInfiller.load(continuous["checkpoint"])
        resumed_model = LinkerInfiller.load(resumed["checkpoint"])
        for name, tensor in full_model.state_dict().items():
            torch.testing.assert_close(tensor, resumed_model.state_dict()[name], rtol=0, atol=0)
        self.assertEqual(load_json(self.root / "continuous/history.json"), load_json(self.root / "resumed/history.json"))
        self.assertEqual(resumed["completed_steps"], 4)

    def test_resume_config_mismatch_retains_failure_record(self):
        manifest = smoke_dataset(self.root / "data")
        config = TrainConfig(tiny(), max_steps=2, checkpoint_every=1, cpu_threads=1)
        job = train(manifest, config, self.root / "first", synthetic=True, stop_after=1)
        with self.assertRaisesRegex(ValueError, "Resume requires"):
            train(manifest, replace(config, seed=18), self.root / "second", synthetic=True, resume=job["checkpoint"])
        self.assertEqual(load_json(self.root / "second/run.json")["status"], "failed")

    def test_synthetic_ceiling_and_output_overwrite(self):
        manifest = smoke_dataset(self.root / "data")
        with self.assertRaisesRegex(ValueError, "Synthetic smoke"):
            train(manifest, TrainConfig(tiny(), max_steps=9), self.root / "run", synthetic=True)
        self.assertFalse((self.root / "run").exists())
        (self.root / "existing").mkdir()
        with self.assertRaises(FileExistsError):
            train(manifest, TrainConfig(tiny(), max_steps=1), self.root / "existing", synthetic=True)

    def test_smoke_cli_writes_labelled_artifacts(self):
        with patch("builtins.print"):
            self.assertEqual(main(["smoke", "--output", str(self.root / "smoke")]), 0)
        result = load_json(self.root / "smoke/smoke.json")
        self.assertTrue(result["synthetic_software_fixture"])
        self.assertIsNone(result["biological_performance"])
        self.assertEqual(result["run"]["completed_steps"], 3)
        report = load_json(self.root / "smoke/development-software-only.json")
        self.assertEqual(set(report["summary"]), {"infiller", "length_matched_frequency", "training_only_context_retrieval"})
        self.assertTrue(all(row["attempted_records"] == 1 for row in report["summary"].values()))

    def make_local_hf(self, incompatible=False):
        from tokenizers import Tokenizer, models, pre_tokenizers
        from transformers import GPT2Config, GPT2LMHeadModel, PreTrainedTokenizerFast
        vocab = {aa: i for i, aa in enumerate(AMINO_ACIDS)} | {"[UNK]": 20, "[BOS]": 21, "[EOS]": 22}
        if incompatible:
            vocab.pop("G")
        tok = Tokenizer(models.WordLevel(vocab, unk_token="[UNK]"))
        tok.pre_tokenizer = pre_tokenizers.Split("", behavior="isolated")
        tokenizer = PreTrainedTokenizerFast(tokenizer_object=tok, unk_token="[UNK]", bos_token="[BOS]", eos_token="[EOS]")
        config = GPT2Config(vocab_size=23, n_positions=64, n_embd=16, n_layer=1, n_head=4,
                            bos_token_id=21, eos_token_id=22, resid_pdrop=0., attn_pdrop=0., embd_pdrop=0.)
        path = self.root / ("hf-bad" if incompatible else "hf")
        GPT2LMHeadModel(config).save_pretrained(path)
        tokenizer.save_pretrained(path)
        return replace(tiny(), backend="hf_causal_lm", base_model=str(path), revision="local",
                       lora_rank=2, lora_alpha=4., lora_targets=("c_attn", "c_proj"))

    def test_hf_frozen_backbone_adapter_training_and_reload(self):
        config = self.make_local_hf()
        model = LinkerInfiller(config)
        frozen = {name: p.detach().clone() for name, p in model.named_parameters() if not p.requires_grad}
        self.assertTrue(model.lora_modules)
        batch = model.tokenizer.batch([example()], config)
        optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=.01)
        model(**batch)["loss"].backward(); optimizer.step()
        for name, parameter in model.named_parameters():
            if name in frozen:
                torch.testing.assert_close(parameter, frozen[name], rtol=0, atol=0)
                self.assertIsNone(parameter.grad)
        model.eval()
        model.save(self.root / "adapter")
        restored = LinkerInfiller.load(self.root / "adapter").eval()
        torch.testing.assert_close(model(**batch)["logits"], restored(**batch)["logits"], rtol=0, atol=0)
        keys = load_json(self.root / "adapter/model.json")["state_keys"]
        self.assertFalse(any("wte.weight" in name for name in keys))

    def test_hf_tokenizer_and_revision_checks(self):
        with self.assertRaisesRegex(ValueError, "canonical residue"):
            LinkerInfiller(self.make_local_hf(incompatible=True))
        with self.assertRaisesRegex(ValueError, "immutable"):
            LinkerInfiller(replace(tiny(), backend="hf_causal_lm", base_model="no-download-fixture", revision="main"))

    def test_hf_local_base_mutation_blocks_reload(self):
        config = self.make_local_hf()
        LinkerInfiller(config).save(self.root / "adapter")
        with (Path(config.base_model) / "config.json").open("a") as handle:
            handle.write(" ")
        with self.assertRaisesRegex(ValueError, "identity changed"):
            LinkerInfiller.load(self.root / "adapter")

    def test_hf_single_letter_tokens_do_not_make_bpe_residue_compatible(self):
        from tokenizers import Tokenizer, models
        from transformers import PreTrainedTokenizerFast
        config = self.make_local_hf()
        vocab = {aa: i for i, aa in enumerate(AMINO_ACIDS)} | {"[UNK]": 20, "GS": 21}
        tokenizer = PreTrainedTokenizerFast(tokenizer_object=Tokenizer(models.BPE(vocab, [("G", "S")], unk_token="[UNK]")), unk_token="[UNK]")
        tokenizer.save_pretrained(config.base_model)
        with self.assertRaisesRegex(ValueError, "merges residues"):
            LinkerInfiller(config)

    def test_library_nulls_unknowns_and_substitutions_are_explicit(self):
        library = {"library_id": "linker_property_library.v1", "sources": {"fixture": {"citation": "INVENTED SOFTWARE FIXTURE"}},
                   "entries": [{"entry_id": "a", "sequence": None, "excluded_from_model": True},
                               {"entry_id": "b", "sequence": "AAAA", "source_key": "fixture", "source_locator": "fixture-row",
                                "rigidity": {"label": "flexible"}, "cleavability": {"label": "unassigned"}}]}
        request = DesignRequest("ACD", "EFG", 4, rigidity="flexible", cleavage="cleavable", motif="GS", motif_start=1, motif_source="SYNTHETIC")
        self.assertEqual(template_candidates(library, request)["returned"], 0)
        result = template_candidates(library, request, max_substitutions=2)
        self.assertEqual(result["candidates"][0]["linker_sequence"], "AGSA")
        self.assertEqual(len(result["candidates"][0]["substitutions"]), 2)
        self.assertFalse(result["candidates"][0]["function_validated"])
        request = DesignRequest("ACD", "EFG", 4, cleavage="no_known_motif")
        self.assertEqual(template_candidates(library, request)["returned"], 0)


if __name__ == "__main__":
    unittest.main()
