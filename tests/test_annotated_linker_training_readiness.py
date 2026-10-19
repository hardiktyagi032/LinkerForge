import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from audit_annotated_linker_training_readiness import audit_record  # noqa: E402


def example(source_key="uniprot_explicit_linker_region", status="needs_boundary_and_homology_audit"):
    sequence = "GGGGS"
    source = ({"accession": "P00001", "start_1based": 10, "end_1based": 14}
              if source_key == "uniprot_explicit_linker_region" else
              {"cluster_file": "test.gbk", "assembly_accession": "GCF_000001"})
    return {"sequence": sequence, "sequence_sha256": hashlib.sha256(sequence.encode()).hexdigest(),
            "length": len(sequence), "qualifying_source_keys": [source_key],
            "qualifying_sources": {source_key: source}, "usage_status": status,
            "provenance": {"input_sha256": "a" * 64}}


def test_valid_record_is_not_promoted_to_dfl_training():
    cleaned, errors = audit_record(example())
    assert errors == []
    assert cleaned["annotation_scope"] == "positive_linker_subsequence_only"
    assert cleaned["dfl_segmentation_training_ready"] is False
    assert cleaned["verified_nonlinker_residues_in_this_record"] == 0


def test_protected_record_remains_protected():
    cleaned, errors = audit_record(example(status="protected_benchmark"))
    assert errors == []
    assert cleaned["review_tier"] == "protected_do_not_train"


def test_coordinate_mismatch_is_rejected():
    record = example()
    record["qualifying_sources"]["uniprot_explicit_linker_region"]["end_1based"] = 15
    cleaned, errors = audit_record(record)
    assert cleaned is None
    assert "uniprot_coordinate_or_accession_error" in errors


def test_duplicate_source_key_is_rejected():
    record = example()
    record["qualifying_source_keys"].append("uniprot_explicit_linker_region")
    cleaned, errors = audit_record(record)
    assert cleaned is None
    assert "invalid_source_keys" in errors
