import unittest

from experiments.topology_poisoning import inject_phrase_into_context


class TopologyPoisoningTests(unittest.TestCase):
    def test_injects_phrase_at_line_boundaries(self):
        context = "Fact one.\nFact two.\nFact three."

        injected = inject_phrase_into_context(
            context=context,
            phrase="Project Note",
            repetitions=2,
        )

        self.assertEqual(injected.count("Project Note"), 2)
        self.assertIn("Project Note: Fact one.", injected)
        self.assertIn("Project Note: Fact two.", injected)

    def test_zero_repetitions_returns_original_context(self):
        context = "Fact one.\nFact two."

        injected = inject_phrase_into_context(
            context=context,
            phrase="Project Note",
            repetitions=0,
        )

        self.assertEqual(injected, context)


if __name__ == "__main__":
    unittest.main()
