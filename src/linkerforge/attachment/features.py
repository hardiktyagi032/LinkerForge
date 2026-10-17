"""Optional local-only frozen ESM extraction; no automatic downloads or jobs."""
from pathlib import Path

import torch

from linkerforge.generation.contracts import AMINO_ACIDS, canonical_hash, sequence
from linkerforge.generation.data import file_sha256
from .data import validate_encoder


def asset_bundle_sha256(directory):
    root = Path(directory)
    files = {p.relative_to(root).as_posix(): file_sha256(p) for p in sorted(root.rglob("*")) if p.is_file() and ".cache" not in p.parts}
    if not files:
        raise ValueError("No local encoder assets")
    return canonical_hash(files)


def load_local_encoder(directory, identity, device="cpu"):
    validate_encoder(identity)
    if asset_bundle_sha256(directory) != identity["weights_sha256"]:
        raise ValueError("Actual frozen local asset bundle hash differs from reviewed identity")
    from transformers import AutoTokenizer, EsmModel
    tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True, trust_remote_code=False)
    model = EsmModel.from_pretrained(directory, local_files_only=True).requires_grad_(False).eval().to(device)
    if model.config.hidden_size != identity["embedding_dim"] or not 0 < identity["layer"] <= model.config.num_hidden_layers:
        raise ValueError("Encoder dimensions/layer mismatch")
    return model, tokenizer


@torch.inference_mode()
def extract_residues(model, tokenizer, seq, layer):
    sequence(seq, "sequence")
    model.requires_grad_(False).eval()
    batch = tokenizer(seq, return_tensors="pt", return_special_tokens_mask=True, truncation=False)
    special = batch.pop("special_tokens_mask")[0].bool()
    expected = [tokenizer.convert_tokens_to_ids(a) for a in seq]
    actual = batch["input_ids"][0][~special].tolist()
    if actual != expected or len(actual) != len(seq) or any(tokenizer.convert_tokens_to_ids(a) in tokenizer.all_special_ids for a in AMINO_ACIDS):
        raise ValueError("Tokenizer residue alignment/BOS/EOS mismatch")
    if len(batch["input_ids"][0]) > model.config.max_position_embeddings:
        raise ValueError("Sequence exceeds frozen encoder context; no silent truncation/window stitching")
    device = next(model.parameters()).device
    values = model(**{k: v.to(device) for k, v in batch.items()}, output_hidden_states=True).hidden_states
    if not 0 < layer < len(values):
        raise ValueError("Requested encoder layer unavailable")
    result = values[layer][0][~special.to(device)].float().cpu()
    if not torch.isfinite(result).all():
        raise ValueError("Nonfinite frozen embeddings")
    return result
