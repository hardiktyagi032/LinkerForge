"""Source-checkout entry point; the package also installs linkerforge-design."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from linkerforge.pipeline.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
