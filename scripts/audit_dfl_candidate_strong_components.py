"""Build provisional connected components from existing strong local-alignment flags."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/dfl_positive_candidate_similarity_screen_2026-10-12.json"
OUTPUT = ROOT / "reports/dfl_candidate_strong_components_2026-10-17.json"
VALID_SOURCES = {"tr166", "te82", "te64", "caid3", "within_candidates"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    if source["status"] != "complete_local_similarity_candidate_screen":
        raise ValueError("Local screen incomplete")
    candidates = {hit["candidate_id"] for hit in source["hits"]}
    if len(candidates) != source["candidates"]:
        raise ValueError("Candidate coverage inconsistent")
    parent = {name: name for name in candidates}

    def find(name):
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    strong = []
    for hit in source["hits"]:
        if hit["other_source"] not in VALID_SOURCES:
            raise ValueError("Unknown protected source")
        if hit["strong_review_flag"]:
            strong.append(hit)
            if hit["other_source"] == "within_candidates":
                if hit["other_id"] not in candidates:
                    raise ValueError("Unknown candidate node")
                union(hit["candidate_id"], hit["other_id"])
    components = {}
    for candidate in sorted(candidates):
        components.setdefault(find(candidate), {"candidate_ids": [], "protected_anchors": [],
                                                 "strong_edges": 0})["candidate_ids"].append(candidate)
    for hit in strong:
        component = components[find(hit["candidate_id"])]
        component["strong_edges"] += 1
        if hit["other_source"] != "within_candidates":
            anchor = {"source": hit["other_source"], "protein_id": hit["other_id"]}
            if anchor not in component["protected_anchors"]:
                component["protected_anchors"].append(anchor)
    values = sorted(components.values(), key=lambda row: (-len(row["candidate_ids"]), row["candidate_ids"][0]))
    connected = sorted({candidate for row in values if row["protected_anchors"] for candidate in row["candidate_ids"]})
    result = {"schema_version": "1.0.0", "created_utc": datetime.now(timezone.utc).isoformat(),
              "status": "provisional_local_similarity_components_not_homology_certification",
              "source_sha256": sha(SOURCE), "script_sha256": sha(Path(__file__)),
              "rule": source["method"], "candidate_count": len(candidates),
              "strong_edge_count": len(strong), "component_count": len(values),
              "candidate_ids_connected_to_protected_anchor": connected,
              "connected_to_protected_count": len(connected), "components": values,
              "limitations": ["Local alignment flags are provisional, not domain-family assignments.",
                              "Unflagged candidates are not certified independent.",
                              "No CAID3 linker labels were used; CAID3 appears only as a protected sequence source."]}
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("candidate_count", "strong_edge_count",
                                                 "component_count", "connected_to_protected_count")}, indent=2))


if __name__ == "__main__":
    main()
