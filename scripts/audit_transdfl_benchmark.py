"""Audit downloaded original TransDFL benchmark files without training."""

import hashlib
import json
from pathlib import Path
import subprocess
from collections import Counter


ROOT = Path(__file__).resolve().parents[1]
FILES = {name: ROOT / "artifacts/transdfl-benchmark-original" / f"{name}.txt"
         for name in ("TR166", "TE82", "TE64")}
CAID = ROOT / "artifacts/caid3-linker.fasta"
DISPROT = ROOT / "data/raw/disprot/disprot_2026_06_regions.json"
OUTPUT = ROOT / "reports/transdfl_benchmark_audit_2026-10-12.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    caid_ids = {line[1:].strip().split()[0] for line in CAID.read_text(encoding="utf-8").splitlines()
                if line.startswith(">")}
    current_entries = {entry["disprot_id"]: entry for entry in json.loads(DISPROT.read_text(encoding="utf-8"))["data"]}
    caid_clusters = {field: {current_entries[id_].get(field) for id_ in caid_ids} - {None, ""}
                     for field in ("uniref50", "uniref90")}
    datasets = {}
    id_sets = {}
    for name, path in FILES.items():
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) % 3:
            raise ValueError(f"{name} does not have three lines per record")
        records = []
        for i in range(0, len(lines), 3):
            id_, seq, labels = lines[i][1:].strip().split()[0], lines[i + 1].strip(), lines[i + 2].strip()
            if not lines[i].startswith(">") or len(seq) != len(labels) or set(labels) - {"0", "1", "x"}:
                raise ValueError(f"Invalid three-line record in {name}, index {i // 3}")
            records.append((id_, seq, labels))
        ids = {row[0] for row in records}
        if len(ids) != len(records):
            raise ValueError(f"Duplicate IDs in {name}")
        id_sets[name] = ids
        datasets[name] = {"source_url": f"http://bliulab.net/TransDFL/static/dataset/{name}.txt",
                          "sha256": sha(path), "proteins": len(records),
                          "residues": sum(len(row[1]) for row in records),
                          "label_counts": dict(Counter("".join(row[2] for row in records))),
                          "caid3_exact_id_overlap": sorted(ids & caid_ids),
                          "current_disprot_id_mapped": sum(row[0] in current_entries for row in records),
                          "current_disprot_exact_sequence": sum(row[0] in current_entries and row[1] == current_entries[row[0]].get("sequence") for row in records),
                          "caid3_shared_uniref50": sorted(row[0] for row in records if row[0] in current_entries and current_entries[row[0]].get("uniref50") in caid_clusters["uniref50"]),
                          "caid3_shared_uniref90": sorted(row[0] for row in records if row[0] in current_entries and current_entries[row[0]].get("uniref90") in caid_clusters["uniref90"])}
    pairs = {f"{a}_{b}": sorted(id_sets[a] & id_sets[b])
             for a in id_sets for b in id_sets if a < b}
    output = {"schema_version": "0.1.0", "record_type": "transdfl_benchmark_audit",
              "provenance": {"caid3_sha256": sha(CAID), "disprot_sha256": sha(DISPROT), "script_sha256": sha(Path(__file__)),
                             "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()},
              "dataset_semantics": "original published 0/1/x labels; released source confirms x is excluded by the residue mask, while 0 and 1 are scored; x must not be converted to a negative",
              "datasets": datasets, "cross_dataset_exact_id_overlaps": pairs,
              "status": "label_mask_confirmed_homology_audit_pending"}
    OUTPUT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
