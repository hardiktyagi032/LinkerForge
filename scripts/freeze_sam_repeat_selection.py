"""Freeze one checkpoint using preregistered protected-development metrics only."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_dfl_disorder_transfer import sha

SCORES = ROOT / "reports/dfl_sam_repeat_development_scores_2026-10-17.json"
RULE = ROOT / "literature/DFL_SAM_REPEAT_SELECTION_RULE_2026-10-17.md"
OUTPUT = ROOT / "reports/dfl_sam_repeat_frozen_selection_2026-10-17.json"
DATA = ROOT / "data/processed/caid3_protected_dfl_v1/manifest.json"
EXPECTED_RULE_SHA = None  # Supplied below by the freeze invocation; never infer from results.


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    if not SCORES.exists():
        raise FileNotFoundError(SCORES)
    scores = json.loads(SCORES.read_text(encoding="utf-8"))
    if scores["claim_status"] != "protected_development_only" or scores["data_manifest_sha256"] != sha(DATA):
        raise ValueError("Development score provenance mismatch")
    rows = scores["results"]
    groups = {}
    for row in rows:
        groups.setdefault(row["variant"], {})[row["seed"]] = row
    if set(groups) != {"baseline", "multiscale_features", "boundary_plus_query"} or any(
            set(seeds) != {7, 17, 31} for seeds in groups.values()):
        raise ValueError("Incomplete or duplicate three-seed comparison")
    summary = {}
    for variant, seeds in groups.items():
        manifests = [json.loads((ROOT / seeds[seed]["checkpoint"]).parent.joinpath("manifest.json").read_text(encoding="utf-8"))
                     for seed in (7, 17, 31)]
        specificity = [m["best_development"]["no_positive_protein_proxy_specificity"] for m in manifests]
        if any(value is None for value in specificity):
            raise ValueError("Missing no-positive proxy specificity")
        summary[variant] = {"mean_aps": statistics.mean(seeds[s]["metrics"]["aps"] for s in (7, 17, 31)),
                            "mean_fmax": statistics.mean(seeds[s]["metrics"]["fmax"] for s in (7, 17, 31)),
                            "specificity_by_seed": dict(zip((7, 17, 31), specificity)),
                            "mean_proxy_specificity": statistics.mean(specificity)}
    baseline = summary["baseline"]
    eligible = [name for name in ("multiscale_features", "boundary_plus_query")
                if summary[name]["mean_aps"] > baseline["mean_aps"] and
                summary[name]["mean_proxy_specificity"] >= baseline["mean_proxy_specificity"] - 0.02]
    chosen = max(eligible, key=lambda name: summary[name]["mean_aps"]) if eligible else "baseline"
    mean = summary[chosen]["mean_aps"]
    seed = min((7, 17, 31), key=lambda s: (abs(groups[chosen][s]["metrics"]["aps"] - mean), s))
    checkpoint = groups[chosen][seed]["checkpoint"]
    candidate = ROOT / checkpoint
    manifest = json.loads((candidate.parent / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("blacklist_status") != "passed_before_training" or manifest["status"] != "completed":
        raise ValueError("Selected checkpoint did not pass protected-data gate")
    frozen = {"schema_version": "1.0.0", "created_utc": datetime.now(timezone.utc).isoformat(),
              "frozen_before_caid3": True, "selection_basis": "filtered_development_only",
              "claim_status": "public_retrospective_not_fresh_blind", "arch": "samlike",
              "variant": None if chosen == "baseline" else chosen, "selected_seed": seed,
              "checkpoint": checkpoint, "checkpoint_sha256": sha(candidate),
              "checkpoint_manifest_sha256": sha(candidate.parent / "manifest.json"),
              "score_file_sha256": sha(SCORES), "selection_rule_sha256": sha(RULE),
              "protected_data_manifest_sha256": sha(DATA), "eligible_variants": eligible,
              "summary": summary, "selection_reason": "highest eligible mean APS, closest-to-mean seed"}
    OUTPUT.write_text(json.dumps(frozen, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"chosen": chosen, "seed": seed, "checkpoint": checkpoint,
                      "eligible": eligible, "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
