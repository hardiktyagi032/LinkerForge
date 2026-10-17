"""Command-line linker geometry: required length, accessibility, occlusion, tether sets.

Deterministic geometry only. No GPU, no training, no network, no third-party
packages. Every record it writes carries its inputs' digests, the commit it ran
at and a digest of the literature constants, and validates against
``schemas/linker-junction-geometry.v1.schema.json``.

One junction between two chains of one structure::

    python scripts/evaluate_linker_geometry.py junction \\
        --structure tests/fixtures/geometry/4e43_protease_dimer.pdb \\
        --chain-a A --anchor-a 99 --chain-b B --anchor-b 1 \\
        --linker-type flexible --residues 5

Several simultaneous tethers, solving for the relative placement of domain B::

    python scripts/evaluate_linker_geometry.py tethers \\
        --structure tests/fixtures/geometry/4e43_protease_dimer.pdb \\
        --chain-a A --chain-b B \\
        --tether 99:1:flexible:2 --tether 1:99:flexible:2

``--structure-b`` reads domain B from a second file. For a tether set the
coordinates of domain B are treated as its internal geometry only: the search
is free to place it anywhere, and reports the placement it found.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from linkerforge.geometry import constants  # noqa: E402
from linkerforge.geometry.junction import evaluate_junction, evaluate_tether_set  # noqa: E402
from linkerforge.geometry.structure import read_chain  # noqa: E402

SCHEMA_VERSION = "1.0.0"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _commit_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _parse_tether(value: str) -> tuple[int, int, str, int]:
    parts = value.split(":")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            f"Expected residue_a:residue_b:type:residues, got {value!r}"
        )
    residue_a, residue_b, tether_type, residues = parts
    if tether_type not in constants.TETHER_TYPES:
        raise argparse.ArgumentTypeError(
            f"Unknown tether type {tether_type!r}; have {list(constants.TETHER_TYPES)}"
        )
    try:
        return int(residue_a), int(residue_b), tether_type, int(residues)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Non-integer residue number in {value!r}") from exc


def _provenance(
    inputs: list[dict[str, object]], command: list[str]
) -> dict[str, object]:
    return {
        "inputs": inputs,
        "commit_sha": _commit_sha(),
        "python_version": sys.version.split()[0],
        "constants_sha256": _digest(Path(constants.__file__)),
        "generated_by": "scripts/evaluate_linker_geometry.py",
        "command": command,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subcommands = parser.add_subparsers(dest="mode", required=True)

    def add_common(target: argparse.ArgumentParser) -> None:
        target.add_argument("--structure", type=Path, required=True, help="PDB file for domain A")
        target.add_argument("--structure-b", type=Path, help="PDB file for domain B (default: same file)")
        target.add_argument("--chain-a", required=True)
        target.add_argument("--chain-b", required=True)
        target.add_argument("--output", type=Path, help="Write the record here instead of stdout")
        target.add_argument("--sphere-points", type=int, default=256)

    junction = subcommands.add_parser("junction", help="One linker between two attachment points")
    add_common(junction)
    junction.add_argument("--anchor-a", type=int, required=True)
    junction.add_argument("--anchor-b", type=int, required=True)
    junction.add_argument("--linker-type", choices=list(constants.LINKER_TYPES), default="flexible")
    junction.add_argument("--residues", type=int, help="Judge this linker length against the window")
    junction.add_argument(
        "--composition",
        choices=sorted(constants.GS_CHAIN_STATISTICS),
        default=constants.DEFAULT_GS_COMPOSITION,
    )

    tethers = subcommands.add_parser("tethers", help="Several simultaneous tethers")
    add_common(tethers)
    tethers.add_argument(
        "--tether",
        action="append",
        required=True,
        type=_parse_tether,
        metavar="A:B:TYPE:RESIDUES",
        help="Repeatable. TYPE is flexible, helical or disulfide; a disulfide takes 0 residues.",
    )
    tethers.add_argument("--restarts", type=int, default=32)
    tethers.add_argument("--iterations", type=int, default=300)
    tethers.add_argument("--tolerance", type=float, default=0.05)
    tethers.add_argument("--seed", type=int, default=0)

    arguments = parser.parse_args()
    path_a = arguments.structure
    path_b = arguments.structure_b or arguments.structure
    domain_a = read_chain(path_a, arguments.chain_a)
    domain_b = read_chain(path_b, arguments.chain_b)
    inputs = [
        {
            "role": "domain_a",
            "path": str(path_a),
            "sha256": _digest(path_a),
            "chain": arguments.chain_a,
            "residue_count": len(domain_a.residues),
        },
        {
            "role": "domain_b",
            "path": str(path_b),
            "sha256": _digest(path_b),
            "chain": arguments.chain_b,
            "residue_count": len(domain_b.residues),
        },
    ]

    if arguments.mode == "junction":
        geometry = evaluate_junction(
            domain_a,
            arguments.anchor_a,
            domain_b,
            arguments.anchor_b,
            arguments.linker_type,
            requested_residues=arguments.residues,
            composition=arguments.composition,
            points=arguments.sphere_points,
        )
    else:
        geometry = evaluate_tether_set(
            domain_a,
            domain_b,
            tuple(arguments.tether),
            restarts=arguments.restarts,
            iterations=arguments.iterations,
            tolerance=arguments.tolerance,
            seed=arguments.seed,
        )

    record = {
        "schema_version": SCHEMA_VERSION,
        "record_type": geometry["record_type"],
        "evidence_quality": "deterministic_geometry",
        "provenance": _provenance(inputs, sys.argv),
        "geometry": geometry,
    }
    text = json.dumps(record, indent=2, sort_keys=False, default=list)
    if arguments.output:
        arguments.output.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {arguments.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
