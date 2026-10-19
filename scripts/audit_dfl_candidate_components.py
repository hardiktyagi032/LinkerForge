"""Conservative transitive review of strong local-similarity flags; not a homology certification."""
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/dfl_positive_candidate_similarity_screen_2026-10-12.json"
OUTPUT = ROOT / "reports/dfl_candidate_component_audit_2026-10-12.json"
MANIFEST = ROOT / "data/processed/dfl_positive_candidates_2026_10_12.manifest.json"
RECORDS = ROOT / "data/processed/dfl_positive_candidates_2026_10_12.jsonl"
CONFIG = ROOT / "configs/dfl_autoresearch_data_gate_2026-10-12.json"
data = json.loads(SOURCE.read_text(encoding="utf-8"))
manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
parent = {}


def find(node):
    parent.setdefault(node, node)
    if parent[node] != node:
        parent[node] = find(parent[node])
    return parent[node]


def union(a, b):
    pa, pb = find(a), find(b)
    if pa != pb:
        parent[max(pa, pb)] = min(pa, pb)


records = [json.loads(line) for line in RECORDS.read_text(encoding="utf-8").splitlines() if line]
candidate_ids = {record["protein_id"] for record in records}
assert len(candidate_ids) == len(records) == manifest["records"]
assert hashlib.sha256(RECORDS.read_bytes()).hexdigest() == manifest["output_sha256"]
hit_candidate_ids = {hit["candidate_id"] for hit in data["hits"]}
assert hit_candidate_ids == candidate_ids
assert set(data["strong_flagged_candidates"]) <= candidate_ids
for record in records:
    labels = record["labels"]
    assert len(labels) == len(record["sequence"])
    assert set(labels) <= {"1", "x"}
    for region in record["positive_regions"]:
        start, end = region["start_1based"], region["end_1based"]
        assert 1 <= start <= end <= len(labels)
        assert set(labels[start - 1:end]) == {"1"}
for candidate in candidate_ids:
    find("candidate:" + candidate)
strong_hits = [hit for hit in data["hits"] if hit["strong_review_flag"]]
for hit in strong_hits:
    left = "candidate:" + hit["candidate_id"]
    right = ("candidate:" if hit["other_source"] == "within_candidates" else "protected:" + hit["other_source"] + ":") + hit["other_id"]
    union(left, right)

components = defaultdict(list)
for node in parent:
    components[find(node)].append(node)
rows = []
for members in components.values():
    candidates = sorted(x.split(":", 1)[1] for x in members if x.startswith("candidate:"))
    if not candidates:
        continue
    protected = sorted(x for x in members if x.startswith("protected:"))
    rows.append({"candidate_ids": candidates, "protected_nodes": protected, "requires_protected_split_review": bool(protected)})
rows.sort(key=lambda x: x["candidate_ids"][0])
direct = {hit["candidate_id"] for hit in strong_hits if hit["other_source"] != "within_candidates"}
transitive = {item for row in rows if row["protected_nodes"] for item in row["candidate_ids"]}
assert direct <= transitive
result = {
    "schema_version": "0.1.0",
    "status": "provisional_strong_hit_component_review_not_homology_certification",
    "source_path": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
    "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    "provenance": {"candidate_manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(), "candidate_records_sha256": hashlib.sha256(RECORDS.read_bytes()).hexdigest(), "config_sha256": hashlib.sha256(CONFIG.read_bytes()).hexdigest(), "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "script_version": "0.2.0", "evidence_quality": "provisional_local_sequence_similarity_review"},
    "method": "union-find over strong_review_flag hits only; candidate/protected nodes source-prefixed",
    "counts": {"candidate_ids_seen_in_hits": len(candidate_ids), "strong_hits": len(strong_hits), "candidate_components": len(rows), "direct_protected_flagged_candidates": len(direct), "transitively_protected_flagged_candidates": len(transitive), "additional_transitive_candidates": len(transitive - direct)},
    "additional_transitive_candidate_ids": sorted(transitive - direct),
    "components": rows,
    "limitations": ["Candidate IDs and label intervals are checked against the full source records.", "Strong local similarity is a review flag, not a domain-family assignment.", "Unflagged candidates are not certified independent or trainable."]
}
OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(result["counts"], indent=2))
