"""Adapter for the PR #2 source library; no rows or citations are invented here."""
from .constraints import candidate_flags
from .contracts import sequence


def template_candidates(library, request, count=8, max_substitutions=0):
    if library.get("library_id") != "linker_property_library.v1":
        raise ValueError("Expected the reviewed property-library interface from PR #2")
    if type(count) is not int or not 1 <= count <= 1024 or type(max_substitutions) is not int or not 0 <= max_substitutions <= request.length:
        raise ValueError("Invalid bounded template/substitution budget")
    candidates, attempts, seen, identities = [], [], set(), set()
    # Exact length only; source-null sequences are never expanded or guessed.
    for entry in sorted(library["entries"], key=lambda row: row["entry_id"]):
        identity = entry["entry_id"]
        if identity in identities:
            raise ValueError("Duplicate library entry ID")
        identities.add(identity)
        if entry.get("excluded_from_model") or entry.get("sequence") is None:
            attempts.append({"entry_id": identity, "status": "unavailable_source", "reasons": ["excluded_or_missing_sequence"]})
            continue
        value = sequence(entry["sequence"], "template sequence")
        source = library.get("sources", {}).get(entry.get("source_key"))
        if not source or not source.get("citation") or not entry.get("source_locator"):
            raise ValueError("Template needs its source citation and locator")
        rigidity = entry.get("rigidity", {}).get("label", "unassigned")
        cleavage = entry.get("cleavability", {}).get("label", "unassigned")
        reasons = []
        if len(value) != request.length:
            reasons.append("wrong_length")
        if request.rigidity != "unknown" and rigidity != request.rigidity:
            reasons.append("unmatched_rigidity_annotation")
        if request.cleavage == "no_known_motif" and cleavage != "non_cleavable":
            reasons.append("unmatched_source_connector_category")
        # Only the explicitly cited/positioned cassette can replace residues.
        # Original activity labels are never inherited as new measurements.
        substitutions = []
        if len(value) == request.length:
            mutable = list(value)
            for index, residue in request.locked_positions().items():
                if mutable[index] != residue:
                    substitutions.append({"position": index + 1, "from": mutable[index], "to": residue})
                    mutable[index] = residue
            value = "".join(mutable)
        if len(substitutions) > max_substitutions:
            reasons.append("substitution_budget_exceeded")
        reasons += candidate_flags(request, value)
        if not reasons and value in seen:
            reasons.append("duplicate")
        attempts.append({"entry_id": identity, "status": "rejected" if reasons else "admissible_sequence_only", "reasons": sorted(set(reasons))})
        if not reasons and len(candidates) < count:
            seen.add(value)
            candidates.append({"linker_sequence": value, "source_entry": identity, "source_sequence": entry["sequence"],
                               "citation": source["citation"], "source_locator": entry["source_locator"],
                               "substitutions": substitutions, "segments": request.segments(),
                               "source_rigidity_annotation": rigidity, "source_cleavability_annotation": cleavage,
                               "function_validated": False, "cleavage_activity_validated": False})
    return {"method": "cited_template_with_explicit_cassette_substitution", "candidates": candidates,
            "attempts": attempts, "requested": count, "returned": len(candidates),
            "limitations": ["Source non_cleavable is a category, not guaranteed resistance to every protease.",
                            "No template resizing, unknown-label inference or validation of substituted designs."]}
