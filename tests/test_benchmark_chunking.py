import unittest

from experiments.benchmark_accurate_retrieval import chunk_text_simple


class BenchmarkChunkingTests(unittest.TestCase):
    def test_splits_single_long_line_by_character_limit(self):
        chunks = chunk_text_simple("a" * 20000, chunk_size=4096)

        self.assertEqual(len(chunks), 2)
        self.assertEqual(len(chunks[0]), 16384)
        self.assertEqual(len(chunks[1]), 3616)


if __name__ == "__main__":
    unittest.main()
