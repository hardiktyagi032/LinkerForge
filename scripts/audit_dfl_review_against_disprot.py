"""Retrospective annotation crosswalk; absence in DisProt is NOT a negative."""

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
import subprocess

from scipy.stats import fisher_exact


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "reports/dfl_te82_blinded_review_packet_2026-10-12.json"
KEY = ROOT / "artifacts/dfl_te82_blinded_review_key_2026-10-12.json"
ANNOTATIONS = ROOT / "data/processed/disprot_2026_06_flexible_linkers.jsonl"
SOURCE = ROOT / "data/processed/published_dfl_splits/te82.jsonl"
OUTPUT = ROOT / "artifacts/dfl_te82_disprot_annotation_crosswalk_2026-10-12.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    packet = json.loads(PACKET.read_text(encoding="utf-8"))["records"]
    key = json.loads(KEY.read_text(encoding="utf-8"))["records"]
    source = {r["protein_id"]: r for line in SOURCE.read_text(encoding="utf-8").splitlines()
              if (r := json.loads(line))}
    annotations = defaultdict(list)
    for line in ANNOTATIONS.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        annotations[record["disprot_id"]].append(record)
    rows = []
    for case, secret in zip(packet, key):
        if case["case_id"] != secret["case_id"]:
            raise ValueError("Packet/key mismatch")
        pid = case["protein_id"]
        seq = source[pid]["sequence"]
        begin, end = case["start_1based"], case["end_1based"]
        if case["candidate_sequence"] != seq[begin - 1:end]:
            raise ValueError("Case/source sequence mismatch")
        hits, sequence_mismatch = [], False
        for annotation in annotations.get(pid, []):
            if annotation["sequence"] != seq:
                sequence_mismatch = True
                continue
            linker = annotation["linker"]
            overlap = max(0, min(end, linker["end"]) - max(begin, linker["start"]) + 1)
            if overlap:
                hits.append({"region_id": annotation["region_id"],
                             "annotated_start_1based": linker["start"],
                             "annotated_end_1based": linker["end"],
                             "overlap_residues": overlap,
                             "reference_id": annotation["evidence"]["reference_id"],
                             "eco_id": annotation["evidence"]["eco_id"]})
        rows.append({"case_id": case["case_id"], "protein_id": pid,
                     "start_1based": begin, "end_1based": end,
                     "selection_category": secret["selection_category"],
                     "published_label": secret["source_label"],
                     "same_sequence_curated_overlap": bool(hits),
                     "same_id_sequence_mismatch": sequence_mismatch,
                     "curated_hits": hits,
                     "interpretation": "curated_flexible_linker_support" if hits else "no_curated_overlap_unknown_not_negative"})
    categories = sorted({r["selection_category"] for r in rows})
    counts = {category: {"cases": sum(r["selection_category"] == category for r in rows),
                         "curated_overlaps": sum(r["selection_category"] == category and r["same_sequence_curated_overlap"] for r in rows),
                         "sequence_mismatches": sum(r["selection_category"] == category and r["same_id_sequence_mismatch"] for r in rows)}
              for category in categories}
    high = counts["model_nominated_unknown"]
    random = counts["random_unknown"]
    odds, p = fisher_exact([[high["curated_overlaps"], high["cases"] - high["curated_overlaps"]],
                            [random["curated_overlaps"], random["cases"] - random["curated_overlaps"]]])
    report = {"schema_version": "0.1.0", "status": "retrospective_curated_annotation_crosswalk_not_independent_test",
              "categories": counts, "unknown_enrichment_exploratory": {"odds_ratio": odds if math.isfinite(odds) else None,
                                                                         "odds_ratio_note": "infinite_or_undefined_due_to_zero_cell" if not math.isfinite(odds) else None,
                                                                         "fisher_p_two_sided": p},
              "records": rows,
              "provenance": {"packet_sha256": sha(PACKET), "key_sha256": sha(KEY),
                             "source_sha256": sha(SOURCE), "annotation_sha256": sha(ANNOTATIONS),
                             "script_sha256": sha(Path(__file__)),
                             "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()},
              "limitations": ["No same-sequence curated overlap means unannotated, not a confirmed negative.",
                              "DisProt 2026 and TransDFL labels are not independent biological sources.",
                              "Case selection is model-informed; this retrospective crosswalk is not a blind accuracy estimate.",
                              "Full expert adjudication and family-aware external testing remain outstanding."]}
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"categories": counts, "odds_ratio": odds, "p": p}, indent=2))


if __name__ == "__main__":
    main()
