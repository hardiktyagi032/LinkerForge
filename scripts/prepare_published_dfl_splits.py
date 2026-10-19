"""Convert original TR166/TE82/TE64 files without changing 0/1/x labels.

Retrospective experimental splits only; not a fresh blinded benchmark.
"""

import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "artifacts/transdfl-benchmark-original"
OUTPUT = ROOT / "data/processed/published_dfl_splits"
CAID = ROOT / "artifacts/caid3-linker.fasta"
SPLITS = {"TR166": "train_original", "TE82": "development_original", "TE64": "retrospective_test_original"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    caid = {line[1:].strip().split()[0] for line in CAID.read_text(encoding="utf-8").splitlines()
            if line.startswith(">")}
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": "0.1.0", "status": "prepared_masked_retrospective_splits_not_fresh_independent_test",
                "caid3_reference_sha256": sha(CAID), "converter_sha256": sha(Path(__file__)),
                "pipeline_commit": commit, "splits": {}}
    all_ids = set()
    for name, split in SPLITS.items():
        source = INPUT / f"{name}.txt"
        lines = source.read_text(encoding="utf-8").splitlines()
        if len(lines) % 3:
            raise ValueError(f"Malformed {name}")
        source_hash = sha(source)
        rows = []
        for i in range(0, len(lines), 3):
            protein_id, sequence, labels = lines[i][1:].strip().split()[0], lines[i + 1].strip(), lines[i + 2].strip()
            if not lines[i].startswith(">") or len(sequence) != len(labels) or set(labels) - set("01x"):
                raise ValueError(f"Invalid sequence/label record: {name}:{i // 3}")
            if protein_id in caid or protein_id in all_ids:
                raise ValueError(f"Exact-ID leakage or duplicate: {protein_id}")
            all_ids.add(protein_id)
            rows.append({"schema_version": "0.1.0", "record_type": "published_dfl_sequence_labels",
                         "protein_id": protein_id, "sequence": sequence, "labels": labels,
                         "split": split, "source": f"TransDFL_{name}",
                         "provenance": {"source_url": f"http://bliulab.net/TransDFL/static/dataset/{name}.txt",
                                        "source_sha256": source_hash, "converter_sha256": manifest["converter_sha256"],
                                        "pipeline_commit": commit,
                                        "label_semantics": "1=DFL_positive;0=published_negative;x=masked_unscored"}})
        target = OUTPUT / f"{name.lower()}.jsonl"
        target.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
        manifest["splits"][name] = {"assignment": split, "source_sha256": source_hash,
                                   "output_sha256": sha(target), "records": len(rows),
                                   "positive_residues": sum(row["labels"].count("1") for row in rows),
                                   "negative_residues": sum(row["labels"].count("0") for row in rows),
                                   "masked_residues": sum(row["labels"].count("x") for row in rows),
                                   "zero_positive_proteins": sum("1" not in row["labels"] for row in rows)}
    target = OUTPUT / "manifest.json"
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest["splits"], indent=2))


if __name__ == "__main__":
    main()
