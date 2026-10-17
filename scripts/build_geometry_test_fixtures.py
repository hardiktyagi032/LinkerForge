"""Rebuild the committed structure fixtures used by the linker geometry tests.

The fixtures are trimmed copies of real coordinate files, not invented
coordinates. This script records where each one came from and the SHA-256 of
the source it was cut from, so a reviewer can re-derive them.

Sources (both obtained from PyPI, which is reachable from CI, unlike RCSB):

* ``4E43.pdb`` - unmodified RCSB PDB entry 4E43 (HIV-1 protease dimer with a
  peptide in the active site), as redistributed in the ``MDAnalysisTests``
  package. Chains A and B are kept, protein heavy atoms only.
* ``adk_open.pdb`` - a CHARMM-processed coordinate file of adenylate kinase in
  the open state, labelled ``(4AKE)`` in its own REMARK, redistributed in the
  same package. It is a *derived* file, not a pristine PDB entry, so only
  C-alpha positions are kept and it is used only for distance measurements.

Usage::

    python -m pip download MDAnalysisTests==2.7.0 --no-deps -d <dir>
    python scripts/build_geometry_test_fixtures.py <dir>/MDAnalysisTests-2.7.0.tar.gz

Nothing here is run by the tests; the fixtures are committed.
"""

from __future__ import annotations

import argparse
import hashlib
import tarfile
from pathlib import Path

PACKAGE_VERSION = "2.7.0"
FIXTURE_DIRECTORY = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "geometry"

SOURCES = {
    "4E43.pdb": "4e43_protease_dimer.pdb",
    "adk_open.pdb": "adk_open_4ake_ca.pdb",
}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _trim_protease_dimer(text: str) -> str:
    kept = [
        line
        for line in text.splitlines(keepends=True)
        if line.startswith("ATOM  ") and line[21] in ("A", "B")
    ]
    return "".join(kept) + "END\n"


def _trim_adk_calpha(text: str) -> str:
    kept = [
        line
        for line in text.splitlines(keepends=True)
        if line.startswith("ATOM  ") and line[12:16].strip() == "CA"
    ]
    return "".join(kept) + "END\n"


TRIMMERS = {
    "4E43.pdb": _trim_protease_dimer,
    "adk_open.pdb": _trim_adk_calpha,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="MDAnalysisTests source tarball")
    arguments = parser.parse_args()

    FIXTURE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Provenance of the linker geometry structure fixtures",
        "",
        f"Source package: MDAnalysisTests {PACKAGE_VERSION} (PyPI source distribution).",
        "Rebuild with `scripts/build_geometry_test_fixtures.py`.",
        "",
        "| Fixture | Source file in package | Source SHA-256 | Trim | Fixture SHA-256 |",
        "| --- | --- | --- | --- | --- |",
    ]
    with tarfile.open(arguments.archive) as archive:
        for source_name, fixture_name in SOURCES.items():
            member = f"MDAnalysisTests-{PACKAGE_VERSION}/MDAnalysisTests/data/{source_name}"
            handle = archive.extractfile(member)
            if handle is None:
                raise SystemExit(f"{member} is not in {arguments.archive}")
            raw = handle.read()
            trimmed = TRIMMERS[source_name](raw.decode("utf-8"))
            destination = FIXTURE_DIRECTORY / fixture_name
            destination.write_text(trimmed, encoding="utf-8")
            trim = (
                "chains A and B, protein ATOM records only"
                if source_name == "4E43.pdb"
                else "C-alpha ATOM records only"
            )
            lines.append(
                f"| `{fixture_name}` | `{source_name}` | `{_digest(raw)}` | {trim} | "
                f"`{_digest(trimmed.encode('utf-8'))}` |"
            )
            print(f"wrote {destination} ({len(trimmed.splitlines())} lines)")
    lines += [
        "",
        "`4E43.pdb` is RCSB PDB entry 4E43 as redistributed by the package; its header is",
        "intact in the source file. `adk_open.pdb` is a CHARMM-processed file of adenylate",
        "kinase in the open state, labelled `(4AKE)` in its own REMARK: a derived file, so",
        "only C-alpha positions are kept and only distances are measured from it.",
        "",
    ]
    (FIXTURE_DIRECTORY / "PROVENANCE.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {FIXTURE_DIRECTORY / 'PROVENANCE.md'}")


if __name__ == "__main__":
    main()
