"""Remove public accession/position from stage-one sequence review packet."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/dfl_te82_blinded_review_packet_2026-10-12.json"
OUTPUT = ROOT / "reports/dfl_te82_sequence_only_review_packet_2026-10-12.json"


def main():
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    records = []
    for item in source["records"]:
        records.append({"case_id": item["case_id"],
                        "candidate_sequence": item["candidate_sequence"],
                        "context_sequence": item["context_sequence"],
                        "candidate_start_in_context_1based": item["start_1based"] - item["context_start_1based"] + 1,
                        "candidate_end_in_context_1based": item["end_1based"] - item["context_start_1based"] + 1,
                        "reviewer_label": None, "reviewer_confidence": None,
                        "reviewer_evidence": None})
    report = {"schema_version": "0.1.0", "status": "stage_one_sequence_only_unadjudicated",
              "instructions": "Assess whether the marked sequence appears consistent with a disordered flexible linker using only the sequence context. Choose linker, not_linker, or uncertain; supply evidence and confidence. Do not search these sequences or accessions against the published source until all first-stage decisions are frozen. Sequence alone may be insufficient: use uncertain when appropriate.",
              "records": records,
              "provenance": {"source_packet_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest()},
              "limitations": ["No domain annotation or structure is shown; this is a preliminary sequence-only review, not definitive biological adjudication.",
                              "Sequences themselves remain potentially searchable; this packet is pseudonymous, not perfectly blind."]}
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cases": len(records), "pseudonymous": True}))


if __name__ == "__main__":
    main()
