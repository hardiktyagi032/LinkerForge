"""Exploratory exact-kmer enrichment against composition-preserving shuffles.

This is a descriptive, unsupervised baseline, not proof of linker function.
"""
import argparse
import hashlib
import json
import platform
import random
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def motifs(sequence, k_values):
    return {sequence[i:i+k] for k in k_values for i in range(len(sequence)-k+1)}


def bh_qvalues(pairs):
    """Benjamini-Hochberg adjusted p-values for all tested patterns."""
    ordered = sorted(pairs, key=lambda item: item[1])
    q = {}
    running = 1.0
    n = len(ordered)
    for rank in range(n, 0, -1):
        pattern, p = ordered[rank - 1]
        running = min(running, p * n / rank)
        q[pattern] = running
    return q


def run(config_path, output_path):
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    source_path = ROOT / config["input_path"]
    audit_path = ROOT / config["component_audit_path"]
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    excluded = {pid for component in audit["components"] if component["requires_protected_split_review"] for pid in component["candidate_ids"]}
    rows = [json.loads(line) for line in source_path.read_text(encoding="utf-8").splitlines() if line]
    assert len({row["protein_id"] for row in rows}) == len(rows)
    grouped = defaultdict(list)
    total_spans = 0
    for row in rows:
        if config["exclude_transitively_protected"] and row["protein_id"] in excluded:
            continue
        for region in row["positive_regions"]:
            sequence = row["sequence"][region["start_1based"]-1:region["end_1based"]]
            if config["min_span_length"] <= len(sequence) <= config["max_span_length"]:
                assert row["labels"][region["start_1based"]-1:region["end_1based"]] == "1" * len(sequence)
                grouped[row["protein_id"]].append(sequence)
                total_spans += 1
    observed = defaultdict(set)
    k_values = config["k_values"]
    for pid, sequences in grouped.items():
        for sequence in sequences:
            for pattern in motifs(sequence, k_values):
                observed[pattern].add(pid)
    tested = {pattern for pattern, ids in observed.items() if len(ids) >= config["minimum_distinct_proteins"]}
    null_counts = {pattern: [] for pattern in tested}
    rng = random.Random(config["seed"])
    for _ in range(config["permutations"]):
        per_pattern = defaultdict(set)
        for pid, sequences in grouped.items():
            for sequence in sequences:
                letters = list(sequence)
                rng.shuffle(letters)
                for pattern in motifs("".join(letters), k_values) & tested:
                    per_pattern[pattern].add(pid)
        for pattern in tested:
            null_counts[pattern].append(len(per_pattern[pattern]))
    pvals = {pattern: (1 + sum(count >= len(observed[pattern]) for count in null_counts[pattern])) / (config["permutations"] + 1) for pattern in tested}
    qvals = bh_qvalues(list(pvals.items()))
    results = []
    for pattern in tested:
        results.append({"sequence_pattern": pattern, "length": len(pattern), "observed_proteins": len(observed[pattern]), "null_mean_proteins": round(sum(null_counts[pattern])/len(null_counts[pattern]), 3), "empirical_p": pvals[pattern], "bh_q": qvals[pattern], "protein_ids": sorted(observed[pattern])})
    results.sort(key=lambda item: (item["bh_q"], -item["observed_proteins"], item["sequence_pattern"]))
    report = {
        "schema_version": "0.1.0", "status": "exploratory_not_functionally_validated", "config": config,
        "input": {"source_type": "DisProt 2026_06 curated flexible-linker positive regions, NOT SynLinker", "path": config["input_path"]},
        "counts": {"source_proteins": len(rows), "excluded_protected_similarity_review": len(excluded), "included_proteins": len(grouped), "included_spans": total_spans, "tested_patterns": len(tested), "patterns_with_bh_q_below_0_05": sum(item["bh_q"] < .05 for item in results)},
        "patterns": results[:config["max_reported_patterns"]],
        "provenance": {"input_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(), "config_sha256": hashlib.sha256(config_bytes).hexdigest(), "component_audit_sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(), "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "python_version": platform.python_version(), "script_version": "0.1.0", "evidence_quality": "exploratory_sequence_enrichment_only"},
        "limitations": ["This pilot uses DisProt positives, not the unavailable original SynLinker row-level collection.", "The component screen is not full homology or domain-family clearance.", "Composition-preserving shuffles are a null control, not verified non-linker negatives.", "Patterns were selected for minimum observed support before BH adjustment, so q-values are descriptive and not confirmatory FDR guarantees.", "Exact short patterns can reflect low complexity or shared ancestry; no geometric or biochemical function is inferred.", "Data are not a fresh external benchmark and no detector is trained here."]
    }
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs/linker_motif_pilot_2026-10-12.json")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/linker_motif_pilot_2026-10-12.json")
    args = parser.parse_args()
    result = run(args.config, args.output)
    print(json.dumps(result["counts"], indent=2))
