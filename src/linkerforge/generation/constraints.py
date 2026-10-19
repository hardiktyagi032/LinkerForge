"""Residue-exact decoding controls. Admissibility does not imply function."""
import math
import torch

from .contracts import AMINO_ACIDS


def candidate_flags(request, linker):
    failures = []
    if len(linker) != request.length:
        failures.append("wrong_length")
    if set(linker) - set(request.allowed_amino_acids):
        failures.append("forbidden_residue")
    if any(position >= len(linker) or linker[position] != residue for position, residue in request.locked_positions().items()):
        failures.append("cleavage_cassette_mismatch")
    # Screen newly created linker and boundary-spanning motifs, not motifs
    # already elsewhere in either fixed domain.
    for motif in request.forbidden_motifs:
        flank = len(motif) - 1
        left, right = request.domain_a[-flank:] if flank else "", request.domain_b[:flank]
        junction = left + linker + right
        start = junction.find(motif)
        while start != -1:
            if start < len(left) + len(linker) and start + len(motif) > len(left):
                failures.append("known_forbidden_motif_at_junction")
                break
            start = junction.find(motif, start + 1)
    return sorted(set(failures))


@torch.no_grad()
def generate(model, request, count=8, max_attempts=32, seed=0, temperature=1., top_k=20):
    if type(count) is not int or type(max_attempts) is not int or not 1 <= count <= max_attempts <= 1024:
        raise ValueError("Require 1 <= count <= max_attempts <= 1024")
    if not math.isfinite(temperature) or temperature <= 0 or type(top_k) is not int or not 1 <= top_k <= 20:
        raise ValueError("Invalid sampling settings")
    device = next(model.parameters()).device
    rng = torch.Generator(device=device).manual_seed(seed)
    prompt = model.tokenizer.prompt(request, model.config)
    locked = request.locked_positions()
    allowed = [AMINO_ACIDS.index(aa) for aa in sorted(set(request.allowed_amino_acids))]
    previous = model.training
    model.eval()
    candidates, attempts, seen = [], [], set()
    try:
        for attempt in range(max_attempts):
            ids, linker, nll, scored, failure = list(prompt), "", 0., 0, None
            for position in range(request.length):
                batch = torch.tensor([ids], device=device)
                logits = model(batch, torch.ones_like(batch, dtype=torch.bool))["logits"][0, -1]
                if not torch.isfinite(logits).all():
                    failure = "nonfinite_model_output"
                    break
                if position in locked:
                    index = AMINO_ACIDS.index(locked[position])
                else:
                    filtered = torch.full_like(logits, -torch.inf)
                    filtered[allowed] = logits[allowed] / temperature
                    cutoff = torch.topk(filtered, min(top_k, len(allowed))).values[-1]
                    filtered[filtered < cutoff] = -torch.inf
                    index = int(torch.multinomial(filtered.softmax(-1), 1, generator=rng))
                    nll -= float(logits.log_softmax(-1)[index])
                    scored += 1
                linker += AMINO_ACIDS[index]
                ids.append(index)
            flags = [failure] if failure else candidate_flags(request, linker)
            if not flags and linker in seen:
                flags = ["duplicate"]
            status = "rejected" if flags else "admissible_sequence_only"
            attempts.append({"attempt": attempt, "status": status, "reasons": flags})
            if not flags:
                seen.add(linker)
                candidates.append({"linker_sequence": linker, "length": len(linker), "segments": request.segments(),
                                   "mean_free_residue_nll": nll / scored if scored else None,
                                   "scored_free_residues": scored, "status": status,
                                   "folding_expression_function_validated": False,
                                   "structure_checks": "not_run", "rigidity_validated": False,
                                   "cleavage_activity_validated": False})
            if len(candidates) == count:
                break
    finally:
        model.train(previous)
    return {"candidates": candidates, "attempts": attempts, "requested": count, "returned": len(candidates),
            "seed": seed, "information_track": "known_length_chosen_tandem_sites_sequence_context",
            "limitations": ["Likelihood is not a fusion-success probability.",
                            "No pLDDT filter, folding, protease-specificity or function validation is performed."]}
