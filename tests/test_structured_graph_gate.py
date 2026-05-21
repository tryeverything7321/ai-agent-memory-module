import unittest

from experiments.structured_graph_gate import (
    analyze_context_fast,
    build_structured_context,
    clean_turn_text,
    extract_entities_rule_based_fast,
    flatten_haystack_messages,
)


class StructuredGraphGateTests(unittest.TestCase):
    def sample(self):
        return {
            "context": "raw",
            "metadata": {
                "haystack_sessions": [
                    [
                        "Chat Time: 2024/01/01",
                        [
                            {
                                "role": "user",
                                "content": "Alice visited Miami.",
                                "has_answer": True,
                            },
                            {
                                "role": "assistant",
                                "content": "Here are some tips.",
                                "has_answer": False,
                            },
                        ],
                    ],
                    [
                        "Chat Time: 2024/01/02",
                        [
                            {
                                "role": "user",
                                "content": "Bob moved to Paris.",
                                "has_answer": False,
                            },
                        ],
                    ],
                ]
            },
        }

    def test_flatten_haystack_messages(self):
        messages = flatten_haystack_messages(self.sample()["metadata"])

        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["session_idx"], 0)

    def test_user_turn_context_excludes_assistant_templates(self):
        context = build_structured_context(self.sample(), "user_turns")

        self.assertIn("Alice visited Miami", context)
        self.assertIn("Bob moved to Paris", context)
        self.assertNotIn("Here are some tips", context)

    def test_answer_turn_context_uses_answer_bearing_messages(self):
        context = build_structured_context(self.sample(), "answer_turns")

        self.assertIn("Alice visited Miami", context)
        self.assertNotIn("Bob moved to Paris", context)

    def test_clean_turn_text_collapses_whitespace_and_headings(self):
        cleaned = clean_turn_text("**Resume Feedback:**\n\n  Alice   visited Miami. ")

        self.assertEqual(cleaned, "Alice visited Miami.")

    def test_fast_entity_extraction_matches_proper_noun_shape(self):
        entities = extract_entities_rule_based_fast(
            "Alice visited Miami after leaving San Francisco."
        )

        self.assertEqual(entities, ["Alice", "Miami", "San Francisco"])

    def test_fast_analyzer_returns_filtered_content_hubs(self):
        context = "\n".join([
            "1. Alice visited Miami with Delta SkyMiles.",
            "2. Alice flew from San Francisco to Boston.",
            "3. Here are some tips for Alice.",
        ])

        result = analyze_context_fast(context, top_k=3)

        self.assertGreaterEqual(result["n_filtered_hubs"], 1)
        self.assertEqual(result["filtered_hubs"][0]["entity"], "Alice")


if __name__ == "__main__":
    unittest.main()
