"""Hash-checked private dataset adapter; preflight runs before loading weights."""
import hashlib
import json
from pathlib import Path

from .contracts import TrainingExample


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def checked_file(root, entry):
    path = (root / entry["path"]).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Dataset files must exist within the manifest directory")
    if file_sha256(path) != entry["sha256"]:
        raise ValueError(f"Input hash mismatch: {entry['path']}")
    return path


def preflight(manifest_path, synthetic=False):
    manifest_path = Path(manifest_path).resolve()
    manifest = load_json(manifest_path)
    root = manifest_path.parent
    if manifest.get("format") != "fusion-generator-dataset.v0" or not manifest.get("dataset_id"):
        raise ValueError("Expected the documented private generator dataset proposal")
    expected_kind = "synthetic_software_fixture" if synthetic else "scientific_dataset"
    if manifest.get("kind") != expected_kind:
        raise ValueError("Synthetic smoke and scientific data cannot share a run mode")
    review = manifest.get("review", {})
    if not synthetic and not (review.get("approved") is True and review.get("reviewer") and review.get("reference")):
        raise ValueError("Scientific data require explicit dataset/protocol review metadata")
    if set(manifest.get("splits", {})) != {"train", "development"}:
        raise ValueError("Training accepts train and development only; blind evaluation is not implemented here")
    records, files = {}, {str(manifest_path): file_sha256(manifest_path)}
    seen_ids, split_families, split_sources = set(), {}, {}
    for split, entry in manifest["splits"].items():
        path = checked_file(root, entry)
        files[str(path)] = entry["sha256"]
        values = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                example = TrainingExample.from_dict(json.loads(line))
                if example.record_id in seen_ids:
                    raise ValueError("Duplicate record ID within or across splits")
                seen_ids.add(example.record_id)
                if synthetic != (example.evidence_tier == "synthetic_software_fixture"):
                    raise ValueError("Synthetic records must never enter scientific training")
                if example.evidence_tier == "predicted_span" and not review.get("allow_predicted_spans", False):
                    raise ValueError("Predicted-span training requires an explicitly reviewed acquisition policy")
                values.append(example)
        if not values:
            raise ValueError("Empty training/development split")
        records[split] = values
        split_families[split] = {f for e in values for f in e.family_ids}
        split_sources[split] = ({e.source_id for e in values} | {e.source_sha256 for e in values}
                                | {hashlib.sha256((e.request.domain_a + e.linker + e.request.domain_b).encode()).hexdigest() for e in values})
    if split_families["train"] & split_families["development"] or split_sources["train"] & split_sources["development"]:
        raise ValueError("Source or supplied family cluster crosses train/development")
    if synthetic and sum(map(len, records.values())) > 32:
        raise ValueError("Synthetic software smoke tests are capped at 32 records")
    registries = manifest.get("benchmark_registries", [])
    if not synthetic and (not registries or not manifest.get("split_audit")):
        raise ValueError("Scientific training requires full exclusion registries and a reviewed family audit")
    registry_hashes = {}
    all_families = set.union(*split_families.values())
    all_sources = set.union(*split_sources.values())
    for entry in registries:
        if not entry.get("name") or entry["name"] in registry_hashes:
            raise ValueError("Benchmark registries need distinct names")
        path = checked_file(root, entry)
        registry = load_json(path)
        if set(registry) != {"format", "records"} or registry["format"] != "sequence-exclusion-registry.v1" or not registry["records"]:
            raise ValueError("Malformed or empty benchmark sequence/family registry")
        for record in registry["records"]:
            if set(record) != {"source_id", "sequence_sha256", "family_ids"} or not record["source_id"] or not record["family_ids"]:
                raise ValueError("Only complete sequence/source/family exclusion metadata may enter registry; labels are prohibited")
            if (not isinstance(record["family_ids"], list) or any(not isinstance(f, str) or not f for f in record["family_ids"])
                    or not isinstance(record["sequence_sha256"], str) or len(record["sequence_sha256"]) != 64
                    or any(c not in "0123456789abcdef" for c in record["sequence_sha256"])):
                raise ValueError("Malformed sequence hash or family identities in exclusion registry")
            if record["source_id"] in all_sources or record["sequence_sha256"] in all_sources or set(record["family_ids"]) & all_families:
                raise ValueError("Benchmark source/sequence/family collision")
        registry_hashes[entry["name"]] = entry["sha256"]
        files[str(path)] = entry["sha256"]
    if not synthetic:
        path = checked_file(root, manifest["split_audit"])
        audit = load_json(path)
        required_splits = {name: entry["sha256"] for name, entry in manifest["splits"].items()}
        if (audit.get("passed") is not True or not audit.get("method") or not audit.get("review_reference")
                or audit.get("split_sha256s") != required_splits or audit.get("benchmark_registry_sha256s") != registry_hashes):
            raise ValueError("Family audit is missing, unreviewed or does not bind these exact inputs")
        files[str(path)] = manifest["split_audit"]["sha256"]
    return {"manifest": manifest, "records": records, "input_hashes": files,
            "synthetic": synthetic, "counts": {name: len(values) for name, values in records.items()},
            "limitation": "Checks supplied provenance/clusters and audit hashes; does not establish homology or biological annotation quality."}
