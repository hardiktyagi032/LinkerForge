"""Causal FIM infiller with a CPU reference backbone and optional protein LM."""
import json
from pathlib import Path
import re

import torch
from torch import nn
from torch.nn import functional as F
from safetensors.torch import load_file, save_file

from .contracts import AMINO_ACIDS, GeneratorConfig, canonical_hash
from .tokenizer import FIMTokenizer
from .data import file_sha256


def base_identity(config):
    if config.backend == "native":
        return None
    root = Path(config.base_model)
    if not root.is_dir():
        return {"model": config.base_model, "revision": config.revision}
    files = {p.relative_to(root).as_posix(): file_sha256(p)
             for p in sorted(root.rglob("*")) if p.is_file() and ".cache" not in p.parts}
    if not files:
        raise ValueError("Empty local pretrained asset directory")
    return {"local_files": files, "sha256": canonical_hash(files)}


class LoRAProjection(nn.Module):
    """Low-rank residual around Linear or HF Conv1D; base weights stay frozen."""
    def __init__(self, base, rank, alpha):
        super().__init__()
        self.base = base.requires_grad_(False)
        if isinstance(base, nn.Linear):
            outputs, inputs = base.weight.shape
        elif base.__class__.__name__ == "Conv1D" and base.weight.ndim == 2:
            inputs, outputs = base.weight.shape
        else:
            raise ValueError("LoRA target must be Linear or Hugging Face Conv1D")
        self.a = nn.Parameter(base.weight.new_empty(rank, inputs))
        self.b = nn.Parameter(base.weight.new_zeros(outputs, rank))
        nn.init.kaiming_uniform_(self.a, a=5 ** .5)
        self.scale = alpha / rank

    def forward(self, x):
        return self.base(x) + self.scale * F.linear(F.linear(x, self.a), self.b)


def install_lora(model, targets, rank, alpha):
    selected = [(name, layer) for name, layer in model.named_modules()
                if name and name.rsplit(".", 1)[-1] in targets]
    if not selected:
        raise ValueError("No LoRA targets matched: configure actual backbone projection names")
    for name, layer in selected:
        parent_path, _, child = name.rpartition(".")
        parent = model.get_submodule(parent_path) if parent_path else model
        setattr(parent, child, LoRAProjection(layer, rank, alpha))
    return [name for name, _ in selected]


class CausalBlock(nn.Module):
    def __init__(self, config):
        super().__init__()
        h = config.hidden_size
        self.heads, self.dropout = config.heads, config.dropout
        self.norm1, self.norm2 = nn.LayerNorm(h), nn.LayerNorm(h)
        self.qkv = nn.Linear(h, 3 * h)
        self.projection = nn.Linear(h, h)
        self.ff_in, self.ff_out = nn.Linear(h, 4 * h), nn.Linear(4 * h, h)

    def forward(self, x, mask):
        batch, length, hidden = x.shape
        q, k, v = self.qkv(self.norm1(x)).chunk(3, dim=-1)
        q, k, v = [a.view(batch, length, self.heads, hidden // self.heads).transpose(1, 2) for a in (q, k, v)]
        causal = torch.ones(length, length, device=x.device, dtype=torch.bool).tril()
        allowed = causal[None, None] & mask[:, None, None, :]
        attended = F.scaled_dot_product_attention(q, k, v, attn_mask=allowed,
                                                  dropout_p=self.dropout if self.training else 0.)
        attended = attended.transpose(1, 2).contiguous().view(batch, length, hidden)
        x = x + F.dropout(self.projection(attended), self.dropout, self.training)
        return x + F.dropout(self.ff_out(F.gelu(self.ff_in(self.norm2(x)))), self.dropout, self.training)


class LinkerInfiller(nn.Module):
    def __init__(self, config: GeneratorConfig):
        super().__init__()
        self.config = config
        self.tokenizer = FIMTokenizer(config.max_linker_length)
        self.base_identity = base_identity(config)
        self.lora_modules = []
        if config.backend == "native":
            if config.lora_rank:
                raise ValueError("Do not train adapters on a frozen random native backbone; use a pretrained protein LM")
            self.embedding = nn.Embedding(len(self.tokenizer.tokens), config.hidden_size)
            self.positions = nn.Embedding(config.max_positions, config.hidden_size)
            self.blocks = nn.ModuleList(CausalBlock(config) for _ in range(config.layers))
            self.final_norm = nn.LayerNorm(config.hidden_size)
            self.output = nn.Linear(config.hidden_size, len(AMINO_ACIDS))
        else:
            self._load_hf(config)

    def _load_hf(self, config):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        local = Path(config.base_model).is_dir()
        if not local and not re.fullmatch(r"[0-9a-f]{40}", config.revision):
            raise ValueError("Remote protein model revision must be an immutable 40-character commit SHA")
        if local and config.revision != "local":
            raise ValueError("Local asset directories use revision=local and are hashed in the training manifest")
        kwargs = dict(local_files_only=config.local_files_only, trust_remote_code=False)
        if not local:
            kwargs["revision"] = config.revision
        hf_tokenizer = AutoTokenizer.from_pretrained(config.base_model, **kwargs)
        # No silent change from residue counts to BPE counts: reject incompatible
        # checkpoints. A future BPE adapter requires a separately tested protocol.
        aa_ids = []
        for residue in AMINO_ACIDS:
            ids = hf_tokenizer.encode(residue, add_special_tokens=False)
            if len(ids) != 1 or hf_tokenizer.decode(ids).strip() != residue or ids[0] in hf_tokenizer.all_special_ids:
                raise ValueError("Backbone tokenizer must represent every canonical residue as one distinct token")
            aa_ids.append(ids[0])
        if len(set(aa_ids)) != 20:
            raise ValueError("Backbone tokenizer aliases distinct amino acids")
        probes = [AMINO_ACIDS * 2, "GSGSGSGS", "EAAAKEAAAK",
                  "".join(a + b for a in AMINO_ACIDS for b in AMINO_ACIDS)]
        for probe in probes:
            if hf_tokenizer.encode(probe, add_special_tokens=False) != [aa_ids[AMINO_ACIDS.index(a)] for a in probe]:
                raise ValueError("Backbone tokenizer merges residues or requires an unsupported serialization; BPE is not a residue-exact backend")
        controls = self.tokenizer.tokens[20:]
        hf_tokenizer.add_special_tokens({"additional_special_tokens": controls})
        self.backbone = AutoModelForCausalLM.from_pretrained(config.base_model, **kwargs)
        self.backbone.resize_token_embeddings(len(hf_tokenizer), mean_resizing=False)
        limit = getattr(self.backbone.config, "max_position_embeddings", None)
        if limit is not None and config.max_positions > limit:
            raise ValueError("Configured context exceeds the pretrained backbone window")
        mapping = aa_ids + [hf_tokenizer.convert_tokens_to_ids(t) for t in controls]
        self.register_buffer("backbone_token_ids", torch.tensor(mapping), persistent=True)
        embedding = self.backbone.get_input_embeddings()
        hidden = embedding.weight.shape[1]
        self.control_embedding = nn.Embedding(len(controls), hidden)
        with torch.no_grad():
            self.control_embedding.weight.copy_(embedding.weight[mapping[20:]])
        self.output = nn.Linear(hidden, 20)
        with torch.no_grad():
            head = self.backbone.get_output_embeddings()
            self.output.weight.copy_(head.weight[aa_ids])
            self.output.bias.zero_()
        if config.lora_rank:
            self.backbone.requires_grad_(False)
            self.lora_modules = install_lora(self.backbone.base_model, config.lora_targets,
                                              config.lora_rank, config.lora_alpha)

    def forward(self, input_ids, attention_mask, labels=None):
        if input_ids.ndim != 2 or input_ids.shape != attention_mask.shape or input_ids.shape[1] > self.config.max_positions:
            raise ValueError("Invalid input dimensions or context overflow")
        if self.config.backend == "native":
            positions = torch.arange(input_ids.shape[1], device=input_ids.device)
            hidden = self.embedding(input_ids) + self.positions(positions)[None]
            hidden = F.dropout(hidden, self.config.dropout, self.training)
            for block in self.blocks:
                hidden = block(hidden, attention_mask.bool())
            hidden = self.final_norm(hidden)
        else:
            mapped = self.backbone_token_ids[input_ids]
            ordinary = self.backbone.get_input_embeddings()(mapped)
            controls = self.control_embedding((input_ids - 20).clamp_min(0))
            embeddings = torch.where((input_ids >= 20)[..., None], controls, ordinary)
            hidden = self.backbone.base_model(inputs_embeds=embeddings, attention_mask=attention_mask.long(),
                                              use_cache=False, return_dict=True).last_hidden_state
        logits = self.output(hidden)
        result = {"logits": logits}
        if labels is not None:
            if labels.shape != input_ids.shape:
                raise ValueError("Label shape mismatch")
            shifted = labels[:, 1:]
            counts = (shifted != -100).sum(dim=1)
            if (counts == 0).any():
                raise ValueError("Every example must contain a learnable target residue")
            losses = F.cross_entropy(logits[:, :-1].transpose(1, 2), shifted,
                                      ignore_index=-100, reduction="none")
            result.update(loss=(losses.sum(dim=1) / counts).mean(),
                          target_nll_sum=losses.sum(), target_residues=counts.sum())
        return result

    def save(self, directory):
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=False)
        # Store trainable state only for a frozen pretrained backbone. Base asset
        # identity stays explicit; this is not a portable standalone pretrained LM.
        state = self.state_dict()
        if self.config.backend == "hf_causal_lm" and self.config.lora_rank:
            names = {name for name, p in self.named_parameters() if p.requires_grad}
            state = {name: tensor for name, tensor in state.items() if name in names or name == "backbone_token_ids"}
        save_file({name: tensor.detach().cpu().contiguous().clone() for name, tensor in state.items()},
                  str(path / "model.safetensors"))
        metadata = {"format": "linkerforge-fim.v1", "config": self.config.to_dict(),
                    "base_identity": self.base_identity,
                    "state_sha256": file_sha256(path / "model.safetensors"),
                    "vocabulary_sha256": canonical_hash(self.tokenizer.tokens),
                    "lora_modules": self.lora_modules, "state_keys": sorted(state)}
        (path / "model.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, directory, device="cpu"):
        path = Path(directory)
        meta = json.loads((path / "model.json").read_text(encoding="utf-8"))
        if meta["format"] != "linkerforge-fim.v1":
            raise ValueError("Unsupported checkpoint format")
        config = GeneratorConfig.from_dict(meta["config"])
        if file_sha256(path / "model.safetensors") != meta["state_sha256"] or base_identity(config) != meta["base_identity"]:
            raise ValueError("Checkpoint weights or frozen base asset identity changed")
        model = cls(config)
        if canonical_hash(model.tokenizer.tokens) != meta["vocabulary_sha256"] or model.lora_modules != meta["lora_modules"]:
            raise ValueError("Checkpoint vocabulary or adapter topology mismatch")
        state = load_file(str(path / "model.safetensors"))
        if sorted(state) != meta["state_keys"]:
            raise ValueError("Checkpoint state-key manifest mismatch")
        expected = set(model.state_dict())
        if model.config.backend == "hf_causal_lm" and model.config.lora_rank:
            expected = {name for name, p in model.named_parameters() if p.requires_grad} | {"backbone_token_ids"}
        if set(state) != expected:
            raise ValueError("Checkpoint is missing required trainable state")
        model.load_state_dict(state, strict=not (model.config.backend == "hf_causal_lm" and model.config.lora_rank))
        return model.to(device)
