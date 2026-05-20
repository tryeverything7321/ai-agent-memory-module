import unittest

from experiments.analyze_cross_task_results import (
    compute_arm_deltas,
    query_level_deltas,
    summarize_sample,
)


class CrossTaskAnalysisTests(unittest.TestCase):
    def test_summarize_sample_reports_f1_and_collateral_deltas(self):
        sample = {
            "sample_idx": 0,
            "baseline": {
                "metrics": {"f1": 67.6, "exact_match": 23.0},
                "all_hubs": [
                    {"entity": "Debbie"},
                    {"entity": "Marianne"},
                ],
            },
            "bfs": {
                "metrics": {"f1": 58.3, "exact_match": 20.4},
                "collateral_damage": 29.4,
            },
            "attribute_aware": {
                "metrics": {"f1": 67.1, "exact_match": 23.0},
                "collateral_damage": 1.0,
            },
        }

        summary = summarize_sample(sample)

        self.assertEqual(summary["sample_idx"], 0)
        self.assertEqual(summary["hubs"], ["Debbie", "Marianne"])
        self.assertAlmostEqual(summary["bfs_f1_delta"], -9.3)
        self.assertAlmostEqual(summary["attr_f1_delta"], -0.5)
        self.assertAlmostEqual(summary["collateral_reduction"], 28.4)

    def test_compute_arm_deltas_counts_retrieval_reversal(self):
        samples = [
            {"bfs_f1_delta": -9.3, "attr_f1_delta": -0.5},
            {"bfs_f1_delta": 11.5, "attr_f1_delta": 0.6},
        ]

        deltas = compute_arm_deltas(samples)

        self.assertEqual(deltas["n_samples"], 2)
        self.assertEqual(deltas["bfs_retrieval_drop_count"], 1)
        self.assertEqual(deltas["bfs_retrieval_gain_count"], 1)
        self.assertAlmostEqual(deltas["mean_bfs_f1_delta"], 1.1)

    def test_query_level_deltas_compare_baseline_and_bfs(self):
        sample = {
            "baseline": {
                "per_query": [
                    {
                        "query_id": 7,
                        "question": "Which event happens next?",
                        "ground_truth": ["A"],
                        "prediction": "B",
                        "f1": 0.0,
                    }
                ]
            },
            "bfs": {
                "per_query": [
                    {
                        "query_id": 7,
                        "prediction": "A",
                        "f1": 1.0,
                    }
                ]
            },
        }

        rows = query_level_deltas(sample)

        self.assertEqual(rows[0]["query_id"], 7)
        self.assertEqual(rows[0]["ground_truth"], ["A"])
        self.assertEqual(rows[0]["baseline_prediction"], "B")
        self.assertEqual(rows[0]["bfs_prediction"], "A")
        self.assertEqual(rows[0]["delta"], 1.0)


if __name__ == "__main__":
    unittest.main()
