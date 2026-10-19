"""Private task/data contract: no implicit negatives or unverified flank labels."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

import torch
from safetensors import safe_open
from safetensors.torch import save_file

from linkerforge.generation.contracts import canonical_hash, sequence, strict_dataclass
from linkerforge.generation.data import checked_file, file_sha256, load_json
from .model import TASKS, allowed_positions


def sequence_sha256(value):
    return hashlib.sha256(value.encode()).hexdigest()


def validate_encoder(identity, synthetic=False):
    if set(identity) != {"model_id", "revision", "weights_sha256", "layer", "embedding_dim"}:
        raise ValueError("Complete frozen encoder identity is required")
    if not identity["model_id"] or type(identity["embedding_dim"]) is not int or identity["embedding_dim"] < 1 or type(identity["layer"]) is not int or identity["layer"] < 0:
        raise ValueError("Malformed encoder identity")
    if not synthetic and (not re.fullmatch(r"[0-9a-f]{40}", identity["revision"] or "") or not re.fullmatch(r"[0-9a-f]{64}", identity["weights_sha256"] or "")):
        raise ValueError("Scientific frozen encoder revision and actual weight hash must be pinned")


def save_embedding(path, seq, embeddings, encoder, synthetic=False):
    validate_encoder(encoder, synthetic)
    sequence(seq, "sequence")
    if embeddings.shape != (len(seq), encoder["embedding_dim"]) or not torch.isfinite(embeddings).all():
        raise ValueError("Embedding rows must match every residue without BOS/EOS or truncation")
    path = Path(path)
    if path.exists():
        raise ValueError("Refusing to overwrite a frozen feature cache")
    save_file({"embeddings": embeddings.detach().cpu().float().contiguous()}, str(path), metadata={
        "format": "attachment-residue-cache.v0", "sequence_sha256": sequence_sha256(seq),
        "encoder": json.dumps(encoder, sort_keys=True), "synthetic": json.dumps(synthetic)})


def load_embedding(path, seq, encoder, synthetic=False):
    with safe_open(str(path), framework="pt", device="cpu") as handle:
        meta = handle.metadata()
        if (list(handle.keys()) != ["embeddings"] or meta.get("format") != "attachment-residue-cache.v0"
                or meta.get("sequence_sha256") != sequence_sha256(seq)
                or json.loads(meta.get("encoder", "{}")) != encoder or json.loads(meta.get("synthetic", "null")) is not synthetic):
            raise ValueError("Frozen feature/sequence/encoder/mode identity mismatch")
        values = handle.get_tensor("embeddings")
    if values.dtype != torch.float32 or values.shape != (len(seq), encoder["embedding_dim"]) or not torch.isfinite(values).all():
        raise ValueError("Invalid cached residue matrix")
    return values


@dataclass(frozen=True)
class SiteExample:
    record_id: str
    sequence: str
    source_id: str
    source_sha256: str
    family_ids: list[str]
    task: str
    labels: list[int]
    evidence_tier: str
    label_reference: str
    training_eligible: bool
    embedding: dict

    def __post_init__(self):
        sequence(self.sequence, "sequence")
        if not all(isinstance(x, str) and x for x in (self.record_id, self.source_id, self.label_reference)):
            raise ValueError("Record/source/label provenance required")
        if not re.fullmatch(r"[0-9a-f]{64}", self.source_sha256):
            raise ValueError("Full source sequence SHA-256 required")
        if not isinstance(self.family_ids, list) or not self.family_ids or any(not isinstance(f, str) or not f for f in self.family_ids):
            raise ValueError("Audited family IDs required")
        if self.task not in TASKS or len(self.labels) != len(self.sequence) or any(type(x) is not int or x not in (-1, 0, 1) for x in self.labels):
            raise ValueError("Known positive/negative/unknown labels must align to every residue")
        allowed = set(allowed_positions(self.task, len(self.sequence)))
        if any(y != -1 and i not in allowed for i, y in enumerate(self.labels, 1)) or all(y == -1 for y in self.labels):
            raise ValueError("Labels must match the declared operation/position convention and include known sites")
        if self.training_eligible is not True:
            raise ValueError("Unreviewed/ineligible records cannot enter the site loader")
        if self.evidence_tier not in {"synthetic_software_fixture", "natural_interruption", "measured_insertion", "measured_terminal_extension"}:
            raise ValueError("Natural linker flanks and predictions are not validated tolerance labels")
        if self.evidence_tier == "natural_interruption" and (self.task != "internal_insertion" or 0 in self.labels):
            raise ValueError("Natural interruption observations establish positives only; other sites remain unknown")
        if self.evidence_tier == "measured_insertion" and self.task != "internal_insertion":
            raise ValueError("Insertion assays cannot silently become terminal-extension labels")
        if self.evidence_tier == "measured_terminal_extension" and self.task == "internal_insertion":
            raise ValueError("Terminal-extension labels cannot silently become insertion labels")


def preflight(manifest_path, synthetic=False):
    path = Path(manifest_path).resolve()
    root, manifest = path.parent, load_json(path)
    if manifest.get("format") != "attachment-site-dataset.v0" or not manifest.get("dataset_id"):
        raise ValueError("Expected private attachment-site dataset proposal")
    if manifest.get("kind") != ("synthetic_software_fixture" if synthetic else "scientific_dataset"):
        raise ValueError("Synthetic and scientific modes are separate")
    validate_encoder(manifest["encoder"], synthetic)
    if set(manifest.get("splits", {})) != {"train", "development"}:
        raise ValueError("Fit/benchmark-development accept train/development only; no blind reader")
    review = manifest.get("review", {})
    if not synthetic and not (review.get("approved") is True and review.get("reference") and review.get("reviewer")):
        raise ValueError("Dataset/task review is required before scientific data loading")
    records, cache, ids, families, sources = {}, {}, set(), {}, {}
    hashes = {str(path): file_sha256(path)}
    raw_counts = {}
    for split, entry in manifest["splits"].items():
        source = checked_file(root, entry)
        hashes[str(source)] = entry["sha256"]
        rows = [strict_dataclass(SiteExample, json.loads(line)) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not rows:
            raise ValueError("Empty split")
        for row in rows:
            if row.record_id in ids or synthetic != (row.evidence_tier == "synthetic_software_fixture"):
                raise ValueError("Duplicate record or synthetic/scientific evidence mixing")
            ids.add(row.record_id)
            definition = manifest.get("task_definitions", {}).get(row.task, {})
            if not synthetic and not (definition.get("review_reference") and definition.get("endpoint")
                                      and definition.get("label_scope") == "donor_aggregated"
                                      and definition.get("aggregation_protocol") and definition.get("negative_evidence_policy")):
                raise ValueError("Single-domain labels require reviewed endpoint, donor aggregation and negative evidence policy")
            features = checked_file(root, row.embedding)
            hashes[str(features)] = row.embedding["sha256"]
            cache[row.record_id] = load_embedding(features, row.sequence, manifest["encoder"], synthetic)
        records[split] = rows
        families[split] = {f for row in rows for f in row.family_ids}
        sources[split] = {v for row in rows for v in (row.source_id, row.source_sha256, sequence_sha256(row.sequence))}
        raw_counts[split] = {"records": len(rows), "positive": sum(y == 1 for row in rows for y in row.labels),
                             "negative": sum(y == 0 for row in rows for y in row.labels), "unknown": sum(y == -1 for row in rows for y in row.labels)}
    if families["train"] & families["development"] or sources["train"] & sources["development"]:
        raise ValueError("Source/sequence/family leakage across splits")
    if synthetic and len(ids) > 32:
        raise ValueError("Synthetic fixture ceiling is 32 records")
    registries = manifest.get("benchmark_registries", [])
    if not synthetic and (not registries or not manifest.get("split_audit")):
        raise ValueError("Full benchmark sequence/family exclusions and reviewed audit required")
    registry_hashes = {}
    for entry in registries:
        source = checked_file(root, entry)
        registry = load_json(source)
        if entry["name"] in registry_hashes or registry.get("format") != "sequence-exclusion-registry.v1" or set(registry) != {"format", "records"} or not registry["records"]:
            raise ValueError("Invalid/duplicate full exclusion registry")
        for row in registry["records"]:
            if (set(row) != {"source_id", "sequence_sha256", "family_ids"} or not row["source_id"]
                    or not re.fullmatch(r"[0-9a-f]{64}", row["sequence_sha256"]) or not isinstance(row["family_ids"], list) or not row["family_ids"]):
                raise ValueError("Only traceable sequence/family exclusion metadata is permitted; labels are forbidden")
            if row["source_id"] in set.union(*sources.values()) or row["sequence_sha256"] in set.union(*sources.values()) or set(row["family_ids"]) & set.union(*families.values()):
                raise ValueError("Protected benchmark source/sequence/family collision")
        registry_hashes[entry["name"]] = entry["sha256"]
        hashes[str(source)] = entry["sha256"]
    if not synthetic:
        source = checked_file(root, manifest["split_audit"])
        audit = load_json(source)
        if (audit.get("passed") is not True or not audit.get("method") or not audit.get("review_reference")
                or audit.get("split_sha256s") != {k: v["sha256"] for k, v in manifest["splits"].items()}
                or audit.get("benchmark_registry_sha256s") != registry_hashes):
            raise ValueError("Audit does not bind the exact split/registry hashes")
        hashes[str(source)] = manifest["split_audit"]["sha256"]
    # A supervised binary head needs real negative controls, not unobserved sites.
    supported = []
    for task in TASKS:
        values = {y for row in records["train"] if row.task == task for y in row.labels if y != -1}
        if values:
            if values != {0, 1}:
                raise ValueError("BCE requires known positive and negative examples per fitted task; PU is not implemented")
            supported.append(task)
    return {"manifest": manifest, "records": records, "embeddings": cache, "input_hashes": hashes,
            "counts": raw_counts, "synthetic": synthetic, "supported_tasks": supported}


def collate(rows, embeddings, device="cpu"):
    width = max(len(row.sequence) for row in rows)
    dim = embeddings[rows[0].record_id].shape[1]
    features = torch.zeros(len(rows), width, dim, device=device)
    labels = torch.full((len(rows), width), -1, dtype=torch.long, device=device)
    for index, row in enumerate(rows):
        features[index, :len(row.sequence)] = embeddings[row.record_id].to(device)
        labels[index, :len(row.sequence)] = torch.tensor(row.labels, device=device)
    return features, labels, torch.tensor([TASKS.index(row.task) for row in rows], device=device)
