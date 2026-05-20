import unittest

from experiments.preprint_hubs import filter_named_entity_hubs, select_actionable_hubs


class PreprintHubTests(unittest.TestCase):
    def test_filters_function_words_pronouns_and_keeps_named_entities(self):
        raw_hubs = [
            {"entity": "And", "degree": 91, "memory_count": 10},
            {"entity": "She", "degree": 88, "memory_count": 9},
            {"entity": "Debbie", "degree": 64, "memory_count": 7},
            {"entity": "Marianne", "degree": 58, "memory_count": 6},
            {"entity": "But", "degree": 55, "memory_count": 6},
            {"entity": "There", "degree": 54, "memory_count": 6},
            {"entity": "What", "degree": 53, "memory_count": 6},
            {"entity": "All", "degree": 52, "memory_count": 6},
            {"entity": "Mrs", "degree": 51, "memory_count": 6},
            {"entity": "Monsieur", "degree": 50, "memory_count": 6},
            {"entity": "One", "degree": 49, "memory_count": 6},
            {"entity": "When", "degree": 48, "memory_count": 6},
            {"entity": "These", "degree": 47, "memory_count": 6},
        ]

        filtered = filter_named_entity_hubs(raw_hubs, top_k=2)

        self.assertEqual([hub["entity"] for hub in filtered], ["Debbie", "Marianne"])

    def test_rejects_lowercase_common_tokens(self):
        raw_hubs = [
            {"entity": "meeting", "degree": 20, "memory_count": 4},
            {"entity": "United States", "degree": 19, "memory_count": 4},
            {"entity": "project alpha", "degree": 18, "memory_count": 4},
            {"entity": "Project Alpha", "degree": 17, "memory_count": 4},
            {"entity": "Miss Brevin", "degree": 16, "memory_count": 4},
        ]

        filtered = filter_named_entity_hubs(raw_hubs, top_k=10)

        self.assertEqual(
            [hub["entity"] for hub in filtered],
            ["United States", "Project Alpha", "Miss Brevin"],
        )

    def test_selects_named_entities_with_triggerable_facts(self):
        raw_hubs = [
            {"entity": "Debbie", "degree": 715},
            {"entity": "Marianne", "degree": 589},
            {"entity": "Kerry", "degree": 394},
            {"entity": "Nadia", "degree": 380},
        ]

        selected = select_actionable_hubs(
            raw_hubs,
            top_k=3,
            has_trigger_fact=lambda entity: entity != "Kerry",
        )

        self.assertEqual(
            [hub["entity"] for hub in selected],
            ["Debbie", "Marianne", "Nadia"],
        )


if __name__ == "__main__":
    unittest.main()
