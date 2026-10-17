"""No data/model download occurs implicitly. Run --help for bounded commands."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from .contracts import DesignRequest, GeneratorConfig
from .constraints import generate
from .data import file_sha256, load_json, preflight
from .engine import TrainConfig, environment, evaluate_development, train, write_json
from .model import LinkerInfiller
from .templates import template_candidates


def smoke_dataset(directory):
    """Invented strings for software verification only, never biological evidence."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    records = {"train": [("ACDEF", "GHIKL", "GSGS"), ("MNPQR", "STVWY", "SGSG")],
               "development": [("VVVAC", "YYYST", "GGSS")]}
    entries = {}
    for split, values in records.items():
        rows = []
        for i, (a, b, linker) in enumerate(values):
            identity = f"SYNTHETIC-{split}-{i}"
            rows.append({"record_id": identity, "request": asdict(DesignRequest(a, b, len(linker))),
                         "linker": linker, "source_id": identity,
                         "source_sha256": hashlib.sha256((a + linker + b).encode()).hexdigest(),
                         "family_ids": [identity], "evidence_tier": "synthetic_software_fixture", "training_eligible": True})
        path = root / f"{split}.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        entries[split] = {"path": path.name, "sha256": file_sha256(path)}
    manifest = root / "manifest.json"
    write_json(manifest, {"format": "fusion-generator-dataset.v0", "dataset_id": "SYNTHETIC-software-only-v1",
                          "kind": "synthetic_software_fixture", "splits": entries})
    return manifest


def run_smoke(output):
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    manifest = smoke_dataset(root / "fixtures")
    config = TrainConfig(GeneratorConfig(max_linker_length=16, flank_residues=8, max_positions=64,
                                        hidden_size=32, layers=1, heads=4, dropout=.1),
                         max_steps=3, batch_size=2, checkpoint_every=1, cpu_threads=1, max_wall_seconds=120)
    write_json(root / "config.json", asdict(config))
    job = train(manifest, config, root / "training", synthetic=True)
    model = LinkerInfiller.load(job["checkpoint"])
    result = evaluate_development(model, preflight(manifest, synthetic=True))
    write_json(root / "development-software-only.json", result)
    summary = {"synthetic_software_fixture": True, "biological_performance": None,
               "purpose": "Optimizer/checkpoint/generation/baseline wiring only; invented nonbiological strings.",
               "run": job, "generation_attempts": len(result["rows"][0]["generation"]["attempts"]),
               "generated_candidates": result["summary"]["infiller"]["valid_calls"]}
    write_json(root / "smoke.json", summary)
    return summary


def parser():
    result = argparse.ArgumentParser(description="LinkerForge FIM generator: known-length tandem sequence proposals, no fusion-success claims")
    commands = result.add_subparsers(dest="command", required=True)
    smoke = commands.add_parser("smoke", help="Three CPU updates on invented software fixtures; no network")
    smoke.add_argument("--output", required=True)
    check = commands.add_parser("preflight", help="Check dataset hashes/reviews/family exclusions before loading a model")
    check.add_argument("--manifest", required=True)
    check.add_argument("--synthetic-smoke", action="store_true")
    fit = commands.add_parser("train")
    fit.add_argument("--manifest", required=True)
    fit.add_argument("--config", required=True)
    fit.add_argument("--output", required=True)
    fit.add_argument("--device", default="cpu")
    fit.add_argument("--resume")
    fit.add_argument("--execution-receipt", help="Required for scientific training; exact host/environment/config/input review")
    fit.add_argument("--synthetic-smoke", action="store_true")
    sample = commands.add_parser("generate")
    sample.add_argument("--checkpoint", required=True)
    sample.add_argument("--request", required=True)
    sample.add_argument("--output", required=True)
    sample.add_argument("--seed", type=int, default=17)
    sample.add_argument("--count", type=int, default=8)
    sample.add_argument("--max-attempts", type=int, default=32)
    sample.add_argument("--temperature", type=float, default=1.)
    sample.add_argument("--top-k", type=int, default=20)
    sample.add_argument("--device", default="cpu")
    evaluate = commands.add_parser("evaluate-development", help="One-candidate known-length reconstruction; no blind evaluation")
    evaluate.add_argument("--manifest", required=True)
    evaluate.add_argument("--checkpoint", required=True)
    evaluate.add_argument("--output", required=True)
    evaluate.add_argument("--seed", type=int, default=17)
    evaluate.add_argument("--device", default="cpu")
    evaluate.add_argument("--synthetic-smoke", action="store_true")
    commands.add_parser("environment", help="Print environment identity for future reviewed execution")
    templates = commands.add_parser("templates", help="Source-library baseline with bounded explicit cassette substitutions")
    templates.add_argument("--library", required=True)
    templates.add_argument("--request", required=True)
    templates.add_argument("--output", required=True)
    templates.add_argument("--count", type=int, default=8)
    templates.add_argument("--max-substitutions", type=int, default=0)
    return result


def checkpoint_identity(path):
    state = load_json(Path(path) / "training.json")
    if file_sha256(Path(path) / "model.json") != state["model_metadata_sha256"]:
        raise ValueError("Training/checkpoint metadata hash mismatch")
    return state["identity"]


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == "smoke":
        result = run_smoke(args.output)
    elif args.command == "environment":
        result = environment()
    elif args.command == "preflight":
        data = preflight(args.manifest, args.synthetic_smoke)
        result = {key: value for key, value in data.items() if key not in {"records", "manifest"}}
        result["training_authorized"] = False
    elif args.command == "train":
        result = train(args.manifest, TrainConfig.from_dict(load_json(args.config)), args.output,
                       synthetic=args.synthetic_smoke, device=args.device, resume=args.resume, execution=args.execution_receipt)
    elif args.command == "templates":
        if Path(args.output).exists():
            raise ValueError("Refusing to overwrite existing output")
        result = template_candidates(load_json(args.library), DesignRequest.from_dict(load_json(args.request)), args.count, args.max_substitutions)
        result.update(library_sha256=file_sha256(args.library), request_sha256=file_sha256(args.request))
        write_json(args.output, result)
    else:
        target = Path(args.output)
        if target.exists():
            raise ValueError("Refusing to overwrite existing output")
        identity = checkpoint_identity(args.checkpoint)
        if args.command == "evaluate-development":
            data = preflight(args.manifest, args.synthetic_smoke)
            if identity["input_hashes"] != data["input_hashes"] or identity["synthetic_software_fixture"] != data["synthetic"]:
                raise ValueError("Development evaluation requires the exact training/development manifest and mode")
        model = LinkerInfiller.load(args.checkpoint, args.device)
        if args.command == "generate":
            request = DesignRequest.from_dict(load_json(args.request))
            result = generate(model, request, args.count, args.max_attempts, args.seed, args.temperature, args.top_k)
            result.update(request=request.to_dict(), checkpoint=str(Path(args.checkpoint).resolve()),
                          synthetic_software_fixture=identity["synthetic_software_fixture"],
                          model_metadata_sha256=file_sha256(Path(args.checkpoint) / "model.json"))
        else:
            result = evaluate_development(model, data, seed=args.seed, device=args.device)
        write_json(target, result)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0
