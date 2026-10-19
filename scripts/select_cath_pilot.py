"""Select simple CATH v4.4 author-numbered two-domain pilot candidates.

This only selects candidates. It does not call them verified linkers or train.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def read_families(path: Path) -> dict[str, str]:
    result = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 5:
                result[parts[0].lower()] = ".".join(parts[1:5])
    return result


def simple_pair(line: str) -> dict[str, object] | None:
    parts = line.split()
    if len(parts) != 17 or parts[1:3] != ["D02", "F00"]:
        return None
    if parts[3] != "1" or parts[10] != "1":
        return None
    chain_key = parts[0]
    if len(chain_key) != 5 or chain_key[4] == "0":
        return None
    # Two one-segment domains: [count, chain, start, iCode, chain, end, iCode].
    try:
        a_chain, a_start, a_i1, a_chain2, a_end, a_i2 = parts[4:10]
        b_chain, b_start, b_i1, b_chain2, b_end, b_i2 = parts[11:17]
        a_start, a_end = int(a_start), int(a_end)
        b_start, b_end = int(b_start), int(b_end)
    except ValueError:
        return None
    if len({a_chain, a_chain2, b_chain, b_chain2, chain_key[4]}) != 1:
        return None
    if any(code != "-" for code in (a_i1, a_i2, b_i1, b_i2)):
        return None
    gap = b_start - a_end - 1
    if not (a_start > 0 and a_end - a_start + 1 >= 40 and b_end - b_start + 1 >= 40 and 5 <= gap <= 30):
        return None
    return {
        "pdb_id": chain_key[:4].upper(), "chain_id": chain_key[4],
        "domain_a_start_author": a_start, "domain_a_end_author": a_end,
        "linker_start_author": a_end + 1, "linker_end_author": b_start - 1,
        "domain_b_start_author": b_start, "domain_b_end_author": b_end,
        "linker_length_author": gap,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--boundaries", type=Path, required=True)
    parser.add_argument("--domain-list", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    families_by_domain = read_families(args.domain_list)
    rows = []
    with args.boundaries.open(encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            pair = simple_pair(line)
            if pair is None:
                continue
            root = (pair["pdb_id"] + pair["chain_id"]).lower()
            families = [families_by_domain.get(root + suffix) for suffix in ("01", "02")]
            pair["family_a"] = families[0] or ""
            pair["family_b"] = families[1] or ""
            pair["family_annotations"] = sum(bool(f) for f in families)
            rows.append(pair)
    rows.sort(key=lambda row: (-row["family_annotations"], row["linker_length_author"], row["pdb_id"], row["chain_id"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)
    print(f"candidates={len(rows)} both_annotated={sum(r['family_annotations'] == 2 for r in rows)} one_annotated={sum(r['family_annotations'] == 1 for r in rows)}")


if __name__ == "__main__":
    main()
