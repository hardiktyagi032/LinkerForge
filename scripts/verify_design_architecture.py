"""Scoped geometry/model software checks; never invoke detector benchmarks."""
import argparse
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("geometry", "models", "all"), default="all")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output and args.output.exists():
        raise ValueError("Refusing to overwrite test evidence")
    patterns = []
    if args.scope in ("geometry", "all"):
        patterns += ["test_linker_geometry_*.py"]
    if args.scope in ("models", "all"):
        patterns += ["test_fusion_generator.py", "test_attachment_sites.py", "test_design_pipeline.py"]
    loader, suite = unittest.TestLoader(), unittest.TestSuite()
    for pattern in patterns:
        suite.addTests(loader.discover(str(ROOT / "tests"), pattern=pattern))
    started = time.monotonic()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    versions = {"python": platform.python_version(), "platform": platform.platform()}
    for package in ("torch", "transformers", "safetensors", "numpy"):
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = None
    sources = list((ROOT / "src" / "linkerforge").rglob("*.py")) + [p for pattern in patterns for p in (ROOT / "tests").glob(pattern)]
    digest = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(sources))}
    report = {"purpose":"Software regressions only; invented model fixtures and existing geometric fixtures, no scientific experiment",
              "scope":args.scope,"patterns":patterns,"tests_run":result.testsRun,"failures":len(result.failures),
              "errors":len(result.errors),"skipped":len(result.skipped),"passed":result.wasSuccessful(),
              "measured_wall_seconds":time.monotonic()-started,"environment":versions,"source_sha256s":digest,
              "scientific_training_or_benchmark_reveal":False}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k != "source_sha256s"}, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
