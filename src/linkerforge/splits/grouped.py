"""Split complete leakage groups, never individual structures.

This is an ID/annotation audit, not a replacement for external sequence
clustering. Supply ``homology_cluster_id`` from a frozen clustering run before
calling a split blind-ready.
"""

import hashlib
import json
from collections import defaultdict


def _tokens(record):
    tokens = []
    source = record.get("source", {})
    for name in ("uniprot_id",):
        value = source.get(name)
        if value:
            tokens.append(f"{name}:{value}")
    cluster = record.get("homology_cluster_id")
    if cluster:
        tokens.append(f"homology:{cluster}")
    family_a = tuple(sorted(record.get("domain_a", {}).get("family_ids", [])))
    family_b = tuple(sorted(record.get("domain_b", {}).get("family_ids", [])))
    if family_a and family_b:
        tokens.append("architecture:" + json.dumps([family_a, family_b]))
    return tokens


def _groups(records):
    records = list(records)
    ids = [r["example_id"] for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate example_id")
    if not all(_tokens(r) for r in records):
        raise ValueError("Each example needs a UniProt ID, homology cluster, or both domain families")
    parent = {ident: ident for ident in ids}

    def find(ident):
        while parent[ident] != ident:
            parent[ident] = parent[parent[ident]]
            ident = parent[ident]
        return ident

    seen = {}
    for record in records:
        ident = record["example_id"]
        for token in _tokens(record):
            if token in seen:
                parent[find(ident)] = find(seen[token])
            else:
                seen[token] = ident
    grouped = defaultdict(list)
    for ident in ids:
        grouped[find(ident)].append(ident)
    return [sorted(group) for group in grouped.values()]


def grouped_split(records, seed=0, fractions=(0.7, 0.15, 0.15), *, require_homology_clusters=True):
    """Return example_id -> split, with entire connected groups assigned once.

    Fractions are targets, not guarantees. Large linked clusters can dominate.
    All records must be frozen before this function is used for a blind set.
    """
    records = list(records)
    if require_homology_clusters and any(not r.get("homology_cluster_id") for r in records):
        raise ValueError("Blind-ready split requires frozen homology_cluster_id for every example")
    if len(fractions) != 3 or any(x <= 0 for x in fractions) or abs(sum(fractions) - 1) > 1e-9:
        raise ValueError("fractions must be three positive values summing to one")
    groups = _groups(records)
    groups.sort(key=lambda g: (-len(g), hashlib.sha256(f"{seed}:{','.join(g)}".encode()).hexdigest()))
    names = ("train", "validation", "blind")
    counts = dict.fromkeys(names, 0)
    output = {}
    for group in groups:
        # Largest deficit against target capacity; deterministic ties.
        name = max(names, key=lambda n: (fractions[names.index(n)] * len(records) - counts[n], -names.index(n)))
        output.update({ident: name for ident in group})
        counts[name] += len(group)
    audit_split(records, output)
    return output


def audit_split(records, assignment):
    """Raise on missing IDs or ID/annotation leakage; return summary otherwise."""
    records = list(records)
    ids = {r["example_id"] for r in records}
    if set(assignment) != ids:
        raise ValueError("Split assignment must contain exactly the input example IDs")
    if set(assignment.values()) - {"train", "validation", "blind"}:
        raise ValueError("Unknown split name")
    for group in _groups(records):
        if len({assignment[ident] for ident in group}) != 1:
            raise ValueError(f"Leakage group crosses splits: {group}")
    return {name: sum(value == name for value in assignment.values()) for name in ("train", "validation", "blind")}
