"""Tests for explicit UniProt linker-region parsing."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/add_uniprot_annotated_linkers.py"
spec = spec_from_file_location("uniprot_regions", SCRIPT)
module = module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class RegionTests(unittest.TestCase):
    def test_linker_region_and_evidence(self):
        text = ('REGION 2..5; /note="Linker"; '
                '/evidence="ECO:0000269|PubMed:123"; '
                'REGION 10..15; /note="Other region"')
        self.assertEqual(list(module.linker_regions(text, "A" * 20)),
                         [(2, 5, "AAAA", "Linker", "ECO:0000269|PubMed:123")])

    def test_out_of_bounds_region_is_skipped(self):
        self.assertEqual(list(module.linker_regions('REGION 10..15; /note="Linker"',
                                                    "A" * 12)), [])


if __name__ == "__main__":
    unittest.main()
