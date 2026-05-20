import unittest

from experiments.summarize_practical_harm import summarize_arm, summarize_result


class PracticalHarmSummaryTests(unittest.TestCase):
    def test_summarize_arm_uses_per_hub_blast_radius_and_collateral(self):
        sample = {
            "baseline": {"metrics": {"f1": 50.0}},
            "bfs": {
                "metrics": {"f1": 40.0},
                "memory_stats_pre": {"retrievable": 100, "invalid": 0},
                "memory_stats_post": {
                    "retrievable": 80,
                    "invalid": 1,
                    "decayed_below_threshold": 20,
                },
                "multi_hub": {
                    "per_hub": [
                        {"affected": 10, "collateral": 3},
                        {"affected": 30, "collateral": 5},
                    ]
                },
            },
        }

        summary = summarize_arm(sample, "bfs")

        self.assertEqual(summary["policy"], "bfs")
        self.assertEqual(summary["mean_blast_radius"], 20.0)
        self.assertEqual(summary["mean_collateral"], 4.0)
        self.assertEqual(summary["retrievable_loss"], 20)
        self.assertEqual(summary["invalid_added"], 1)
        self.assertEqual(summary["f1_delta"], -10.0)

    def test_summarize_result_aggregates_samples(self):
        result = {
            "config": {"sub_dataset": "eventqa_test"},
            "per_sample": [
                {
                    "baseline": {"metrics": {"f1": 50.0}},
                    "bfs": {
                        "metrics": {"f1": 40.0},
                        "memory_stats_pre": {"retrievable": 100, "invalid": 0},
                        "memory_stats_post": {
                            "retrievable": 80,
                            "invalid": 1,
                            "decayed_below_threshold": 20,
                        },
                        "multi_hub": {"per_hub": [{"affected": 10, "collateral": 3}]},
                    },
                    "attribute_aware": {
                        "metrics": {"f1": 49.0},
                        "memory_stats_pre": {"retrievable": 100, "invalid": 0},
                        "memory_stats_post": {
                            "retrievable": 99,
                            "invalid": 1,
                            "decayed_below_threshold": 0,
                        },
                        "multi_hub": {"per_hub": [{"affected": 2, "collateral": 1}]},
                    },
                }
            ],
        }

        rows = summarize_result(result)

        self.assertEqual(rows[0]["dataset"], "eventqa_test")
        self.assertEqual([row["policy"] for row in rows], ["bfs", "attribute_aware"])
        self.assertEqual(rows[0]["mean_blast_radius"], 10.0)
        self.assertEqual(rows[1]["mean_blast_radius"], 2.0)


if __name__ == "__main__":
    unittest.main()
