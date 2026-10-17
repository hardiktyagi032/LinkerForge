"""Private generator input proposal; does not change shared repository schemas."""
from dataclasses import asdict, dataclass, fields
import hashlib
import json
import math

AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def sequence(value, name):
    if not isinstance(value, str) or not value or any(x not in AMINO_ACIDS for x in value):
        raise ValueError(f"{name} must be a nonempty canonical uppercase amino-acid sequence")
    return value


def strict_dataclass(cls, value):
    if not isinstance(value, dict) or set(value) - {f.name for f in fields(cls)}:
        raise ValueError(f"Unknown fields or invalid object for {cls.__name__}")
    return cls(**value)


def family_components(rows):
    """Transitive multi-family groups for paired resampling, not clustering."""
    groups = []
    for row in rows:
        group, families = [row], set(row.family_ids)
        remaining = list(groups)
        changed = True
        while changed:
            changed, rest = False, []
            for existing, ids in remaining:
                if families & ids:
                    group += existing
                    families |= ids
                    changed = True
                else:
                    rest.append((existing, ids))
            remaining = rest
        groups = remaining + [(group, families)]
    return [group for group, _ in groups]


@dataclass(frozen=True)
class DesignRequest:
    domain_a: str
    domain_b: str
    length: int
    rigidity: str = "unknown"
    cleavage: str = "unknown"
    motif: str = ""
    motif_source: str = ""
    motif_start: int | None = None  # zero-based within linker, never source numbering
    cassette_flank: int = 2  # engineering layout, not a biological threshold
    allowed_amino_acids: str = AMINO_ACIDS
    forbidden_motifs: tuple[str, ...] = ()
    topology: str = "tandem"
    attachment_a: int | None = None  # one-based; defaults to domain A C terminus
    attachment_b: int = 1

    def __post_init__(self):
        sequence(self.domain_a, "domain_a")
        sequence(self.domain_b, "domain_b")
        if type(self.length) is not int or self.length < 1:
            raise ValueError("length must be a positive residue count")
        if self.rigidity not in {"unknown", "flexible", "rigid"}:
            raise ValueError("Unsupported rigidity annotation")
        if self.cleavage not in {"unknown", "cleavable", "no_known_motif"}:
            raise ValueError("Use unknown, cleavable or no_known_motif, never guaranteed non-cleavable")
        if (self.attachment_a is not None and type(self.attachment_a) is not int) or type(self.attachment_b) is not int:
            raise ValueError("Attachment sites must be integer residue positions")
        if self.topology != "tandem" or self.attachment_a not in (None, len(self.domain_a)) or self.attachment_b != 1:
            raise ValueError("This generator supports C(A)-to-N(B) tandem infilling; internal/multi-tether designs need a separate topology protocol")
        if not isinstance(self.allowed_amino_acids, str) or not self.allowed_amino_acids or set(self.allowed_amino_acids) - set(AMINO_ACIDS):
            raise ValueError("Invalid allowed residue alphabet")
        if type(self.cassette_flank) is not int or self.cassette_flank < 0:
            raise ValueError("cassette_flank must be a nonnegative engineering layout parameter")
        if not isinstance(self.forbidden_motifs, (list, tuple)):
            raise ValueError("forbidden_motifs must be an explicit list")
        object.__setattr__(self, "forbidden_motifs", tuple(self.forbidden_motifs))
        for motif in self.forbidden_motifs:
            sequence(motif, "forbidden motif")
        if self.cleavage == "cleavable":
            sequence(self.motif, "cited exact cleavage motif")
            if not isinstance(self.motif_source, str) or not self.motif_source.strip():
                raise ValueError("A cleavage motif requires its source; specificity is not learned")
            if set(self.motif) - set(self.allowed_amino_acids):
                raise ValueError("Cleavage motif conflicts with allowed alphabet")
            start = self.motif_start
            if start is None:
                start = (self.length - len(self.motif)) // 2
                if self.rigidity == "rigid":
                    start = self.length - self.cassette_flank - len(self.motif)
            if type(start) is not int or start < 0 or start + len(self.motif) > self.length:
                raise ValueError("Cleavage motif does not fit requested length")
            object.__setattr__(self, "motif_start", start)
            if self.rigidity == "rigid" and (start - self.cassette_flank < 1 or self.length - start - len(self.motif) < self.cassette_flank):
                raise ValueError("Rigid+cleavable requires a distinct spacer plus flanked flexible protease cassette")
        elif self.motif or self.motif_start is not None or self.motif_source:
            raise ValueError("A supplied cleavage cassette requires cleavage=cleavable")

    @classmethod
    def from_dict(cls, value):
        return strict_dataclass(cls, value)

    def to_dict(self):
        return asdict(self)

    def locked_positions(self):
        if self.cleavage != "cleavable":
            return {}
        return {self.motif_start + i: residue for i, residue in enumerate(self.motif)}

    def segments(self):
        if self.rigidity == "rigid" and self.cleavage == "cleavable":
            stop = self.motif_start - self.cassette_flank
            return [{"start": 1, "end": stop, "design_intent": "rigid_spacer"},
                    {"start": stop + 1, "end": self.length, "design_intent": "flexible_protease_cassette"}]
        return [{"start": 1, "end": self.length, "design_intent": self.rigidity}]


@dataclass(frozen=True)
class TrainingExample:
    record_id: str
    request: DesignRequest
    linker: str
    source_id: str
    source_sha256: str
    family_ids: tuple[str, ...]
    evidence_tier: str
    training_eligible: bool

    def __post_init__(self):
        sequence(self.linker, "linker")
        if len(self.linker) != self.request.length or set(self.linker) - set(self.request.allowed_amino_acids):
            raise ValueError("Linker target conflicts with the explicitly supplied design constraints")
        if any(self.linker[p] != residue for p, residue in self.request.locked_positions().items()):
            raise ValueError("Target does not contain its declared cleavage cassette")
        if (not isinstance(self.record_id, str) or not isinstance(self.source_id, str)
                or not self.record_id or not self.source_id or not isinstance(self.family_ids, (list, tuple))
                or not self.family_ids or any(not isinstance(f, str) or not f for f in self.family_ids)):
            raise ValueError("Record, source and family identities are required")
        if not isinstance(self.source_sha256, str) or len(self.source_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.source_sha256):
            raise ValueError("A source sequence SHA-256 is required")
        if self.evidence_tier not in {"synthetic_software_fixture", "natural_observation", "predicted_span", "measured_function"}:
            raise ValueError("Evidence tiers must distinguish predictions, observations and measurements")
        if type(self.training_eligible) is not bool or not self.training_eligible:
            raise ValueError("Ineligible examples cannot enter a training loader")
        object.__setattr__(self, "family_ids", tuple(self.family_ids))

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["request"] = DesignRequest.from_dict(value["request"])
        return strict_dataclass(cls, value)


@dataclass(frozen=True)
class GeneratorConfig:
    backend: str = "native"
    max_linker_length: int = 128
    flank_residues: int = 128
    max_positions: int = 512
    hidden_size: int = 256
    layers: int = 4
    heads: int = 8
    dropout: float = .1
    base_model: str | None = None
    revision: str | None = None
    local_files_only: bool = True
    lora_rank: int = 0
    lora_alpha: float = 16.
    lora_targets: tuple[str, ...] = ("qkv", "projection", "ff_in", "ff_out")

    def __post_init__(self):
        if self.backend not in {"native", "hf_causal_lm"}:
            raise ValueError("Unsupported backbone")
        for name in ("max_linker_length", "flank_residues", "max_positions", "hidden_size", "layers", "heads"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.hidden_size % self.heads or not 0 <= self.dropout < 1 or not math.isfinite(self.dropout):
            raise ValueError("Invalid attention dimensions/dropout")
        if type(self.lora_rank) is not int or self.lora_rank < 0 or self.lora_alpha <= 0 or not math.isfinite(self.lora_alpha):
            raise ValueError("Invalid LoRA parameters")
        if type(self.local_files_only) is not bool or not isinstance(self.lora_targets, (list, tuple)) or any(not isinstance(t, str) or not t for t in self.lora_targets):
            raise ValueError("Invalid backbone loading/adapter configuration")
        object.__setattr__(self, "lora_targets", tuple(self.lora_targets))
        if self.backend == "hf_causal_lm" and (not self.base_model or not self.revision):
            raise ValueError("Pretrained backbone requires a named checkpoint and pinned revision (or local directory with revision=local)")

    @classmethod
    def from_dict(cls, value):
        return strict_dataclass(cls, value)

    def to_dict(self):
        return asdict(self)
