"""The command-line tool writes schema-valid records with provenance."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "evaluate_linker_geometry.py"
STRUCTURE = ROOT / "tests" / "fixtures" / "geometry" / "4e43_protease_dimer.pdb"
SCHEMA = ROOT / "schemas" / "linker-junction-geometry.v1.schema.json"


def _run(*arguments: str) -> dict:
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "record.json"
        subprocess.run(
            [sys.executable, str(SCRIPT), *arguments, "--output", str(output)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(output.read_text(encoding="utf-8"))


def _validate(record: dict) -> None:
    try:
        import jsonschema
    except ImportError:
        return
    jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(record)


class JunctionCommandTests(unittest.TestCase):
    def test_a_junction_record_is_schema_valid_and_carries_provenance(self):
        record = _run(
            "junction",
            "--structure",
            str(STRUCTURE),
            "--chain-a",
            "A",
            "--anchor-a",
            "99",
            "--chain-b",
            "B",
            "--anchor-b",
            "1",
            "--residues",
            "5",
        )
        _validate(record)
        self.assertEqual(record["record_type"], "linker_junction_geometry")
        self.assertEqual(record["evidence_quality"], "deterministic_geometry")
        provenance = record["provenance"]
        self.assertEqual(len(provenance["inputs"]), 2)
        self.assertRegex(provenance["constants_sha256"], r"^[0-9a-f]{64}$")
        for entry in provenance["inputs"]:
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(record["geometry"]["requested_length_verdict"]["verdict"], "bridgeable")

    def test_the_record_is_reproducible_for_the_same_inputs(self):
        arguments = (
            "junction",
            "--structure",
            str(STRUCTURE),
            "--chain-a",
            "A",
            "--anchor-a",
            "99",
            "--chain-b",
            "B",
            "--anchor-b",
            "1",
        )
        first, second = _run(*arguments), _run(*arguments)
        self.assertEqual(first["geometry"], second["geometry"])


class TetherCommandTests(unittest.TestCase):
    def test_a_tether_set_record_is_schema_valid(self):
        record = _run(
            "tethers",
            "--structure",
            str(STRUCTURE),
            "--chain-a",
            "A",
            "--chain-b",
            "B",
            "--tether",
            "99:1:flexible:2",
            "--tether",
            "1:99:flexible:2",
        )
        _validate(record)
        self.assertEqual(record["record_type"], "linker_tether_set_geometry")
        self.assertEqual(record["geometry"]["verdict"], "feasible_with_witness")
        self.assertEqual(record["geometry"]["chain_topology"]["peptide_tethers"], 2)

    def test_a_malformed_tether_is_rejected(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "tethers",
                "--structure",
                str(STRUCTURE),
                "--chain-a",
                "A",
                "--chain-b",
                "B",
                "--tether",
                "99:1:flexible",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("residue_a:residue_b:type:residues", result.stderr)


if __name__ == "__main__":
    unittest.main()
