import unittest

from experiments.preprint_hubs import filter_named_entity_hubs


class PreprintHubTests(unittest.TestCase):
    def test_filters_function_words_pronouns_and_keeps_named_entities(self):
        raw_hubs = [
            {"entity": "And", "degree": 91, "memory_count": 10},
            {"entity": "She", "degree": 88, "memory_count": 9},
            {"entity": "Debbie", "degree": 64, "memory_count": 7},
            {"entity": "Marianne", "degree": 58, "memory_count": 6},
            {"entity": "But", "degree": 55, "memory_count": 6},
        ]

        filtered = filter_named_entity_hubs(raw_hubs, top_k=2)

        self.assertEqual([hub["entity"] for hub in filtered], ["Debbie", "Marianne"])

    def test_rejects_lowercase_common_tokens(self):
        raw_hubs = [
            {"entity": "meeting", "degree": 20, "memory_count": 4},
            {"entity": "United States", "degree": 19, "memory_count": 4},
            {"entity": "project alpha", "degree": 18, "memory_count": 4},
            {"entity": "Project Alpha", "degree": 17, "memory_count": 4},
        ]

        filtered = filter_named_entity_hubs(raw_hubs, top_k=10)

        self.assertEqual(
            [hub["entity"] for hub in filtered],
            ["United States", "Project Alpha"],
        )


if __name__ == "__main__":
    unittest.main()
