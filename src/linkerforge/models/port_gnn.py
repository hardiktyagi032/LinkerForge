"""Experimental, deployment-compatible local-port graph linker ranker.

Each domain graph is encoded independently. In particular, this model never
uses native inter-domain distances unavailable for two uploaded structures.
Scores are within-query preferences, not probabilities of fusion success.
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    import torch
    from torch import Tensor, nn
except ImportError:  # Keep the non-neural baseline importable without PyTorch.
    torch = None
    Tensor = object
    nn = None


ALPHABET = "ACDEFGHIKLMNPQRSTVWY"
AA_INDEX = {aa: index for index, aa in enumerate(ALPHABET)}


@dataclass(frozen=True)
class PortGraph:
    """A single domain's C-alpha neighborhood around a specified port.

    ``sequence`` and ``coordinates`` contain only domain residues; the natural
    linker and the other domain are excluded. Coordinates need no alignment.
    """

    sequence: str
    coordinates: tuple[tuple[float, float, float], ...]
    port_index: int

    def __post_init__(self) -> None:
        if not self.sequence or set(self.sequence) - set(ALPHABET):
            raise ValueError("graph sequence must use canonical amino acids")
        if len(self.coordinates) != len(self.sequence):
            raise ValueError("one coordinate is required per residue")
        if not 0 <= self.port_index < len(self.sequence):
            raise ValueError("port index outside domain")
        if any(len(xyz) != 3 for xyz in self.coordinates):
            raise ValueError("coordinates must be 3D")


def tensorize_port(graph: PortGraph, *, radius: float = 12.0, max_nodes: int = 48, device=None):
    """Return local residue features and coordinates, sorted by sequence index.

    The port is always retained. Selection uses only intra-domain distances.
    """
    if torch is None:
        raise RuntimeError("PyTorch is required for the geometric ranker")
    if radius <= 0 or max_nodes < 1:
        raise ValueError("radius and max_nodes must be positive")
    coords = torch.tensor(graph.coordinates, dtype=torch.float32, device=device)
    if not torch.isfinite(coords).all():
        raise ValueError("nonfinite coordinates")
    distances = torch.linalg.vector_norm(coords - coords[graph.port_index], dim=-1)
    selected = torch.where(distances <= radius)[0]
    selected = selected[torch.argsort(distances[selected])[:max_nodes]]
    selected = torch.sort(selected).values
    feature = torch.zeros((len(selected), 21), dtype=torch.float32, device=device)
    for row, index in enumerate(selected.tolist()):
        feature[row, AA_INDEX[graph.sequence[index]]] = 1.0
        feature[row, 20] = float(index == graph.port_index)
    return feature, coords[selected]


if nn is not None:
    class LocalPortEncoder(nn.Module):
        """Distance-only message passing; invariant to rigid-body motion."""

        def __init__(self, hidden: int = 64, layers: int = 2, k: int = 8):
            super().__init__()
            if hidden < 1 or layers < 1 or k < 1:
                raise ValueError("invalid graph hyperparameters")
            self.k = k
            self.input = nn.Linear(21, hidden)
            self.messages = nn.ModuleList(nn.Sequential(nn.Linear(2 * hidden + 1, hidden), nn.SiLU(), nn.Linear(hidden, hidden)) for _ in range(layers))
            self.updates = nn.ModuleList(nn.Sequential(nn.Linear(2 * hidden, hidden), nn.SiLU()) for _ in range(layers))

        def forward(self, features: Tensor, coordinates: Tensor) -> Tensor:
            if features.ndim != 2 or features.shape[1] != 21 or coordinates.shape != (len(features), 3):
                raise ValueError("invalid local graph tensors")
            n = len(features)
            distances = torch.cdist(coordinates, coordinates)
            neighbors = torch.topk(distances + torch.eye(n, device=distances.device) * 1e6, k=min(self.k, max(1, n - 1)), largest=False).indices if n > 1 else None
            h = self.input(features)
            for message, update in zip(self.messages, self.updates):
                if neighbors is None:
                    aggregate = torch.zeros_like(h)
                else:
                    source = h[:, None, :].expand(-1, neighbors.shape[1], -1)
                    target = h[neighbors]
                    edge = distances.gather(1, neighbors).unsqueeze(-1) / 20.0
                    aggregate = message(torch.cat((source, target, edge), dim=-1)).mean(dim=1)
                h = h + update(torch.cat((h, aggregate), dim=-1))
            port = torch.argmax(features[:, 20])
            return torch.cat((h[port], h.mean(dim=0)), dim=-1)


    class PortGNNRanker(nn.Module):
        """Two independent local-port encoders plus an order-aware linker head.

        Frozen ESM-2 is not wired in yet; this is a geometry proof-of-concept.
        """

        def __init__(self, hidden: int = 64, layers: int = 2):
            super().__init__()
            self.port_encoder = LocalPortEncoder(hidden=hidden, layers=layers)
            self.linker_embedding = nn.Embedding(len(ALPHABET), hidden)
            self.linker_rnn = nn.GRU(hidden, hidden, batch_first=True)
            self.scorer = nn.Sequential(nn.Linear(5 * hidden, hidden), nn.SiLU(), nn.Linear(hidden, 1))

        def forward(self, port_a: PortGraph, port_b: PortGraph, linker: str) -> Tensor:
            if not 5 <= len(linker) <= 30 or set(linker) - set(ALPHABET):
                raise ValueError("linker must contain 5-30 canonical residues")
            device = next(self.parameters()).device
            a = self.port_encoder(*tensorize_port(port_a, device=device))
            b = self.port_encoder(*tensorize_port(port_b, device=device))
            tokens = torch.tensor([AA_INDEX[aa] for aa in linker], dtype=torch.long, device=device)[None, :]
            embedded = self.linker_embedding(tokens)
            _, hidden = self.linker_rnn(embedded)
            return self.scorer(torch.cat((a, b, hidden[-1, 0]), dim=-1)).squeeze()


    def pairwise_loss(model: PortGNNRanker, port_a: PortGraph, port_b: PortGraph, observed: str, alternative: str) -> Tensor:
        """Softplus ranking loss; alternative is constructed, not measured failure."""
        return torch.nn.functional.softplus(model(port_a, port_b, alternative) - model(port_a, port_b, observed))
else:
    class PortGNNRanker:  # pragma: no cover - checked by explicit missing-dependency test
        def __init__(self, *args, **kwargs):
            raise RuntimeError("PyTorch is required for the geometric ranker")

    def pairwise_loss(*args, **kwargs):
        raise RuntimeError("PyTorch is required for the geometric ranker")
