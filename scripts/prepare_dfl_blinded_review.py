"""Make a score-blind TE82 review packet and separately held answer key.

Published 0/1 labels are controls, not asserted biological ground truth.
"""

import hashlib
import json
from pathlib import Path
import random
import subprocess

from train_dfl_masked_cnn import load


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/processed/published_dfl_splits/te82.jsonl"
NOMINATIONS = ROOT / "reports/dfl_te82_unknown_review_queue_2026-10-12.json"
PACKET = ROOT / "reports/dfl_te82_blinded_review_packet_2026-10-12.json"
KEY = ROOT / "artifacts/dfl_te82_blinded_review_key_2026-10-12.json"
SEED = 41012


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runs(labels, target):
    start = None
    for i, value in enumerate(labels + "!", 1):
        if value == target and start is None:
            start = i
        elif value != target and start is not None:
            if i - start >= 10:
                yield start, min(start + 19, i - 1)
            start = None


def main():
    if PACKET.exists() or KEY.exists():
        raise FileExistsError("Review packet/key already exists")
    rows = {row["protein_id"]: row for row in load(SOURCE)}
    high = json.loads(NOMINATIONS.read_text(encoding="utf-8"))["records"]
    if len(high) != 20 or len({r["protein_id"] for r in high}) != 20:
        raise ValueError("Expected twenty distinct high-score nominations")
    rng = random.Random(SEED)
    selected = []
    used = set()
    for item in high:
        pid = item["protein_id"]
        row = rows[pid]
        begin, end = item["start_1based"], item["end_1based"]
        if row["labels"][begin - 1:end] != "x" * (end - begin + 1):
            raise ValueError("Nomination is not wholly unknown")
        selected.append((pid, begin, end, "model_nominated_unknown", item["mean_model_score"]))
        used.add(pid)
    for label, category, count in [("x", "random_unknown", 10),
                                    ("1", "published_positive_control", 10),
                                    ("0", "published_negative_control", 10)]:
        options = [(pid, a, b) for pid, row in rows.items() if pid not in used
                   for a, b in runs(row["labels"], label)]
        rng.shuffle(options)
        taken = 0
        for pid, begin, end in options:
            if pid in used:
                continue
            selected.append((pid, begin, end, category, None))
            used.add(pid)
            taken += 1
            if taken == count:
                break
        if taken != count:
            raise ValueError(f"Insufficient distinct-protein controls: {category} {taken}/{count}")
    rng.shuffle(selected)
    public, private = [], []
    for i, (pid, begin, end, category, score) in enumerate(selected, 1):
        row = rows[pid]
        sequence = row["sequence"]
        context_begin = max(1, begin - 30)
        context_end = min(len(sequence), end + 30)
        case = f"TE82-R{i:03d}"
        public.append({"case_id": case, "protein_id": pid,
                       "start_1based": begin, "end_1based": end,
                       "candidate_sequence": sequence[begin - 1:end],
                       "context_start_1based": context_begin,
                       "context_end_1based": context_end,
                       "context_sequence": sequence[context_begin - 1:context_end],
                       "reviewer_label": None, "reviewer_confidence": None,
                       "reviewer_evidence": None})
        private.append({"case_id": case, "selection_category": category,
                        "source_label": row["labels"][begin - 1:end],
                        "model_mean_score": score})
    provenance = {"source_sha256": sha(SOURCE), "nomination_sha256": sha(NOMINATIONS),
                  "pipeline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                  "seed": SEED}
    packet = {"schema_version": "0.1.0", "status": "blinded_unadjudicated_review_packet",
              "instructions": "Independently assess whether each candidate is a disordered flexible interdomain linker; use not_linker, linker, or uncertain. Give evidence and confidence. Source labels and model scores are withheld.",
              "records": public, "provenance": provenance}
    key = {"schema_version": "0.1.0", "status": "private_review_key_not_ground_truth",
           "records": private, "provenance": provenance,
           "warning": "Do not show this key to reviewers before their decisions are frozen. Published 0/1 controls are not infallible biological ground truth."}
    PACKET.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    KEY.write_text(json.dumps(key, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"total": len(public), "categories": {c: sum(r["selection_category"] == c for r in private)
                                                  for c in sorted({r["selection_category"] for r in private})}}))


if __name__ == "__main__":
    main()
