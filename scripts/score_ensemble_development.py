"""Evaluate an ensemble of saved per-residue development scores (CPU, numpy only).

Usage: python scripts/score_ensemble_development.py --output OUT.json member1.npz member2.npz member3.npz
Members are produced from APS-selected checkpoints, one GPU job at a time, with
``linkerforge.ensemble.save_member``. No CAID3 data is read; non-development
members are refused.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from linkerforge.ensemble import evaluate_ensemble  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("members", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--min-members", type=int, default=3)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = evaluate_ensemble(args.members, min_members=args.min_members)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "completed", "output": str(args.output)}))


if __name__ == "__main__":
    main()
