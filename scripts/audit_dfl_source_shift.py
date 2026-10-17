"""Descriptive label/length/source shift audit; no model selection."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import subprocess

from audit_caid3_dld_overlap import caid_records


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "TR166_train": ROOT / "data/processed/published_dfl_splits/tr166.jsonl",
    "TE82_development": ROOT / "data/processed/published_dfl_splits/te82.jsonl",
    "TE64_retrospective": ROOT / "data/processed/published_dfl_splits/te64.jsonl",
}
CAID3 = ROOT / "artifacts/caid3-common-coverage-001/linker-common.fasta"
OUTPUT = ROOT / "reports/dfl_source_shift_audit_2026-10-12.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def spans(labels):
    result = []
    start = None
    for i, value in enumerate(labels + "!"):
        if value == "1" and start is None:
            start = i
        elif value != "1" and start is not None:
            result.append((start, i - 1))
            start = None
    return result


def describe(rows, masked):
    lengths = [len(sequence) for _, sequence, _ in rows]
    counts = Counter("".join(labels for _, _, labels in rows))
    positive = counts["1"]
    scored = positive + counts["0"]
    span_lengths = [end - start + 1 for _, _, labels in rows for start, end in spans(labels)]
    positive_proteins = sum("1" in labels for _, _, labels in rows)
    positive_residues = Counter(aa for _, sequence, labels in rows for aa, label in zip(sequence, labels) if label == "1")
    negative_residues = Counter(aa for _, sequence, labels in rows for aa, label in zip(sequence, labels) if label == "0")
    return {"proteins": len(rows), "positive_proteins": positive_proteins,
            "no_positive_proteins": len(rows) - positive_proteins,
            "total_residues": sum(lengths), "scored_residues": scored, "positive_residues": positive,
            "negative_residues": counts["0"], "masked_residues": counts["x"] if masked else None,
            "positive_fraction_of_scored": positive / scored,
            "positive_fraction_of_all": positive / sum(lengths),
            "median_protein_length": statistics.median(lengths),
            "median_positive_span_length": statistics.median(span_lengths) if span_lengths else None,
            "positive_spans": len(span_lengths),
            "positive_amino_acid_counts": dict(sorted(positive_residues.items())),
            "negative_amino_acid_counts": dict(sorted(negative_residues.items()))}


def main():
    if OUTPUT.exists():
        raise FileExistsError("Audit output already exists")
    rows = {}
    for name, path in SOURCES.items():
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        rows[name] = [(r["protein_id"], r["sequence"], r["labels"]) for r in records]
    rows["CAID3_common_public_reference"] = caid_records(CAID3)
    result = {"schema_version": "0.1.0", "status": "descriptive_shift_audit_not_model_selection",
              "sources": {name: describe(records, name != "CAID3_common_public_reference") for name, records in rows.items()},
              "provenance": {"sha256": {name: sha(path) for name, path in {**SOURCES, "CAID3_common_public_reference": CAID3}.items()},
                             "script_sha256": sha(Path(__file__)),
                             "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()},
              "limitations": ["Descriptive differences do not establish the cause of transfer failure.",
                              "The CAID3 reference is public and linker-positive only; its labels must not be used to select new models.",
                              "Sequence-family overlap and source annotation practices need separate audit."]}
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({name: {key: value for key, value in item.items() if key not in {"positive_amino_acid_counts", "negative_amino_acid_counts"}}
                      for name, item in result["sources"].items()}, indent=2))


if __name__ == "__main__":
    main()
