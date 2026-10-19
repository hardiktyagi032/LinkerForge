"""Score a mapped, single-chain predicted fusion PDB without applying pass rules.

This is a diagnostic CLI for pre-existing PDB predictions, not a folding tool.
Output includes source hashes and an exact scoring-config hash. Run from the
repository root with PYTHONPATH=src until a backend package is committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from linkerforge.structure import load_ca_pdb, score_fusion


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def span(value: str) -> tuple[int, int]:
    try:
        start, end = (int(item) for item in value.split(":"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use START:END, inclusive") from exc
    if start < 1 or end < start:
        raise argparse.ArgumentTypeError("Span must be positive and increasing")
    return start, end


def reference(path: Path | None, chain: str, extent: tuple[int, int]):
    if path is None:
        return None
    coordinates = load_ca_pdb(path, chain)
    missing = [i for i in range(extent[0], extent[1] + 1) if i not in coordinates]
    if missing:
        raise ValueError(f"Reference {path} lacks residue {missing[0]}; supply a mapped reference")
    return [coordinates[i] for i in range(extent[0], extent[1] + 1)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prediction", required=True, type=Path)
    parser.add_argument("--chain", required=True)
    parser.add_argument("--domain-a", required=True, type=span)
    parser.add_argument("--linker", required=True, type=span)
    parser.add_argument("--domain-b", required=True, type=span)
    parser.add_argument("--reference-a", type=Path)
    parser.add_argument("--reference-b", type=Path)
    parser.add_argument("--reference-a-chain")
    parser.add_argument("--reference-b-chain")
    parser.add_argument("--predictor", required=True,
                        help="Declared predictor name; recorded, not inferred")
    parser.add_argument("--predictor-version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if len(args.chain) != 1:
        parser.error("PDB chain must be one character")
    config = {"chain": args.chain, "domain_a": args.domain_a,
              "linker": args.linker, "domain_b": args.domain_b,
              "reference_a_chain": args.reference_a_chain,
              "reference_b_chain": args.reference_b_chain}
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    metrics = score_fusion(
        load_ca_pdb(args.prediction, args.chain), args.domain_a, args.linker,
        args.domain_b,
        reference(args.reference_a, args.reference_a_chain or args.chain, args.domain_a),
        reference(args.reference_b, args.reference_b_chain or args.chain, args.domain_b),
    )
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                            text=True, check=True).stdout.strip()
    result = {"status": "diagnostic_only", "metrics": metrics,
              "provenance": {"pipeline_commit": commit, "config_hash": config_hash,
                             "prediction_sha256": sha256(args.prediction),
                             "reference_a_sha256": sha256(args.reference_a) if args.reference_a else None,
                             "reference_b_sha256": sha256(args.reference_b) if args.reference_b else None,
                             "predictor": args.predictor,
                             "predictor_version": args.predictor_version,
                             "scorer": "linkerforge-ca-geometry-0.1.0"}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
