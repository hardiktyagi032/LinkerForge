"""Conservative exact-sequence/substring overlap screen; not a homology audit."""

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path


def rows(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def audit(disprot: list[dict], dld: list[dict]) -> dict:
    exact = {}
    for row in dld:
        exact.setdefault(row["sequence"], []).append({"source_id": row["source_id"], "split": row["split"]})
    counts = Counter()
    examples = []
    for row in disprot:
        seq = row["sequence"]
        matches = exact.get(seq, [])
        if not matches:
            matches = [{"source_id": item["source_id"], "split": item["split"]}
                       for item in dld if len(item["sequence"]) >= 40 and
                       (item["sequence"] in seq or seq in item["sequence"])]
            kind = "contiguous_sequence_containment" if matches else "none_found_by_exact_screen"
        else:
            kind = "identical_full_sequence"
        counts[kind] += 1
        if matches:
            examples.append({"disprot_region_id": row["region_id"], "match_kind": kind, "dld": matches[:10]})
    return {"status": "partial_overlap_screen_not_independence_certification",
            "disprot_regions": len(disprot), "dld_records": len(dld),
            "overlap_counts": dict(counts), "matches": examples,
            "limitations": ["No sequence-alignment or homology-cluster audit", "Protein fragment/isoform matches may be missed",
                            "DLD paper used older DisProt annotations; later versions may overlap by region or homology"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--disprot", required=True, type=Path)
    parser.add_argument("--dld", required=True, type=Path, nargs="+")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit(list(rows(args.disprot)), [row for path in args.dld for row in rows(path)])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "matches"}, indent=2))


if __name__ == "__main__":
    main()
