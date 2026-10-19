"""Explicit local commands for components 2--5 software preparation only."""
import argparse
import json
from pathlib import Path

from linkerforge.attachment.plans import evaluate_geometry
from linkerforge.generation.cli import checkpoint_identity
from linkerforge.generation.contracts import strict_dataclass
from linkerforge.generation.data import checked_file, file_sha256, load_json
from linkerforge.generation.engine import write_json
from linkerforge.generation.model import LinkerInfiller
from linkerforge.geometry.structure import read_chain
from .design import DesignBudget, design
from .intake import review_candidate
from .routes import parse_plan
from .training import benchmark_commands, inspect, launch, prepare


def design_input(path):
    value = load_json(path)
    if (value.get("format") != "fusion-design-input.v0" or value.get("kind") not in {"synthetic_software_fixture", "unvalidated_design_request"}
            or set(value) - {"format", "kind", "plans", "domain_scores", "geometry_reports", "controls", "budget"}):
        raise ValueError("Expected private fusion-design-input.v0 interface")
    return value, [parse_plan(p) for p in value["plans"]]


def geometry_input(path, plans):
    path = Path(path).resolve()
    value = load_json(path)
    if value.get("format") != "fusion-geometry-input.v0" or set(value) != {"format", "plans", "budget"}:
        raise ValueError("Expected private geometry inputs with exact file hashes and sequence/PDB maps")
    expected = {p.plan_id: p for p in plans}
    if set(value["plans"]) != set(expected):
        raise ValueError("Geometry inputs must cover exactly the supplied plans")
    reports = {}
    for identity, entry in value["plans"].items():
        if set(entry) != {"a", "b"}:
            raise ValueError("Both domain structures required")
        chains, maps, sources = {}, {}, {}
        for domain, source in entry.items():
            if set(source) != {"file", "chain", "sequence_to_pdb"}:
                raise ValueError("File, chain and explicit residue mapping required")
            structure = checked_file(path.parent, source["file"])
            chains[domain] = read_chain(structure, source["chain"])
            raw = source["sequence_to_pdb"]
            if any(not isinstance(k, str) or not k.isdigit() or str(int(k)) != k for k in raw):
                raise ValueError("Canonical 1-based mapping keys required")
            maps[domain] = {int(k): v for k, v in raw.items()}
            sources[domain] = {"path": str(structure), "sha256": file_sha256(structure), "chain": source["chain"], "sequence_to_pdb": raw}
        report = evaluate_geometry(expected[identity], chains["a"], chains["b"], maps["a"], maps["b"], **value["budget"])
        report["structure_inputs"] = sources
        reports[identity] = report
    return reports


def parser():
    p = argparse.ArgumentParser(description="Design pipeline preparation: no detector, mining, data acquisition or implicit fitting")
    sub = p.add_subparsers(dest="command", required=True)
    d = sub.add_parser("design", help="Bounded sequence proposals from explicit plans, optional frozen scores/geometry/models")
    d.add_argument("--input", required=True)
    d.add_argument("--library")
    d.add_argument("--checkpoint")
    d.add_argument("--geometry-reports", help="Pinned output of assess-geometry")
    d.add_argument("--device", default="cpu")
    d.add_argument("--output", required=True)
    g = sub.add_parser("assess-geometry", help="Bounded common-placement solver on explicitly supplied structures")
    g.add_argument("--input", required=True)
    g.add_argument("--structures", required=True)
    g.add_argument("--output", required=True)
    c = sub.add_parser("review-candidate", help="Validate one supplied future mining output; remains training-ineligible")
    c.add_argument("--input", required=True)
    c.add_argument("--output", required=True)
    t = sub.add_parser("prepare-training", help="Write per-seed configs and unsigned receipts; never train")
    t.add_argument("--recipe", required=True)
    t.add_argument("--output", required=True)
    i = sub.add_parser("inspect-training", help="Show actual local dispatch ledger/lock; remote state remains unverified")
    i.add_argument("--prepared", required=True)
    r = sub.add_parser("run-training", help="One reviewed future job, hard timeout, no automatic retries")
    r.add_argument("--prepared", required=True)
    r.add_argument("--job-id", required=True)
    r.add_argument("--execution-receipt", required=True)
    r.add_argument("--device", default="cuda:0")
    b = sub.add_parser("benchmark-commands", help="Prepare development argv after all seeds/control jobs complete; never reveal a test")
    b.add_argument("--prepared", required=True)
    b.add_argument("--coverage-fraction", type=float)
    b.add_argument("--bootstrap-draws", type=int, default=200)
    b.add_argument("--seed", type=int, default=17)
    b.add_argument("--output", required=True)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if hasattr(args, "output") and Path(args.output).exists():
        raise ValueError("Refusing to overwrite existing evidence")
    if args.command == "review-candidate":
        result = review_candidate(load_json(args.input))
        result["input_file_sha256"] = file_sha256(args.input)
        write_json(args.output, result)
    elif args.command == "prepare-training":
        result = prepare(args.recipe, args.output)
    elif args.command == "inspect-training":
        result = inspect(args.prepared)
    elif args.command == "run-training":
        result = launch(args.prepared, args.job_id, args.execution_receipt, args.device)
    elif args.command == "benchmark-commands":
        result = benchmark_commands(args.prepared, args.coverage_fraction, args.bootstrap_draws, args.seed)
        write_json(args.output, result)
    else:
        value, plans = design_input(args.input)
        if args.command == "assess-geometry":
            result = {"format": "fusion-geometry-reports.v0", "reports": geometry_input(args.structures, plans),
                      "design_input_sha256": file_sha256(args.input), "geometry_input_sha256": file_sha256(args.structures),
                      "synthetic_software_fixture": value["kind"] == "synthetic_software_fixture"}
        else:
            geometry = value.get("geometry_reports", {})
            if args.geometry_reports:
                external = load_json(args.geometry_reports)
                if (external.get("format") != "fusion-geometry-reports.v0"
                        or external.get("design_input_sha256") != file_sha256(args.input) or geometry):
                    raise ValueError("Geometry report must bind this input; no conflicting embedded reports")
                geometry = external["reports"]
            model, identity = None, None
            if args.checkpoint:
                metadata = checkpoint_identity(args.checkpoint)
                identity = {"model_metadata_sha256": file_sha256(Path(args.checkpoint) / "model.json"),
                            "synthetic_software_fixture": metadata["synthetic_software_fixture"]}
                model = LinkerInfiller.load(args.checkpoint, args.device)
            result = design(plans, value.get("domain_scores", {}), geometry,
                            library=load_json(args.library) if args.library else None, model=model, model_identity=identity,
                            controls=value.get("controls"), budget=strict_dataclass(DesignBudget, value.get("budget", {})))
            result["input_sha256"] = file_sha256(args.input)
            result["synthetic_software_fixture"] |= value["kind"] == "synthetic_software_fixture"
            if args.library:
                result["library_file_sha256"] = file_sha256(args.library)
            if args.geometry_reports:
                result["geometry_reports_file_sha256"] = file_sha256(args.geometry_reports)
        write_json(args.output, result)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 2 if args.command == "run-training" and result["status"] != "completed" else 0
