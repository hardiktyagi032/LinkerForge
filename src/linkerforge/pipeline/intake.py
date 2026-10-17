"""Validate future supplied mining outputs, without running a detector/miner.

This private boundary deliberately produces review-queue items, not supervised
site labels or training-eligible generator examples. Calibration and biological
correctness are external reviews, not established by a valid checksum/score.
"""
import math
import re

from linkerforge.attachment.data import sequence_sha256
from linkerforge.generation.contracts import canonical_hash, sequence


def review_candidate(record):
    required = {"format", "source_id", "source_release", "source_sequence", "source_sha256", "start", "end",
                "residues", "flank_before", "flank_after", "score", "threshold_id", "abstained",
                "classifier_sha256", "calibration_sha256", "config_sha256", "pipeline_commit", "family_ids"}
    if (not isinstance(record, dict) or set(record) != required or record["format"] != "mined-linker-candidate.v0"
            or any(not isinstance(record[k], str) or not record[k].strip() for k in ("source_id", "source_release", "threshold_id"))):
        raise ValueError("Complete source/model/calibration provenance required")
    seq = sequence(record["source_sequence"], "source_sequence")
    for key in ("source_sha256", "classifier_sha256", "calibration_sha256", "config_sha256"):
        if not isinstance(record[key], str) or not re.fullmatch("[0-9a-f]{64}", record[key]):
            raise ValueError("Pinned SHA-256 identities required")
    if not isinstance(record["pipeline_commit"], str) or not re.fullmatch("[0-9a-f]{40}", record["pipeline_commit"]):
        raise ValueError("Pinned source commit required")
    start, end = record["start"], record["end"]
    if (type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(seq)
            or record["source_sha256"] != sequence_sha256(seq) or record["residues"] != seq[start-1:end]
            or record["flank_before"] != seq[max(0, start-11):start-1] or record["flank_after"] != seq[end:end+10]):
        raise ValueError("Exact 1-based inclusive span, source hash and ten-residue flanks required")
    if (type(record["score"]) not in (float, int) or not math.isfinite(record["score"]) or not 0 <= record["score"] <= 1
            or type(record["abstained"]) is not bool or not isinstance(record["family_ids"], list)
            or not record["family_ids"] or any(not isinstance(f, str) or not f for f in record["family_ids"])):
        raise ValueError("Finite score, explicit abstention and proposed family identities required")
    return {"format": "linker-candidate-review.v0", "candidate_sha256": canonical_hash(record),
            "source_id": record["source_id"], "source_sha256": record["source_sha256"],
            "evidence_tier": "predicted_span", "training_eligible": False, "site_tolerance_labels": None,
            "status": "abstained_do_not_use" if record["abstained"] else "awaiting_boundary_and_evidence_review",
            "pending_reviews": ["classifier/calibration validity and admissible mining cohort",
                "same-chain domain boundaries, complete source trace and target semantics",
                "homology/domain-family exclusions and frozen train/development assignment",
                "explicit predicted-span policy for generator use; no tolerance labels inferred"],
            "limitation": "Record consistency only; a high score or non-abstention does not establish a real linker or calibrated confidence."}
