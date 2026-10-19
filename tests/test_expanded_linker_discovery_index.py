"""Boundary tests for the lower-confidence UniProt domain-gap extractor."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_expanded_linker_discovery_index.py"
spec = spec_from_file_location("expanded_linker_index", SCRIPT)
module = module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class DomainGapTests(unittest.TestCase):
    def test_adjacent_domains_have_one_candidate_gap(self):
        seq = "A" * 50
        features = 'DOMAIN 1..10; /note="A"; DOMAIN 20..40; /note="B"'
        hits = list(module.candidates(seq, features, [], 5, 150))
        self.assertEqual([(s, e) for s, e, *_ in hits], [(11, 19)])

    def test_nested_domain_prevents_false_gap(self):
        seq = "A" * 100
        features = ('DOMAIN 1..100; /note="outer"; DOMAIN 10..20; '
                    '/note="inner 1"; DOMAIN 30..40; /note="inner 2"')
        self.assertEqual(list(module.candidates(seq, features, [], 5, 150)), [])

    def test_repeat_overlap_prevents_candidate(self):
        seq = "A" * 50
        features = 'DOMAIN 1..10; DOMAIN 20..40'
        self.assertEqual(list(module.candidates(seq, features, [(15, 16)], 5, 150)), [])


if __name__ == "__main__":
    unittest.main()
