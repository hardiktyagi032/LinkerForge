"""Simple scores on a caller-supplied fixed candidate pool."""

def _target_length(query):
    features = query.get("connection_features", {})
    if "estimated_linker_length" in features:
        return float(features["estimated_linker_length"])
    # No shared frame for independent domains: 15 is a declared default.
    return 15.0


def score_candidates(query, candidates, training_records, method):
    """Return scores sorted high-first; no held-out linker is read from query.

    Available methods: fixed_gs, length_heuristic, nearest_training,
    hand_features. The last is an untrained transparent heuristic, not a
    random-forest/XGBoost reproduction.
    """
    allowed = {"fixed_gs", "length_heuristic", "nearest_training", "hand_features"}
    if method not in allowed:
        raise ValueError(f"Unknown method: {method}")
    candidates = list(candidates)
    if len({c["candidate_id"] for c in candidates}) != len(candidates):
        raise ValueError("Candidate IDs must be unique")
    train = list(training_records)
    if any(r.get("example_id") == query.get("example_id") for r in train):
        raise ValueError("Query present in training set")
    if any(r.get("split", "train") != "train" for r in train):
        raise ValueError("Baseline retrieval records must be from the training split")
    target = _target_length(query)
    train_sequences = {r.get("linker", {}).get("sequence", "") for r in train}
    output = []
    for candidate in candidates:
        sequence = candidate["linker_sequence"]
        length = len(sequence)
        if method == "fixed_gs":
            score = 1.0 if sequence == "GGGGSGGGGSGGGGS" else 0.0
        elif method == "length_heuristic":
            score = -abs(length - target)
        elif method == "nearest_training":
            # Exact training retrieval is strongest; otherwise select the
            # closest training length. This is deliberately simple.
            score = (100.0 if sequence in train_sequences else 0.0) - min(
                (abs(length - len(s)) for s in train_sequences if s), default=1000000)
        else:
            gs_fraction = sum(ch in "GS" for ch in sequence) / length
            hydrophobic_fraction = sum(ch in "AVILMFWY" for ch in sequence) / length
            score = -abs(length - target) / 30 + gs_fraction - hydrophobic_fraction
        output.append({"candidate_id": candidate["candidate_id"], "score": score, "method": method})
    return tuple(sorted(output, key=lambda row: (-row["score"], row["candidate_id"])))
