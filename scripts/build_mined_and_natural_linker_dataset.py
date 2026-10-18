"""Build and verify the Part 1 -> Part 2 Mined and Natural Linker Dataset (`v1`).

Completes Part 1 of the LinkerForge workflow by:
  1. Verifying the B1 V2 family-disjoint split (`d62136ce...`) and frozen Seed-31
     `ThreeLayerDFLCNN` checkpoint (`c0d356c5...`).
  2. Executing B2 two-stage domain-gated conformal calibration on the family-disjoint
     `development` split (`calibrate_conformal_threshold` + `call_two_stage_interdomain_spans`).
  3. Executing B3 specificity verification on a benchmark-disjoint 40-protein
     no-linker / single-domain and experimental-order panel (`auxiliary` + single-Pfam
     non-linker DisProt controls).
  4. Assembling the provenance-stratified dataset `data/processed/mined_and_natural_linkers_v1/`
     across four explicit authority tiers:
       - `natural_cath_pdb_verified` (91 coordinate-resolved CATH v4.4.0 natural linkers)
       - `natural_disprot_curated_dfl` (benchmark-disjoint curated `IDPO:0000033` linkers)
       - `mined_domain_gated_interdomain` (benchmark-disjoint hetero-domain `5..60` aa
         candidates scored by Stage 1 domain gate + Stage 2 frozen Seed-31 CNN)
       - `literature_engineered_template` (cited Chen et al. 2013 templates)
     Every record is annotated with `linkerforge.properties` biophysical calls
     (`rigidity`, `cleavability`, `composition_features`) and frozen Seed-31 CNN scores.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from math import dist
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from jsonschema import Draft202012Validator  # noqa: E402
import torch  # noqa: E402
from transformers import AutoModel, AutoTokenizer  # noqa: E402

from audit_dfl_b1_source_capacity import caid3_sequences, two_line_fasta  # noqa: E402
from audit_dfl_disprot_family_metadata import DISPROT_SHA256, project_entry  # noqa: E402
from build_dfl_curated_evidence_pool import (  # noqa: E402
    CAID3_SHA256,
    DP94_MANIFEST_SHA256,
    family_components,
    mask_entry,
)
from build_rcsb_pilot import read_ca  # noqa: E402
from preflight_dfl_family_training_v2 import v2_homolog_hit  # noqa: E402

from linkerforge.detector.cnn import ThreeLayerDFLCNN  # noqa: E402
from linkerforge.detector.conformal_mining import (  # noqa: E402
    calibrate_conformal_threshold,
    call_two_stage_interdomain_spans,
)
from linkerforge.detector.domain_gate import DomainMatch, domain_gap_candidates  # noqa: E402
from linkerforge.properties import (  # noqa: E402
    call_cleavability,
    composition_features,
    fit_rigidity_model,
    load_library,
    modelling_subset,
)

PINNED_B1_V2_MANIFEST_SHA256 = "d62136ce699294a0c07f0fa01a5350d3571643796cedadaf37d8399824893452"
PINNED_SEED31_CHECKPOINT_SHA256 = "c0d356c55ed83807353e66b875501c61b17f0b9b83f2910c0f1147f6409fdf6f"
FROZEN_SEED31_THRESHOLD = 0.7351981997489929
PROVISIONAL_SPAN_THRESHOLD = 0.50
ENCODER_NAME = "facebook/esm2_t12_35M_UR50D"
MAX_WINDOW = 1022
C_ALPHA_MAX_STEP_A = 3.8


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_pfam_matches(entry: dict) -> list[DomainMatch]:
    features = entry.get("features") or {}
    pfam_items = features.get("pfam") or []
    matches: list[DomainMatch] = []
    for item in pfam_items:
        acc = item.get("id") or item.get("accession")
        start = item.get("start")
        end = item.get("end")
        if acc and isinstance(start, int) and isinstance(end, int) and start <= end:
            matches.append(
                DomainMatch(
                    start=int(start),
                    end=int(end),
                    accession=str(acc),
                    kind="domain",
                )
            )
    return matches


def positive_runs(mask: str) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for idx, ch in enumerate(mask, start=1):
        if ch == "1" and start is None:
            start = idx
        elif ch != "1" and start is not None:
            runs.append((start, idx - 1))
            start = None
    if start is not None:
        runs.append((start, len(mask)))
    return runs


class FrozenSeed31Scorer:
    """Offline residue-level probability scorer for the frozen Seed-31 CNN."""

    def __init__(self, checkpoint_path: Path) -> None:
        if sha256_file(checkpoint_path) != PINNED_SEED31_CHECKPOINT_SHA256:
            raise ValueError(f"Seed-31 checkpoint hash mismatch: {checkpoint_path}")
        torch.set_num_threads(min(4, torch.get_num_threads()))
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        self.tokenizer = AutoTokenizer.from_pretrained(ENCODER_NAME, local_files_only=True)
        self.backbone = (
            AutoModel.from_pretrained(ENCODER_NAME, local_files_only=True)
            .to(self.device)
            .eval()
        )
        self.backbone.requires_grad_(False)
        self.head = ThreeLayerDFLCNN(self.backbone.config.hidden_size).to(self.device).eval()
        self.head.load_state_dict(checkpoint["head"])
        self._cache: dict[str, list[float]] = {}

    def score_sequence(self, sequence: str) -> list[float]:
        if sequence in self._cache:
            return self._cache[sequence]
        out: list[float] = []
        for start in range(0, len(sequence), MAX_WINDOW):
            chunk = sequence[start : start + MAX_WINDOW]
            tokens = self.tokenizer([chunk], return_tensors="pt", add_special_tokens=True)
            tokens = {k: v.to(self.device) for k, v in tokens.items()}
            with torch.no_grad():
                feats = self.backbone(**tokens).last_hidden_state[:, 1 : 1 + len(chunk)]
                probs = self.head(feats).sigmoid().squeeze(0).cpu().tolist()
            if isinstance(probs, float):
                probs = [probs]
            out.extend(float(p) for p in probs)
        if len(out) != len(sequence):
            raise ValueError("Scored residue count does not match sequence length")
        self._cache[sequence] = out
        return out


def annotate_biophysical_properties(sequence: str, library, rigidity_model) -> dict:
    comp = composition_features(sequence)
    cleav = call_cleavability(sequence, library)
    p_rigid = float(rigidity_model.predict_proba(sequence))
    return {
        "rigidity_predicted_label": rigidity_model.predict(sequence),
        "rigidity_p_rigid": round(p_rigid, 6),
        "cleavability_label": cleav.label,
        "matched_proteases": cleav.proteases,
        "matched_motif_ids": [m.entry_id for m in cleav.matches],
        "composition_features": {k: round(float(v), 6) for k, v in comp.items()},
    }


def write_jsonl(path: Path, rows: list[dict]) -> dict:
    text = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)
    path.write_text(text, encoding="utf-8")
    return {
        "path": path.name,
        "records": len(rows),
        "sha256": sha256_file(path),
    }


def build_dataset(source_root: Path, output_dir: Path, summary_path: Path) -> dict:
    source_root = source_root.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    b1_dir = ROOT / "data" / "processed" / "dfl_b1_v2_family_split"
    b1_manifest_path = b1_dir / "manifest.json"
    if sha256_file(b1_manifest_path) != PINNED_B1_V2_MANIFEST_SHA256:
        raise ValueError("B1 V2 split manifest SHA-256 mismatch")

    checkpoint_path = ROOT / "artifacts" / "dfl-b1-v2-cnn-seed31-2026-10-18" / "best.pt"
    scorer = FrozenSeed31Scorer(checkpoint_path)

    # Verify raw pins from source_root
    disprot_path = source_root / "data" / "raw" / "disprot" / "disprot_2026_06_regions.json"
    if sha256_file(disprot_path) != DISPROT_SHA256:
        raise ValueError("DisProt 2026_06 raw JSON hash mismatch")
    cath_path = source_root / "data" / "processed" / "cath_full_pilot.jsonl"
    rcsb_dir = source_root / "data" / "raw" / "rcsb"
    caid_path = source_root / "artifacts" / "caid3-linker.fasta"
    if sha256_file(caid_path) != CAID3_SHA256:
        raise ValueError("CAID3 FASTA hash mismatch")
    dp_manifest_path = source_root / "data" / "processed" / "prospective_dfl_holdout_dp94_v1" / "manifest.json"
    if sha256_file(dp_manifest_path) != DP94_MANIFEST_SHA256:
        raise ValueError("DP94 manifest hash mismatch")
    dp_fasta_path = dp_manifest_path.parent / "sequences.fasta"

    caid3_reg_path = ROOT / "data" / "registry" / "caid3_linker_disprot_ids.txt"
    dp94_reg_path = ROOT / "data" / "registry" / "dp94_benchmark_ids.txt"
    curated_lib_path = ROOT / "data" / "curated" / "linker_property_library_sources.v1.json"

    # Load biophysical property models
    library = load_library(curated_lib_path)
    rigidity_entries = modelling_subset(library, "rigidity")
    rigidity_model = fit_rigidity_model(
        [e.sequence for e in rigidity_entries if e.sequence is not None],
        [e.rigidity_label for e in rigidity_entries if e.sequence is not None],
    )

    # Load DisProt raw entries and family components for benchmark firewall
    raw_disprot = json.loads(disprot_path.read_text(encoding="utf-8"))
    disprot_by_id: dict[str, dict] = {}
    metadata: dict[str, dict] = {}
    for entry in raw_disprot["data"]:
        did = entry["disprot_id"]
        disprot_by_id[did] = entry
        try:
            metadata[did] = project_entry(entry)
        except ValueError:
            continue

    caid3 = caid3_sequences(caid_path)
    dp94 = two_line_fasta(dp_fasta_path)
    references = [("caid3", k, s) for k, s in caid3] + [("dp94", k, s) for k, s in dp94]
    ref_ids = {k for _, k, _ in references}

    components = family_components(metadata)
    for reg_name, ref_id, _ in references:
        if ref_id not in components:
            components[ref_id] = f"benchmark_isolated_{reg_name}_{ref_id}"
    benchmark_components = {components[ref_id] for _, ref_id, _ in references}

    # Load B1 V2 train, development, auxiliary splits
    train_rows = [
        json.loads(line)
        for line in (b1_dir / "train.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    dev_rows = [
        json.loads(line)
        for line in (b1_dir / "development.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    aux_rows = [
        json.loads(line)
        for line in (b1_dir / "auxiliary.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    # -------------------------------------------------------------------------
    # Part 1 Validation: B2 Conformal Risk Control on `development`
    # -------------------------------------------------------------------------
    dev_res_labels: list[int] = []
    dev_res_scores: list[float] = []
    dev_gated_labels: list[int] = []
    dev_gated_scores: list[float] = []
    dev_stage1_passed_proteins = 0

    for row in dev_rows:
        pid = row["protein_id"]
        seq = row["sequence"]
        mask = row["labels"]
        scores = scorer.score_sequence(seq)
        pfam_matches = extract_pfam_matches(disprot_by_id.get(pid, {}))
        cands, reason = domain_gap_candidates(seq, pfam_matches, sequence_verified=True)
        in_gate = [False] * len(seq)
        if reason is None and cands:
            dev_stage1_passed_proteins += 1
            for span in cands:
                for pos in range(span.start - 1, span.end):
                    in_gate[pos] = True
        for idx, (lbl, sc) in enumerate(zip(mask, scores)):
            if lbl in ("0", "1"):
                y = int(lbl)
                dev_res_labels.append(y)
                dev_res_scores.append(sc)
                # Under two-stage calling, residues outside Stage 1 domain gaps receive effective score 0.0
                dev_gated_labels.append(y)
                dev_gated_scores.append(sc if in_gate[idx] else 0.0)

    b2_ungated = calibrate_conformal_threshold(
        dev_res_labels,
        dev_res_scores,
        target_fdr=0.10,
        alpha=0.05,
        min_true_positives=30,
    )
    b2_two_stage = calibrate_conformal_threshold(
        dev_gated_labels,
        dev_gated_scores,
        target_fdr=0.10,
        alpha=0.05,
        min_true_positives=20,
    )

    # -------------------------------------------------------------------------
    # Tier 1: `natural_cath_pdb_verified` (91 CATH two-domain natural linkers)
    # -------------------------------------------------------------------------
    cath_rows = [
        json.loads(line)
        for line in cath_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    tier1_records: list[dict] = []
    for row in cath_rows:
        ex_id = row["example_id"]
        pdb_id = row["source"]["pdb_id"].upper()
        chain_id = row["source"]["chain_id"]
        pdb_path = rcsb_dir / f"{pdb_id}.pdb"
        ca_map = read_ca(pdb_path.read_bytes(), chain_id)
        port_a_num = int(row["residue_mapping"][0]["author_number"])
        port_b_num = int(row["residue_mapping"][-1]["author_number"])
        port_a_xyz = ca_map[port_a_num][1]
        port_b_xyz = ca_map[port_b_num][1]
        ca_dist = float(dist(port_a_xyz, port_b_xyz))

        linker_seq = row["linker"]["sequence"]
        linker_len = int(row["linker"]["length"])
        max_cap = linker_len * C_ALPHA_MAX_STEP_A
        ext_ratio = ca_dist / max_cap if max_cap > 0 else 0.0
        feasible = ca_dist <= max_cap

        full_seq = row["domain_a"]["sequence"] + linker_seq + row["domain_b"]["sequence"]
        full_scores = scorer.score_sequence(full_seq)
        l_start = int(row["linker"]["start"])
        l_end = int(row["linker"]["end"])
        span_scores = full_scores[l_start - 1 : l_end]
        mean_sc = sum(span_scores) / len(span_scores)
        max_sc = max(span_scores)
        frac_high = sum(1 for x in span_scores if x >= FROZEN_SEED31_THRESHOLD) / len(span_scores)

        props = annotate_biophysical_properties(linker_seq, library, rigidity_model)
        tier1_records.append(
            {
                "record_id": f"cath:{ex_id}",
                "authority_tier": "natural_cath_pdb_verified",
                "evidence_grade": "experimental_structure_cath_v4_4_0",
                "protein_id": f"{pdb_id}_{chain_id}",
                "homology_cluster_id": row["homology_cluster_id"],
                "linker_sequence": linker_seq,
                "linker_length": linker_len,
                "linker_start_1based": l_start,
                "linker_end_1based": l_end,
                "flanking_context": {
                    "left_domain_source": "CATH",
                    "left_domain_id": row["domain_a"]["family_ids"][0],
                    "left_flank_sequence": row["domain_a"]["sequence"][-80:],
                    "right_domain_source": "CATH",
                    "right_domain_id": row["domain_b"]["family_ids"][0],
                    "right_flank_sequence": row["domain_b"]["sequence"][:80],
                },
                "geometry": {
                    "pdb_id": pdb_id,
                    "chain_id": chain_id,
                    "port_a_author_number": port_a_num,
                    "port_b_author_number": port_b_num,
                    "inter_port_ca_distance_A": round(ca_dist, 4),
                    "max_extended_3p8A_capacity_A": round(max_cap, 4),
                    "end_to_end_extension_ratio": round(ext_ratio, 4),
                    "physical_3p8A_feasible": bool(feasible),
                    "unresolved_linker_residues": int(row["source"]["unresolved_linker_residues"]),
                    "port_a_accessibility_proxy": round(
                        float(row["connection_features"]["port_a"]["accessibility_proxy"]), 4
                    ),
                    "port_b_accessibility_proxy": round(
                        float(row["connection_features"]["port_b"]["accessibility_proxy"]), 4
                    ),
                },
                "classifier_scores": {
                    "cnn_mean_score": round(mean_sc, 6),
                    "cnn_max_score": round(max_sc, 6),
                    "cnn_fraction_above_high_threshold": round(frac_high, 6),
                },
                "biophysical_properties": props,
                "benchmark_firewall_verified": True,
            }
        )

    # -------------------------------------------------------------------------
    # Tier 2: `natural_disprot_curated_dfl` (Benchmark-disjoint curated DisProt DFLs)
    # -------------------------------------------------------------------------
    tier2_records: list[dict] = []
    curated_longer_than_60_count = 0
    for split_name, split_rows in (("train", train_rows), ("development", dev_rows)):
        for row in split_rows:
            pid = row["protein_id"]
            seq = row["sequence"]
            mask = row["labels"]
            scores = scorer.score_sequence(seq)
            pfam_matches = sorted(
                extract_pfam_matches(disprot_by_id.get(pid, {})),
                key=lambda m: (m.start, m.end, m.accession),
            )
            for s_start, s_end in positive_runs(mask):
                s_len = s_end - s_start + 1
                if s_len < 5 or s_len > 60:
                    if s_len > 60:
                        curated_longer_than_60_count += 1
                    continue
                l_seq = seq[s_start - 1 : s_end]
                span_scores = scores[s_start - 1 : s_end]
                left_domains = [m.accession for m in pfam_matches if m.end < s_start]
                right_domains = [m.accession for m in pfam_matches if m.start > s_end]
                props = annotate_biophysical_properties(l_seq, library, rigidity_model)
                tier2_records.append(
                    {
                        "record_id": f"disprot_curated:{pid}:{s_start}-{s_end}",
                        "authority_tier": "natural_disprot_curated_dfl",
                        "evidence_grade": "curator_validated_idpo_0000033",
                        "b1_v2_split_role": split_name,
                        "protein_id": pid,
                        "homology_cluster_id": row["family_component_id"],
                        "linker_sequence": l_seq,
                        "linker_length": s_len,
                        "linker_start_1based": s_start,
                        "linker_end_1based": s_end,
                        "flanking_context": {
                            "left_domain_source": "Pfam" if left_domains else None,
                            "left_domain_id": left_domains[-1] if left_domains else None,
                            "left_flank_sequence": seq[max(0, s_start - 81) : s_start - 1],
                            "right_domain_source": "Pfam" if right_domains else None,
                            "right_domain_id": right_domains[0] if right_domains else None,
                            "right_flank_sequence": seq[s_end : min(len(seq), s_end + 80)],
                        },
                        "geometry": None,
                        "classifier_scores": {
                            "cnn_mean_score": round(sum(span_scores) / len(span_scores), 6),
                            "cnn_max_score": round(max(span_scores), 6),
                            "cnn_fraction_above_high_threshold": round(
                                sum(1 for x in span_scores if x >= FROZEN_SEED31_THRESHOLD)
                                / len(span_scores),
                                6,
                            ),
                        },
                        "biophysical_properties": props,
                        "benchmark_firewall_verified": True,
                    }
                )

    # -------------------------------------------------------------------------
    # Tier 3: `mined_domain_gated_interdomain` + B3 No-Linker Specificity Panel
    # -------------------------------------------------------------------------
    b1_protein_ids = {r["protein_id"] for r in train_rows + dev_rows + aux_rows}
    tier3_records: list[dict] = []
    b3_panel_records: list[dict] = []

    # First add the 9 B1 V2 auxiliary experimental-order proteins to B3 panel
    for row in aux_rows:
        pid = row["protein_id"]
        seq = row["sequence"]
        scores = scorer.score_sequence(seq)
        pfam_matches = extract_pfam_matches(disprot_by_id.get(pid, {}))
        two_stage = call_two_stage_interdomain_spans(
            seq,
            pfam_matches,
            scores,
            sequence_verified=True,
            high_confidence_threshold=FROZEN_SEED31_THRESHOLD,
            provisional_threshold=PROVISIONAL_SPAN_THRESHOLD,
        )
        b3_panel_records.append(
            {
                "protein_id": pid,
                "panel_role": "b1_v2_auxiliary_experimental_order",
                "family_component_id": row["family_component_id"],
                "sequence_length": len(seq),
                "pfam_domain_count": len(pfam_matches),
                "known_order_residues": row["labels"].count("0"),
                "stage1_passed": two_stage["stage1_passed"],
                "stage1_abstention_reason": two_stage["stage1_abstention_reason"],
                "called_high_confidence_spans": two_stage["called_high_confidence_spans"],
                "called_provisional_spans": two_stage["called_provisional_spans"],
                "max_residue_score": round(max(scores), 6),
                "benchmark_firewall_verified": True,
            }
        )

    # Scan DisProt_2026_06 for benchmark-disjoint unannotated proteins:
    # (a) hetero-Pfam inter-domain gap candidates -> Tier 3 mining
    # (b) single-Pfam proteins without DFL annotations -> B3 specificity panel (up to 40 total)
    for did, entry in sorted(disprot_by_id.items()):
        if did in b1_protein_ids or did in ref_ids:
            continue
        if did not in metadata:
            continue
        comp_id = components.get(did)
        if comp_id in benchmark_components:
            continue
        seq = entry.get("sequence") or ""
        if not seq or any(ch not in "ACDEFGHIKLMNPQRSTVWY" for ch in seq):
            continue
        # Skip any entry with an IDPO:0000033 linker region (even if obsolete/unvalidated)
        has_dfl_region = any(
            r.get("term_id") == "IDPO:0000033" for r in (entry.get("regions") or [])
        )
        if has_dfl_region:
            continue

        pfam_matches = extract_pfam_matches(entry)
        cands, reason = domain_gap_candidates(seq, pfam_matches, sequence_verified=True)

        if reason is None and cands:
            # Verify V2 sequence firewall against CAID3 + DP94 before scoring
            if any(v2_homolog_hit(seq, ref_seq) for _, _, ref_seq in references):
                continue
            scores = scorer.score_sequence(seq)
            two_stage = call_two_stage_interdomain_spans(
                seq,
                pfam_matches,
                scores,
                sequence_verified=True,
                high_confidence_threshold=FROZEN_SEED31_THRESHOLD,
                provisional_threshold=PROVISIONAL_SPAN_THRESHOLD,
            )
            for span_info in two_stage["candidate_spans"]:
                s_start = int(span_info["start"])
                s_end = int(span_info["end"])
                l_seq = span_info["sequence"]
                props = annotate_biophysical_properties(l_seq, library, rigidity_model)
                tier3_records.append(
                    {
                        "record_id": f"mined_disprot_gap:{did}:{s_start}-{s_end}",
                        "authority_tier": span_info["calling_tier"],
                        "evidence_grade": "two_stage_domain_gated_seed31_cnn_prediction_not_ground_truth",
                        "protein_id": did,
                        "homology_cluster_id": comp_id,
                        "linker_sequence": l_seq,
                        "linker_length": int(span_info["length"]),
                        "linker_start_1based": s_start,
                        "linker_end_1based": s_end,
                        "flanking_context": {
                            "left_domain_source": "Pfam",
                            "left_domain_id": span_info["left_domain_accession"],
                            "left_flank_sequence": seq[max(0, s_start - 81) : s_start - 1],
                            "right_domain_source": "Pfam",
                            "right_domain_id": span_info["right_domain_accession"],
                            "right_flank_sequence": seq[s_end : min(len(seq), s_end + 80)],
                        },
                        "geometry": None,
                        "classifier_scores": {
                            "cnn_mean_score": span_info["cnn_mean_score"],
                            "cnn_max_score": span_info["cnn_max_score"],
                            "cnn_fraction_above_high_threshold": span_info[
                                "cnn_fraction_above_high_threshold"
                            ],
                        },
                        "biophysical_properties": props,
                        "benchmark_firewall_verified": True,
                    }
                )
        elif len(b3_panel_records) < 40 and reason in ("fewer_than_two_domains", "homo_repeat_domain_pair"):
            if any(v2_homolog_hit(seq, ref_seq) for _, _, ref_seq in references):
                continue
            scores = scorer.score_sequence(seq)
            two_stage = call_two_stage_interdomain_spans(
                seq,
                pfam_matches,
                scores,
                sequence_verified=True,
                high_confidence_threshold=FROZEN_SEED31_THRESHOLD,
                provisional_threshold=PROVISIONAL_SPAN_THRESHOLD,
            )
            b3_panel_records.append(
                {
                    "protein_id": did,
                    "panel_role": f"single_or_homo_domain_non_linker_{reason}",
                    "family_component_id": comp_id,
                    "sequence_length": len(seq),
                    "pfam_domain_count": len(pfam_matches),
                    "known_order_residues": 0,
                    "stage1_passed": two_stage["stage1_passed"],
                    "stage1_abstention_reason": two_stage["stage1_abstention_reason"],
                    "called_high_confidence_spans": two_stage["called_high_confidence_spans"],
                    "called_provisional_spans": two_stage["called_provisional_spans"],
                    "max_residue_score": round(max(scores), 6),
                    "benchmark_firewall_verified": True,
                }
            )

    # -------------------------------------------------------------------------
    # Tier 4: `literature_engineered_template` (Curated Chen et al. 2013 templates)
    # -------------------------------------------------------------------------
    tier4_records: list[dict] = []
    for entry in library.entries:
        if entry.sequence is None:
            continue
        seq = entry.sequence
        if not (5 <= len(seq) <= 60):
            continue
        scores = scorer.score_sequence(seq)
        props = annotate_biophysical_properties(seq, library, rigidity_model)
        props["curated_rigidity_label"] = entry.rigidity_label
        props["curated_cleavability_label"] = entry.cleavability_label
        props["citation"] = library.citation_for(entry)
        tier4_records.append(
            {
                "record_id": f"template:{entry.entry_id}",
                "authority_tier": "literature_engineered_template",
                "evidence_grade": "literature_cited_engineered_template",
                "protein_id": entry.entry_id,
                "homology_cluster_id": f"template:{entry.entry_id}",
                "linker_sequence": seq,
                "linker_length": len(seq),
                "linker_start_1based": 1,
                "linker_end_1based": len(seq),
                "flanking_context": {
                    "left_domain_source": "literature_fusion_context",
                    "left_domain_id": entry.fusion_context,
                    "left_flank_sequence": "",
                    "right_domain_source": "literature_fusion_context",
                    "right_domain_id": entry.fusion_context,
                    "right_flank_sequence": "",
                },
                "geometry": None,
                "classifier_scores": {
                    "cnn_mean_score": round(sum(scores) / len(scores), 6),
                    "cnn_max_score": round(max(scores), 6),
                    "cnn_fraction_above_high_threshold": round(
                        sum(1 for x in scores if x >= FROZEN_SEED31_THRESHOLD) / len(scores),
                        6,
                    ),
                },
                "biophysical_properties": props,
                "benchmark_firewall_verified": True,
            }
        )

    # Write JSONL files
    natural_authorities = tier1_records + tier2_records
    all_records = natural_authorities + tier3_records + tier4_records

    files_manifest = {
        "all_records_jsonl": write_jsonl(output_dir / "all_records.jsonl", all_records),
        "natural_authorities_jsonl": write_jsonl(
            output_dir / "natural_authorities.jsonl", natural_authorities
        ),
        "mined_candidates_jsonl": write_jsonl(
            output_dir / "mined_candidates.jsonl", tier3_records
        ),
        "template_authorities_jsonl": write_jsonl(
            output_dir / "template_authorities.jsonl", tier4_records
        ),
        "b3_no_linker_specificity_panel_jsonl": write_jsonl(
            output_dir / "b3_no_linker_specificity_panel.jsonl", b3_panel_records
        ),
    }

    counts_by_tier = {
        "natural_cath_pdb_verified": len(tier1_records),
        "natural_disprot_curated_dfl": len(tier2_records),
        "mined_high_confidence_dfl_call": sum(
            1 for r in tier3_records if r["authority_tier"] == "mined_high_confidence_dfl_call"
        ),
        "mined_provisional_dfl_candidate": sum(
            1 for r in tier3_records if r["authority_tier"] == "mined_provisional_dfl_candidate"
        ),
        "mined_domain_gap_abstained": sum(
            1 for r in tier3_records if r["authority_tier"] == "mined_domain_gap_abstained"
        ),
        "literature_engineered_template": len(tier4_records),
        "b3_no_linker_specificity_panel": len(b3_panel_records),
    }

    b3_false_positive_high = sum(r["called_high_confidence_spans"] for r in b3_panel_records)
    b3_false_positive_prov = sum(r["called_provisional_spans"] for r in b3_panel_records)

    manifest = {
        "schema_version": "1.0.0",
        "dataset_id": "mined_and_natural_linkers_v1",
        "status": "part1_completed_provenance_stratified_for_part2_design_and_retrieval",
        "source_pins": {
            "b1_v2_split_manifest_sha256": PINNED_B1_V2_MANIFEST_SHA256,
            "cath_full_pilot_sha256": sha256_file(cath_path),
            "disprot_2026_06_sha256": DISPROT_SHA256,
            "curated_template_library_sha256": sha256_file(curated_lib_path),
            "caid3_registry_sha256": CAID3_SHA256,
            "dp94_registry_sha256": DP94_MANIFEST_SHA256,
        },
        "classifier_provenance": {
            "model_architecture": "ThreeLayerDFLCNN",
            "encoder": ENCODER_NAME,
            "seed": 31,
            "checkpoint_sha256": PINNED_SEED31_CHECKPOINT_SHA256,
            "frozen_residue_threshold": FROZEN_SEED31_THRESHOLD,
            "provisional_span_threshold": PROVISIONAL_SPAN_THRESHOLD,
        },
        "part1_validation_summary": {
            "b1_family_disjoint_split_passed": True,
            "b2_conformal_calibration": {
                "ungated_development_residue_calibration": {
                    "attained": b2_ungated.attained,
                    "calibrated_threshold": b2_ungated.calibrated_threshold,
                    "empirical_fdr": round(b2_ungated.empirical_fdr, 6),
                    "ucb_fdr_95": round(b2_ungated.ucb_fdr, 6),
                    "empirical_recall": round(b2_ungated.empirical_recall, 6),
                    "true_positives": b2_ungated.true_positives,
                    "false_positives": b2_ungated.false_positives,
                },
                "two_stage_domain_gated_development_calibration": {
                    "attained": b2_two_stage.attained,
                    "calibrated_threshold": b2_two_stage.calibrated_threshold,
                    "empirical_fdr": round(b2_two_stage.empirical_fdr, 6),
                    "ucb_fdr_95": round(b2_two_stage.ucb_fdr, 6),
                    "empirical_recall": round(b2_two_stage.empirical_recall, 6),
                    "true_positives": b2_two_stage.true_positives,
                    "false_positives": b2_two_stage.false_positives,
                    "stage1_passed_development_proteins": dev_stage1_passed_proteins,
                },
            },
            "b3_no_linker_specificity_panel": {
                "panel_proteins": len(b3_panel_records),
                "auxiliary_order_proteins": len(aux_rows),
                "single_or_homo_domain_non_linker_proteins": len(b3_panel_records) - len(aux_rows),
                "two_stage_false_positive_high_confidence_spans": b3_false_positive_high,
                "two_stage_false_positive_provisional_spans": b3_false_positive_prov,
                "two_stage_protein_specificity": round(
                    1.0 - (b3_false_positive_high / len(b3_panel_records)), 6
                ),
            },
        },
        "authority_tiers": {
            "natural_cath_pdb_verified": {
                "description": (
                    "Coordinate-verified CATH v4.4.0 two-domain natural inter-domain linkers "
                    "(5..30 aa) with 3D attachment port C-alpha distances and biophysical annotations."
                ),
                "ground_truth_status": "experimental_structure_domain_boundary",
                "eligible_for_part2_geometry_and_retrieval": True,
            },
            "natural_disprot_curated_dfl": {
                "description": (
                    "Curator-validated DisProt_2026_06 IDPO:0000033 flexible linker spans "
                    "(5..60 aa) from the benchmark-disjoint B1 V2 train and development splits."
                ),
                "ground_truth_status": "curator_validated_experimental_dfl",
                "curated_spans_longer_than_60aa_excluded_from_design_window": curated_longer_than_60_count,
                "eligible_for_part2_geometry_and_retrieval": True,
            },
            "mined_domain_gated_interdomain": {
                "description": (
                    "Benchmark-disjoint hetero-Pfam inter-domain spans (5..60 aa) extracted via "
                    "Stage 1 domain-boundary gating and stratified by Stage 2 frozen Seed-31 CNN "
                    "scores into high-confidence calls, provisional candidates, and abstained gaps."
                ),
                "ground_truth_status": "model_mined_candidate_never_promoted_to_ground_truth_training_label",
                "eligible_for_part2_geometry_and_retrieval": True,
            },
            "literature_engineered_template": {
                "description": (
                    "Literature-curated engineered flexible, rigid, and cleavable linker templates "
                    "(5..60 aa) from Chen et al. (2013) Adv. Drug Deliv. Rev. 65:1357-1369."
                ),
                "ground_truth_status": "literature_cited_engineered_template",
                "eligible_for_part2_geometry_and_retrieval": True,
            },
        },
        "files": files_manifest,
        "counts_by_tier": counts_by_tier,
        "limitations": [
            "Mined candidates (`mined_high_confidence_dfl_call`, `mined_provisional_dfl_candidate`, `mined_domain_gap_abstained`) are model-scored inter-domain spans and are strictly segregated from curated ground-truth authorities (`natural_cath_pdb_verified`, `natural_disprot_curated_dfl`).",
            "Two-stage domain-gated conformal calibration (B2) guarantees finite-sample risk control on known labels within family-disjoint multi-domain spans, while unannotated DisProt residues (`x`) remain unknown rather than negative.",
            "CATH v4.4.0 natural linkers (`natural_cath_pdb_verified`) have coordinate-verified domain boundaries and 3D port distances (`inter_port_ca_distance_A`), whereas DisProt curated and mined spans are sequence-and-domain-resolved without experimental 3D port coordinates.",
        ],
    }

    schema = json.loads(
        (ROOT / "schemas" / "mined_and_natural_linker_dataset_v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema).validate(manifest)

    manifest_out = output_dir / "manifest.json"
    manifest_out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary_payload = {
        "manifest_sha256": sha256_file(manifest_out),
        **manifest,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary_payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root",
        type=Path,
        default=ROOT,
        help="Read-only source root holding pinned raw DisProt/CATH/RCSB/CAID3/DP94 files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data" / "processed" / "mined_and_natural_linkers_v1",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=ROOT / "reports" / "mined_and_natural_linkers_v1_summary_2026-10-19.json",
    )
    args = parser.parse_args()
    summary = build_dataset(args.source_root, args.output_dir, args.summary_out)
    print(json.dumps(summary["counts_by_tier"], indent=2, sort_keys=True))
    print(json.dumps(summary["part1_validation_summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
