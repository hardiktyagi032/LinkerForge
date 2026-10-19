"""Run the separately logged span-to-residue coupled architecture variant."""

import json
from pathlib import Path

import run_caid3_protected_bounded_span_trial as base
from linkerforge.models.coupled_bounded_span_segmenter import CoupledBoundedSpanSegmenter


def configure_head(arch, dimension, device):
    if arch != "bounded_span":
        raise ValueError(arch)
    return CoupledBoundedSpanSegmenter(dimension).to(device)


if __name__ == "__main__":
    base.CONFIG = base.ROOT / "configs/dfl_coupled_bounded_span_protected_round_2026-10-16.json"
    base.MODEL_SOURCE = base.ROOT / "src/linkerforge/models/coupled_bounded_span_segmenter.py"
    base.configure_head = configure_head
    try:
        base.main()
    finally:
        # The underlying runner persists its own config/data/source hashes.
        # Add this dispatch layer and variant identity for auditability.
        import argparse
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--output-dir", type=Path)
        args, _ = parser.parse_known_args()
        if args.output_dir:
            path = args.output_dir / "manifest.json"
            if path.exists():
                manifest = json.loads(path.read_text(encoding="utf-8"))
                manifest["variant"] = "coupled_span_to_residue_max_support"
                manifest["dispatch_source_sha256"] = base.trial.sha(Path(__file__))
                path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
