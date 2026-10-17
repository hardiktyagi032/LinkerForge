"""Run the local source tree without using another worktree's installed package."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from linkerforge.generation.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
