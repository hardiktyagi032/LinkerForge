"""Fail-closed seed-7 context-plus-span DFL development trial."""

import json
from pathlib import Path

import run_caid3_protected_bounded_span_trial as base
from linkerforge.models.global_context_span_segmenter import GlobalContextSpanSegmenter


def configure_head(arch, dimension, device):
    if arch != "bounded_span":
        raise ValueError(arch)
    return GlobalContextSpanSegmenter(dimension, max_span=192).to(device)


if __name__ == "__main__":
    base.CONFIG = base.ROOT / "configs/dfl_global_context_span_protected_round_2026-10-17.json"
    base.MODEL_SOURCE = base.ROOT / "src/linkerforge/models/global_context_span_segmenter.py"
    base.configure_head = configure_head
    try:
        base.main()
    finally:
        import argparse
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--output-dir", type=Path)
        args, _ = parser.parse_known_args()
        if args.output_dir:
            path = args.output_dir / "manifest.json"
            if path.exists():
                manifest = json.loads(path.read_text(encoding="utf-8"))
                manifest["variant"] = "global_context_plus_coupled_span_192"
                manifest["max_span"] = 192
                manifest["dispatch_source_sha256"] = base.trial.sha(Path(__file__))
                manifest["parent_model_source_sha256"] = base.trial.sha(
                    base.ROOT / "src/linkerforge/models/bounded_span_linker_segmenter.py")
                manifest["coupled_model_source_sha256"] = base.trial.sha(
                    base.ROOT / "src/linkerforge/models/coupled_bounded_span_segmenter.py")
                path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
