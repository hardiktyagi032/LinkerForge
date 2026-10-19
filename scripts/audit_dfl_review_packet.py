"""Verify a TE82 annotation packet against the frozen source and held key."""

import hashlib
import json
from pathlib import Path
import subprocess

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/processed/published_dfl_splits/te82.jsonl"
PACKET = ROOT / "reports/dfl_te82_blinded_review_packet_2026-10-12.json"
KEY = ROOT / "artifacts/dfl_te82_blinded_review_key_2026-10-12.json"
SCHEMA = ROOT / "schemas/dfl_blinded_review_packet_v0.1.0.schema.json"
OUTPUT = ROOT / "reports/dfl_te82_review_packet_integrity_2026-10-12.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    key = json.loads(KEY.read_text(encoding="utf-8"))
    jsonschema.validate(packet, json.loads(SCHEMA.read_text(encoding="utf-8")))
    source = {r["protein_id"]: r for line in SOURCE.read_text(encoding="utf-8").splitlines()
              if (r := json.loads(line))}
    assert sha(SOURCE) == packet["provenance"]["source_sha256"] == key["provenance"]["source_sha256"]
    assert sha(ROOT / "reports/dfl_te82_unknown_review_queue_2026-10-12.json") == packet["provenance"]["nomination_sha256"]
    assert len(packet["records"]) == len(key["records"]) == 50
    assert len({p["protein_id"] for p in packet["records"]}) == 50
    counts = {}
    for public, private in zip(packet["records"], key["records"]):
        assert public["case_id"] == private["case_id"]
        assert public["reviewer_label"] is None and public["reviewer_confidence"] is None
        assert public["reviewer_evidence"] is None
        row = source[public["protein_id"]]
        a, b = public["start_1based"], public["end_1based"]
        c, d = public["context_start_1based"], public["context_end_1based"]
        assert 1 <= c <= a <= b <= d <= len(row["sequence"])
        assert public["candidate_sequence"] == row["sequence"][a - 1:b]
        assert public["context_sequence"] == row["sequence"][c - 1:d]
        assert private["source_label"] == row["labels"][a - 1:b]
        category = private["selection_category"]
        expected = {"model_nominated_unknown": "x", "random_unknown": "x",
                    "published_positive_control": "1", "published_negative_control": "0"}[category]
        assert set(private["source_label"]) == {expected}
        counts[category] = counts.get(category, 0) + 1
    assert counts == {"model_nominated_unknown": 20, "random_unknown": 10,
                      "published_positive_control": 10, "published_negative_control": 10}
    ignored = subprocess.run(["git", "check-ignore", "-q", str(KEY)], cwd=ROOT).returncode == 0
    if not ignored:
        raise ValueError("Private answer key is not Git-ignored")
    report = {"schema_version": "0.1.0", "status": "packet_integrity_passed_not_biological_validation",
              "records": 50, "distinct_proteins": 50, "category_counts": counts,
              "private_key_git_ignored": ignored,
              "provenance": {"source_sha256": sha(SOURCE), "packet_sha256": sha(PACKET),
                             "key_sha256": sha(KEY), "schema_sha256": sha(SCHEMA),
                             "script_sha256": sha(Path(__file__)),
                             "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()},
              "limitations": ["Protein IDs and coordinates allow a reviewer to look up public source labels; instruct reviewers not to do so.",
                              "Published positive and negative controls are not independent biological truth.",
                              "No expert decisions are present yet; no biological validity or performance claim follows."]}
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "counts": counts, "key_ignored": ignored}))


if __name__ == "__main__":
    main()
