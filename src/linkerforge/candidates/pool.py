"""Create one immutable-in-convention candidate list shared by all scorers."""

import hashlib


def _valid(sequence, min_length, max_length):
    return isinstance(sequence, str) and sequence.isalpha() and sequence.isupper() and min_length <= len(sequence) <= max_length


def candidate_pool(query_id, training_records, *, min_length=5, max_length=30,
                   reference_sequence=None, max_retrieved=32):
    """Build deterministic pool from training linkers and GS controls.

    ``reference_sequence`` is evaluation-only; it must be passed by the
    benchmark harness *after* generation to guarantee rank measurability.
    This does not make the reference available to the inference generator.
    """
    if not query_id or not 0 < min_length <= max_length or max_retrieved < 0:
        raise ValueError("Invalid candidate pool configuration")
    sequences = set()

    def add(sequence):
        if _valid(sequence, min_length, max_length):
            sequences.add(sequence)

    for n in range(1, max_length // 5 + 1):
        add("GGGGS" * n)
    add("G" * min_length)
    training_records = list(training_records)
    if any(r.get("example_id") == query_id for r in training_records):
        raise ValueError("Query is present in the training retrieval set")
    if any(r.get("split", "train") != "train" for r in training_records):
        raise ValueError("Retrieval records must be from the training split")
    for record in sorted(training_records, key=lambda r: r["example_id"])[:max_retrieved]:
        add(record.get("linker", {}).get("sequence"))
    if reference_sequence is not None:
        if not _valid(reference_sequence, min_length, max_length):
            raise ValueError("Reference linker violates candidate constraints")
        add(reference_sequence)
    return tuple({"candidate_id": hashlib.sha256(s.encode()).hexdigest()[:16],
                  "linker_sequence": s, "linker_length": len(s),
                  "generation_method": "fixed_candidate_pool"}
                 for s in sorted(sequences))
