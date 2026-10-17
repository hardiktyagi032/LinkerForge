"""Matched known-length development reconstruction; no structural endpoint.

Failures remain in exact-match denominators. Edit distance is reported on
valid calls separately. Family components are transitive, and all methods use
the same resampling draws. No test-set loading or threshold selection occurs.
"""
import random

from .contracts import family_components
from .baselines import edit_distance
from .constraints import candidate_flags


def compare_reconstruction(records, methods, *, bootstrap_draws=200, seed=17):
    if (not records or not methods or type(bootstrap_draws) is not int or not 0 <= bootstrap_draws <= 1000
            or len({r.record_id for r in records}) != len(records)):
        raise ValueError("Nonempty distinct development records/methods and bounded draws required")
    expected = {r.record_id for r in records}
    validated, failures = {}, {}
    for method, predictions in methods.items():
        if not isinstance(method, str) or not method or not isinstance(predictions, dict) or set(predictions) - expected:
            raise ValueError("Methods must identify exactly this development cohort without extra records")
        validated[method], failures[method] = {}, {}
        for row in records:
            value = predictions.get(row.record_id)
            flags = candidate_flags(row.request, value) if isinstance(value, str) else ["missing_failed_or_invalid"]
            if flags:
                failures[method][row.record_id] = flags
            else:
                validated[method][row.record_id] = value

    def summary(subset, name):
        calls = validated[name]
        valid = [r for r in subset if r.record_id in calls]
        exact = sum(calls.get(r.record_id) == r.linker for r in subset)
        distances = [edit_distance(calls[r.record_id], r.linker) for r in valid]
        return {"attempted_records": len(subset), "valid_calls": len(valid), "exact_matches": exact,
                "exact_match_fraction_all_attempts": exact/len(subset) if subset else None,
                "edit_distance_valid_calls_sum": sum(distances),
                "edit_distance_valid_calls_mean": sum(distances)/len(valid) if valid else None,
                "missing_failed_or_rejected": len(subset)-len(valid)}

    common = [r for r in records if all(r.record_id in validated[name] for name in methods)]
    components = family_components(records)
    common_components = family_components(common)
    names, uncertainty = list(methods), {}
    for cohort_name, cohort, groups in (("full_attempted_coverage", records, components), ("common_coverage", common, common_components)):
        contrasts = {}
        for other in names[1:]:
            deltas, rng = [], random.Random(seed)
            if len(groups) >= 2:
                for _ in range(bootstrap_draws):
                    sampled = [r for _ in groups for r in groups[rng.randrange(len(groups))]]
                    deltas.append(summary(sampled, names[0])["exact_match_fraction_all_attempts"]-
                                  summary(sampled, other)["exact_match_fraction_all_attempts"])
            deltas.sort()
            contrasts[other] = {"contrast": f"{names[0]} minus {other}", "metric": "exact_match_fraction_all_attempts",
                                "family_components": len(groups), "requested_draws": bootstrap_draws,
                                "valid_draws": len(deltas), "seed": seed,
                                "paired_percentile_95_interval": [deltas[int(.025*(len(deltas)-1))], deltas[int(.975*(len(deltas)-1))]] if deltas else None}
        uncertainty[cohort_name] = contrasts
    return {"format": "generator-development-comparison.v0", "candidate_budget": 1, "attempt_budget_per_method": 1,
            "information_track": "known_length_chosen_tandem_sites_sequence_context",
            "full_attempted_coverage": {name: summary(records, name) for name in methods},
            "common_coverage": {name: summary(common, name) for name in methods}, "common_records": len(common),
            "failure_reasons": failures, "paired_family_uncertainty": uncertainty,
            "limitations": ["Known-length sequence diagnostics, not hidden-length generation, function or structural success.",
                            "Descriptive paired family bootstrap, not uncertainty calibration or proof of independence.",
                            "Every method has one final call per record; no best-of-k or length tuning."]}
