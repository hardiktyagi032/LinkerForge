"""Count large-scale domain-gap candidates without saving protein records.

This is a throughput/yield probe, not a linker labeler. It reads two public
InterPro streams and writes only aggregate counts and source headers.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from itertools import groupby
from pathlib import Path
from urllib.request import Request, urlopen


BASE = "https://ftp.ebi.ac.uk/pub/databases/interpro/releases/110.0/"


def domain_ids(url: str) -> set[str]:
    with urlopen(Request(url, headers={"User-Agent": "LinkerForge-probe/0.1"}), timeout=60) as response:
        reader = csv.DictReader((line.decode("utf-8") for line in response), delimiter="\t")
        return {row["ENTRY_AC"] for row in reader if row["ENTRY_TYPE"].lower() == "domain"}


def candidate_pairs(annotations: list[tuple[str, int, int]]) -> list[tuple]:
    # Same or highly overlapping member-signature hits are not separate domains.
    unique = sorted(set(annotations), key=lambda row: (row[1], row[2], row[0]))
    found = []
    for i, (entry_a, start_a, end_a) in enumerate(unique):
        if end_a - start_a + 1 < 40:
            continue
        for entry_b, start_b, end_b in unique[i + 1:]:
            gap = start_b - end_a - 1
            if gap > 30:
                break
            if 5 <= gap <= 30 and end_b - start_b + 1 >= 40:
                found.append((entry_a, start_a, end_a, entry_b, start_b, end_b))
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=BASE)
    parser.add_argument("--max-proteins", type=int, default=100_000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.max_proteins < 1:
        raise ValueError("max-proteins must be positive")
    root = args.base.rstrip("/") + "/"
    domain_set = domain_ids(root + "entry.list")
    response = urlopen(Request(root + "protein2ipr.dat.gz",
                               headers={"User-Agent": "LinkerForge-probe/0.1"}), timeout=60)
    headers = {key: response.headers.get(key) for key in ("ETag", "Last-Modified", "Content-Length")}
    counts = {"proteins_seen": 0, "proteins_with_domain_matches": 0,
              "proteins_with_candidate_gap": 0, "candidate_pairs": 0,
              "malformed_rows": 0}
    last_accession = ""
    try:
        lines = (line.decode("utf-8") for line in gzip.GzipFile(fileobj=response))
        for accession, group in groupby(lines, key=lambda line: line.split("\t", 1)[0]):
            if accession < last_accession:
                raise ValueError("InterPro stream not sorted by accession; cannot group safely")
            last_accession = accession
            counts["proteins_seen"] += 1
            annotations = []
            for line in group:
                fields = line.rstrip("\n").split("\t")
                if len(fields) != 6:
                    counts["malformed_rows"] += 1
                    continue
                _, entry, _, _, start, end = fields
                if entry not in domain_set:
                    continue
                try:
                    annotations.append((entry, int(start), int(end)))
                except ValueError:
                    counts["malformed_rows"] += 1
            if annotations:
                counts["proteins_with_domain_matches"] += 1
                pairs = candidate_pairs(annotations)
                if pairs:
                    counts["proteins_with_candidate_gap"] += 1
                    counts["candidate_pairs"] += len(pairs)
            if counts["proteins_seen"] >= args.max_proteins:
                break
    finally:
        response.close()
    report = {"status": "unlabeled_domain_gap_yield_probe", "counts": counts,
              "interpro_domain_entry_count": len(domain_set),
              "source_url": root + "protein2ipr.dat.gz", "source_headers": headers,
              "notes": "No sequences, linker labels, or per-protein records were saved. Candidate gaps are not confirmed linkers."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(counts), flush=True)


if __name__ == "__main__":
    main()
