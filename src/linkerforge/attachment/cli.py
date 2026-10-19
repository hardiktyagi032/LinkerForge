"""Training and development benchmark entry points for future reviewed data."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

import torch

from linkerforge.generation.data import file_sha256, load_json
from linkerforge.generation.engine import write_json
from .benchmark import compare
from .data import load_embedding, preflight, save_embedding, sequence_sha256
from .engine import SiteTrainConfig, score_domain, train
from .model import SiteModel, SiteModelConfig, TASKS
from .plans import AttachmentPlan, rank_plans


def make_smoke_dataset(root):
    """Invented features/labels for wiring tests, not a protein experiment."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    encoder = {"model_id": "SYNTHETIC-random-features", "revision": "SYNTHETIC", "weights_sha256": "SYNTHETIC", "layer": 0, "embedding_dim": 8}
    splits = {}
    for split, sequences in {"train": ["ACDE", "FGHI"], "development": ["KLMN", "PQRS"]}.items():
        rows = []
        for index, seq in enumerate(sequences):
            identity = f"SYNTHETIC-{split}-{index}"
            feature_path = root / f"{identity}.safetensors"
            save_embedding(feature_path, seq, torch.randn(len(seq), 8, generator=torch.Generator().manual_seed(17 + index + (10 if split == "development" else 0))), encoder, True)
            for task in TASKS:
                labels = [-1] * len(seq)
                if task == "internal_insertion":
                    labels[:2] = [index, 1-index]
                else:
                    labels[0 if task == "n_terminal_extension" else -1] = index
                rows.append({"record_id": identity + ":" + task, "sequence": seq, "source_id": identity,
                    "source_sha256": sequence_sha256(seq), "family_ids": [identity], "task": task,
                    "labels": labels, "evidence_tier": "synthetic_software_fixture", "label_reference": "invented-software-fixture-only",
                    "training_eligible": True, "embedding": {"path": feature_path.name, "sha256": file_sha256(feature_path)}})
        path = root / f"{split}.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        splits[split] = {"path": path.name, "sha256": file_sha256(path)}
    manifest = root / "manifest.json"
    write_json(manifest, {"format": "attachment-site-dataset.v0", "dataset_id": "SYNTHETIC-software-v1",
                          "kind": "synthetic_software_fixture", "encoder": encoder, "splits": splits})
    return manifest


def peer_predictions(path, data):
    value = load_json(path)
    if (value.get("format") != "attachment-peer-predictions.v0" or not value.get("method_id")
            or not value.get("version") or not value.get("review_reference") or not value.get("exposure_audit")
            or not value.get("position_mapping_reference") or value.get("input_modality") not in {"sequence", "sequence_plus_structure"}):
        raise ValueError("Peer scores require version, exposure, endpoint-position mapping and modality review")
    expected = {row.record_id: row for row in data["records"]["development"]}
    predictions = {}
    for row in value["records"]:
        if set(row) != {"record_id", "sequence_sha256", "task", "scores"} or row["record_id"] in predictions or row["record_id"] not in expected:
            raise ValueError("Peer records must identify the declared cohort without labels/duplicates")
        reference = expected[row["record_id"]]
        if row["sequence_sha256"] != sequence_sha256(reference.sequence) or row["task"] != reference.task:
            raise ValueError("Peer sequence/task alignment mismatch")
        predictions[row["record_id"]] = row["scores"]
    return predictions, {k: v for k, v in value.items() if k != "records"} | {"file_sha256": file_sha256(path)}


def benchmark_checkpoints(data, checkpoints, coverage_fraction=.1, bootstrap_draws=200, seed=17, device="cpu", peer_scores=None):
    methods, models = {}, {}
    for name, path in checkpoints.items():
        if name in {"uniform", "terminal_proximity"}:
            raise ValueError("Reserved baseline name")
        model, meta = SiteModel.load(path, device)
        if meta["identity"]["input_hashes"] != data["input_hashes"] or meta["identity"]["synthetic_software_fixture"] != data["synthetic"]:
            raise ValueError("Development benchmark requires exact fitting inputs/mode")
        methods[name] = {}
        for row in data["records"]["development"]:
            report = score_domain(model, row.sequence, data["embeddings"][row.record_id], meta)
            item = report["tasks"][row.task]
            if item["status"] == "untrained_no_score":
                methods[name][row.record_id] = None
            else:
                values = [0.] * len(row.sequence)
                for site in item["sites"]:
                    values[site["residue_position"]-1] = site["logit"]
                methods[name][row.record_id] = values
        models[name] = {"checkpoint": str(path), "metadata_sha256": file_sha256(Path(path) / "model.json"),
                        "seed": meta["identity"]["config"]["seed"], "trained_tasks": meta["trained_tasks"]}
    rows = data["records"]["development"]
    methods["uniform"] = {r.record_id: [0.] * len(r.sequence) for r in rows}
    methods["terminal_proximity"] = {r.record_id: [-min(i, len(r.sequence)-1-i) for i in range(len(r.sequence))] for r in rows}
    peers = {}
    for name, path in (peer_scores or {}).items():
        if name in methods:
            raise ValueError("Duplicate/reserved method name")
        methods[name], peers[name] = peer_predictions(path, data)
    result = compare(rows, methods, coverage_fraction, bootstrap_draws, seed)
    result.update(models=models, input_hashes=data["input_hashes"], synthetic_software_fixture=data["synthetic"],
                  scientific_performance=None if data["synthetic"] else "development_only_not_independent_evidence",
                  external_methods=peers,
                  external_comparator_status="Supplied frozen scores only; no external predictor was executed." if peers else "Official ProDomino and richer-input methods not run; no weights/scores supplied.")
    result["information_tracks"] = {name: peers[name]["input_modality"] if name in peers else "sequence" for name in methods}
    result["modality_warning"] = "Structure-assisted methods are labelled richer-input comparisons; do not claim matched sequence-only superiority from this joint report."
    return result


def smoke(output):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    manifest = make_smoke_dataset(out / "fixtures")
    config = SiteTrainConfig(SiteModelConfig(embedding_dim=8, hidden_size=16), max_steps=3, batch_size=6,
                             checkpoint_every=1, cpu_threads=1, max_wall_seconds=120)
    write_json(out / "config.json", asdict(config))
    job = train(manifest, config, out / "training", synthetic=True)
    data = preflight(manifest, True)
    result = benchmark_checkpoints(data, {"synthetic_mlp": job["checkpoint"]}, coverage_fraction=.5, bootstrap_draws=20)
    write_json(out / "benchmark-software-only.json", result)
    model, meta = SiteModel.load(job["checkpoint"])
    row = data["records"]["development"][0]
    scores = score_domain(model, row.sequence, data["embeddings"][row.record_id], meta)
    write_json(out / "domain-score-software-only.json", scores)
    record = {"synthetic_software_fixture": True, "biological_performance": None,
              "purpose": "Invented vectors/Boolean labels: optimizer, masks, scoring, benchmark and checkpoint wiring only.",
              "run": job, "benchmark_tasks": list(result["tasks"]), "trained_tasks": meta["trained_tasks"]}
    write_json(out / "smoke.json", record)
    return record


def parser():
    p = argparse.ArgumentParser(description="Attachment site model: frozen residue features, separate operation endpoints, no fusion-success claims")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("smoke")
    s.add_argument("--output", required=True)
    c = sub.add_parser("preflight")
    c.add_argument("--manifest", required=True)
    c.add_argument("--synthetic-smoke", action="store_true")
    t = sub.add_parser("train")
    t.add_argument("--manifest", required=True)
    t.add_argument("--config", required=True)
    t.add_argument("--output", required=True)
    t.add_argument("--synthetic-smoke", action="store_true")
    t.add_argument("--device", default="cpu")
    t.add_argument("--resume")
    t.add_argument("--execution-receipt")
    b = sub.add_parser("benchmark-development")
    b.add_argument("--manifest", required=True)
    b.add_argument("--checkpoint", action="append", required=True, help="NAME=CHECKPOINT, repeat for matched model seeds/linear controls")
    b.add_argument("--peer-scores", action="append", default=[], help="NAME=JSON for separately reviewed/versioned external scores")
    b.add_argument("--coverage-fraction", type=float, required=True, help="Must be fixed before independent evaluation; not a score threshold")
    b.add_argument("--bootstrap-draws", type=int, default=200)
    b.add_argument("--seed", type=int, default=17)
    b.add_argument("--device", default="cpu")
    b.add_argument("--synthetic-smoke", action="store_true")
    b.add_argument("--output", required=True)
    d = sub.add_parser("score")
    d.add_argument("--checkpoint", required=True)
    d.add_argument("--sequence-json", required=True, help="JSON with exactly a sequence field")
    d.add_argument("--embedding", required=True)
    d.add_argument("--embedding-sha256", required=True)
    d.add_argument("--device", default="cpu")
    d.add_argument("--output", required=True)
    r = sub.add_parser("rank-plans")
    r.add_argument("--input", required=True, help="JSON: plans, domain_scores, geometry_reports")
    r.add_argument("--output", required=True)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if hasattr(args, "output") and Path(args.output).exists():
        raise ValueError("Refusing to overwrite existing outputs")
    if args.command == "smoke":
        result = smoke(args.output)
    elif args.command == "train":
        result = train(args.manifest, SiteTrainConfig.from_dict(load_json(args.config)), args.output,
                       args.synthetic_smoke, args.device, args.resume, args.execution_receipt)
    elif args.command == "preflight":
        data = preflight(args.manifest, args.synthetic_smoke)
        result = {k: data[k] for k in ("input_hashes", "counts", "synthetic", "supported_tasks")}
        result["training_authorized"] = False
    else:
        if args.command == "benchmark-development":
            data = preflight(args.manifest, args.synthetic_smoke)
            pairs = [value.split("=", 1) for value in args.checkpoint]
            if any(len(pair) != 2 or not all(pair) for pair in pairs) or len({pair[0] for pair in pairs}) != len(pairs):
                raise ValueError("Distinct NAME=CHECKPOINT entries required")
            peers = [value.split("=", 1) for value in args.peer_scores]
            if any(len(pair) != 2 or not all(pair) for pair in peers) or len({pair[0] for pair in peers}) != len(peers):
                raise ValueError("Distinct NAME=JSON peer entries required")
            result = benchmark_checkpoints(data, dict(pairs), args.coverage_fraction, args.bootstrap_draws, args.seed, args.device, dict(peers))
        elif args.command == "score":
            value = load_json(args.sequence_json)
            if set(value) != {"sequence"} or file_sha256(args.embedding) != args.embedding_sha256:
                raise ValueError("Input sequence/feature hash mismatch")
            model, meta = SiteModel.load(args.checkpoint, args.device)
            matrix = load_embedding(args.embedding, value["sequence"], meta["identity"]["encoder"], meta["identity"]["synthetic_software_fixture"])
            result = score_domain(model, value["sequence"], matrix, meta)
            result.update(embedding_sha256=args.embedding_sha256, checkpoint_metadata_sha256=file_sha256(Path(args.checkpoint)/"model.json"))
        else:
            value = load_json(args.input)
            result = rank_plans([AttachmentPlan.from_dict(p) for p in value["plans"]], value["domain_scores"], value["geometry_reports"])
        write_json(args.output, result)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0
