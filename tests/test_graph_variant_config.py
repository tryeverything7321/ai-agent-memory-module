import unittest

from experiments.graph_variant_config import GRAPH_VARIANTS, validate_variant


class GraphVariantConfigTests(unittest.TestCase):
    def test_expected_variants_exist(self):
        self.assertIn("raw_rule_based", GRAPH_VARIANTS)
        self.assertIn("stopword_pronoun_filtered", GRAPH_VARIANTS)
        self.assertIn("typed_relation_only", GRAPH_VARIANTS)

    def test_validate_variant_rejects_unknown(self):
        with self.assertRaises(ValueError):
            validate_variant("unknown")


if __name__ == "__main__":
    unittest.main()
