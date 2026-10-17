"""Shared domain tower with separate operation heads and frozen input features."""
from dataclasses import asdict, dataclass
import json
from pathlib import Path

import torch
from torch import nn
from torch.nn import functional as F
from safetensors.torch import load_file, save_file

from linkerforge.generation.contracts import strict_dataclass
from linkerforge.generation.data import file_sha256, load_json

TASKS = ("internal_insertion", "n_terminal_extension", "c_terminal_extension")


def allowed_positions(task, length):
    """1-based anchor residues; internal insertion is AFTER its anchor."""
    if task == "internal_insertion":
        return list(range(1, length))
    if task == "n_terminal_extension":
        return [1]
    if task == "c_terminal_extension":
        return [length]
    raise ValueError("Unknown attachment operation")


@dataclass(frozen=True)
class SiteModelConfig:
    embedding_dim: int = 2560
    hidden_size: int = 1280
    architecture: str = "mlp"
    dropout: float = 0.

    def __post_init__(self):
        if any(type(x) is not int or x < 1 for x in (self.embedding_dim, self.hidden_size)):
            raise ValueError("Invalid model dimensions")
        if self.architecture not in {"mlp", "linear"} or not 0 <= self.dropout < 1:
            raise ValueError("Invalid site architecture/dropout")

    @classmethod
    def from_dict(cls, value):
        return strict_dataclass(cls, value)


class SiteModel(nn.Module):
    def __init__(self, config=SiteModelConfig()):
        super().__init__()
        self.config = config
        if config.architecture == "mlp":
            self.tower = nn.Sequential(nn.Linear(config.embedding_dim, config.hidden_size), nn.ReLU(),
                                       nn.Dropout(config.dropout), nn.Linear(config.hidden_size, len(TASKS)))
        else:
            self.tower = nn.Linear(config.embedding_dim, len(TASKS))

    def forward(self, embeddings):
        if embeddings.ndim != 3 or embeddings.shape[-1] != self.config.embedding_dim or not torch.isfinite(embeddings).all():
            raise ValueError("Expected finite batch x residues x frozen embedding dimensions")
        return self.tower(embeddings.detach())

    def loss(self, embeddings, labels, tasks):
        logits = self(embeddings)
        if labels.shape != embeddings.shape[:2] or tasks.shape != (embeddings.shape[0],):
            raise ValueError("Invalid label/task shapes")
        if not ((labels == -1) | (labels == 0) | (labels == 1)).all():
            raise ValueError("Unknown annotations must be -1; known labels are binary")
        selected = logits.gather(2, tasks[:, None, None].expand(-1, logits.shape[1], 1)).squeeze(-1)
        mask = labels != -1
        counts = mask.sum(1)
        if (counts == 0).any():
            raise ValueError("Every fitting record needs known labels")
        losses = F.binary_cross_entropy_with_logits(selected, labels.clamp_min(0).float(), reduction="none") * mask
        return {"loss": (losses.sum(1) / counts).mean(), "bce_sum": losses.sum(), "known_sites": counts.sum()}

    def save(self, directory, metadata):
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=False)
        save_file({k: v.detach().cpu().contiguous() for k, v in self.state_dict().items()}, str(path / "model.safetensors"))
        values = {"format": "attachment-site-head.v0", "config": asdict(self.config), "tasks": list(TASKS),
                  "state_sha256": file_sha256(path / "model.safetensors"), "training": metadata}
        (path / "model.json").write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, directory, device="cpu"):
        path = Path(directory)
        meta = load_json(path / "model.json")
        if (path / "training.json").exists() and load_json(path / "training.json").get("model_metadata_sha256") != file_sha256(path / "model.json"):
            raise ValueError("Checkpoint training metadata binding changed")
        if meta["format"] != "attachment-site-head.v0" or meta["tasks"] != list(TASKS) or file_sha256(path / "model.safetensors") != meta["state_sha256"]:
            raise ValueError("Site checkpoint format/identity mismatch")
        model = cls(SiteModelConfig.from_dict(meta["config"]))
        model.load_state_dict(load_file(str(path / "model.safetensors")), strict=True)
        return model.to(device), meta["training"]
