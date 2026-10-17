"""Bounded one-batch-ahead loading for cloud-scale, no-raw-cache training.

The caller supplies a lazy batch source (for example, an HTTP object stream).
Only the current and next batch are held by this adapter. No records are
written to disk here; persistent manifests/checkpoints are a separate concern.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from typing import Iterable, Iterator, TypeVar


T = TypeVar("T")


def _next_or_end(iterator: Iterator[T]) -> tuple[bool, T | None]:
    try:
        return True, next(iterator)
    except StopIteration:
        return False, None


def prefetch_one_batch(source: Iterable[T]) -> Iterator[T]:
    """Fetch batch n+1 while the consumer trains on batch n.

    The source must have finite network timeouts. Materialized batches should
    be bounded by the caller. Do not retain yielded batches after optimizer use.
    """
    iterator = iter(source)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="linkerforge-prefetch") as executor:
        future = executor.submit(_next_or_end, iterator)
        while True:
            has_batch, batch = future.result()
            if not has_batch:
                return
            future = executor.submit(_next_or_end, iterator)
            yield batch  # type: ignore[misc]
            del batch


def partition_for_cluster(cluster_id: str, *, train_fraction: float = 0.90,
                          validation_fraction: float = 0.05, seed: str = "linkerforge-v1") -> str:
    """Stable cluster-level split; rejects missing IDs rather than row splits.

    The caller must provide a real sequence-homology cluster ID. A domain
    architecture, organism, or accession is not an adequate substitute.
    """
    if not cluster_id or cluster_id.isspace():
        raise ValueError("A real homology cluster ID is required")
    if not (0 < train_fraction < 1 and 0 < validation_fraction < 1
            and train_fraction + validation_fraction < 1):
        raise ValueError("Invalid train/validation fractions")
    value = int.from_bytes(sha256(f"{seed}:{cluster_id}".encode()).digest()[:8], "big") / 2**64
    if value < train_fraction:
        return "train"
    if value < train_fraction + validation_fraction:
        return "validation"
    return "blind"
