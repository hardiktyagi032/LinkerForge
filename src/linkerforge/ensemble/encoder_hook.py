"""Encoder-swap hook: precomputed per-residue embeddings (interface only).

Design: swapping the frozen ESM2-35M encoder for ESM-2 650M or ProtT5 is done
OFFLINE. A separate, user-run extraction step (not in this repo, no downloads
here) writes one ``.npz`` per protein/encoder containing the sequence, its
SHA-256, the encoder name/revision and a float16/32 ``(L, D)`` array holding
exactly one row per residue (special tokens stripped). Training/scoring code
reads them through :class:`PrecomputedEmbeddingStore`, which fails closed:
missing file, sequence mismatch, hash mismatch, wrong encoder, wrong dimension,
wrong length or non-finite values all raise :class:`EncoderHookError`. No
fallback to another encoder or to zeros ever occurs.

A matched baseline MUST be retrained on the same embeddings (contract rule 4);
a 650M/ProtT5 comparison is a distinct, richer-input comparison.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

SUPPORTED_ENCODERS = {"esm2_t33_650M_UR50D": 1280, "prot_t5_xl_uniref50": 1024,
                      "esm2_t12_35M_UR50D": 480}


class EncoderHookError(ValueError):
    """Missing or inconsistent precomputed embeddings."""


def _seq_hash(sequence: str) -> str:
    return hashlib.sha256(sequence.encode("ascii")).hexdigest()


def save_embeddings(path, *, protein_id, sequence, encoder, revision, embeddings):
    """Writer used by an offline extractor (and by tests)."""
    emb = np.asarray(embeddings)
    np.savez(path, protein_id=np.asarray(protein_id), sequence=np.asarray(sequence),
             sequence_sha256=np.asarray(_seq_hash(sequence)), encoder=np.asarray(encoder),
             revision=np.asarray(revision), embeddings=emb)


class PrecomputedEmbeddingStore:
    """Directory of ``<protein_id>.<encoder>.npz`` files for one encoder."""

    def __init__(self, root, encoder: str, revision: str | None = None):
        if encoder not in SUPPORTED_ENCODERS:
            raise EncoderHookError(f"unsupported encoder {encoder!r}; known: {sorted(SUPPORTED_ENCODERS)}")
        self.root, self.encoder, self.revision = Path(root), encoder, revision
        self.dimension = SUPPORTED_ENCODERS[encoder]
        if not self.root.is_dir():
            raise EncoderHookError(f"embedding directory missing: {self.root}")

    def path_for(self, protein_id: str) -> Path:
        if not protein_id or "/" in protein_id or "\\" in protein_id or protein_id.startswith("."):
            raise EncoderHookError(f"unsafe protein id {protein_id!r}")
        return self.root / f"{protein_id}.{self.encoder}.npz"

    def get(self, protein_id: str, sequence: str) -> np.ndarray:
        path = self.path_for(protein_id)
        if not path.is_file():
            raise EncoderHookError(f"missing embeddings for {protein_id} ({self.encoder}); never substituted")
        with np.load(path, allow_pickle=False) as z:
            stored = {k: z[k] for k in z.files}
        for key in ("protein_id", "sequence", "sequence_sha256", "encoder", "revision", "embeddings"):
            if key not in stored:
                raise EncoderHookError(f"{path}: missing field {key}")
        if str(stored["encoder"]) != self.encoder:
            raise EncoderHookError(f"{path}: encoder {stored['encoder']} != {self.encoder}")
        if self.revision is not None and str(stored["revision"]) != self.revision:
            raise EncoderHookError(f"{path}: revision {stored['revision']} != {self.revision}")
        if str(stored["protein_id"]) != protein_id:
            raise EncoderHookError(f"{path}: protein id mismatch")
        if str(stored["sequence"]) != sequence or str(stored["sequence_sha256"]) != _seq_hash(sequence):
            raise EncoderHookError(f"{path}: sequence mismatch for {protein_id}")
        emb = stored["embeddings"]
        if emb.ndim != 2 or emb.shape[0] != len(sequence):
            raise EncoderHookError(f"{path}: need one row per residue, got {emb.shape} for length {len(sequence)}")
        if emb.shape[1] != self.dimension:
            raise EncoderHookError(f"{path}: dimension {emb.shape[1]} != {self.dimension}")
        if not np.isfinite(emb).all():
            raise EncoderHookError(f"{path}: non-finite embeddings")
        return emb

    def batch(self, items) -> list:
        """items: iterable of (protein_id, sequence). All-or-nothing."""
        return [self.get(pid, seq) for pid, seq in items]
