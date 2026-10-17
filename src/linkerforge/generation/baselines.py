"""Length-matched frequency and training-only contextual template baselines."""
from .constraints import candidate_flags


def template_baselines(train_examples, request, flank_residues=32):
    eligible = [e for e in train_examples if not candidate_flags(request, e.linker)
                and (request.rigidity == "unknown" or request.rigidity == e.request.rigidity)
                and (request.cleavage == "unknown" or request.cleavage == e.request.cleavage)]
    counts = {}
    for example in eligible:
        counts[example.linker] = counts.get(example.linker, 0) + 1
    frequent = min(counts, key=lambda x: (-counts[x], x)) if counts else None
    def context_score(example):
        # Unfitted 2-mer overlap, using flanks only; no target linker identity.
        def kmers(a, b):
            return {a[i:i+2] for i in range(len(a)-1)} | {b[i:i+2] for i in range(len(b)-1)}
        query = kmers(request.domain_a[-flank_residues:], request.domain_b[:flank_residues])
        candidate = kmers(example.request.domain_a[-flank_residues:], example.request.domain_b[:flank_residues])
        return len(query & candidate) / len(query | candidate) if query | candidate else 0.
    nearest = min(eligible, key=lambda e: (-context_score(e), e.record_id)) if eligible else None
    return {"length_matched_frequency": frequent,
            "training_only_context_retrieval": nearest.linker if nearest else None,
            "retrieved_training_record": nearest.record_id if nearest else None,
            "eligible_training_templates": len(eligible),
            "limitations": "Unavailable baselines remain null, never resized or fabricated; this is not SynLinker or ESM retrieval."}


def edit_distance(a, b):
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        next_row = [i]
        for j, y in enumerate(b, 1):
            next_row.append(min(next_row[-1] + 1, row[j] + 1, row[j-1] + (x != y)))
        row = next_row
    return row[-1]
