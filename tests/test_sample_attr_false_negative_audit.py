import unittest

from experiments.sample_attr_false_negative_audit import (
    _round_robin_by_group,
    make_audit_item,
    sample_audit_items,
)


class AttrFalseNegativeAuditTests(unittest.TestCase):
    def test_make_audit_item_has_required_fields(self):
        item = make_audit_item(
            sample_idx=0,
            hub="Debbie",
            source_memory="Debbie moved to Paris.",
            target_memory="Debbie lives in Paris.",
            bfs_reached=True,
            attr_reached=False,
        )

        self.assertEqual(item["sample_idx"], 0)
        self.assertEqual(item["hub"], "Debbie")
        self.assertEqual(item["bucket"], "bfs_reached_attr_blocked")
        self.assertEqual(item["label"], "")

    def test_sample_audit_items_uses_bfs_minus_attr_trace(self):
        result = {
            "per_sample": [
                {
                    "sample_idx": 2,
                    "bfs": {
                        "multi_hub": {
                            "per_hub": [
                                {
                                    "hub_entity": "Debbie",
                                    "audit_trace": {
                                        "trigger_content": "Debbie moved.",
                                        "affected_sample": [
                                            {"memory_id": "a", "content": "Debbie lives in Paris."},
                                            {"memory_id": "b", "content": "Unrelated Debbie fact."},
                                        ],
                                    },
                                }
                            ]
                        }
                    },
                    "attribute_aware": {
                        "multi_hub": {
                            "per_hub": [
                                {
                                    "hub_entity": "Debbie",
                                    "audit_trace": {
                                        "trigger_content": "Debbie moved.",
                                        "affected_sample": [
                                            {"memory_id": "a", "content": "Debbie lives in Paris."},
                                        ],
                                    },
                                }
                            ]
                        }
                    },
                }
            ]
        }

        items = sample_audit_items(result, max_items_per_bucket=10)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["bucket"], "bfs_reached_attr_blocked")
        self.assertEqual(items[0]["target_memory"], "Unrelated Debbie fact.")
        self.assertEqual(items[1]["bucket"], "attr_reached")

    def test_sample_audit_items_samples_attr_trace_directly(self):
        result = {
            "per_sample": [
                {
                    "sample_idx": 1,
                    "bfs": {
                        "multi_hub": {
                            "per_hub": [
                                {
                                    "hub_entity": "Debbie",
                                    "audit_trace": {
                                        "trigger_content": "Debbie moved.",
                                        "affected_sample": [
                                            {"memory_id": "b", "content": "Blocked target."},
                                        ],
                                    },
                                }
                            ]
                        }
                    },
                    "attribute_aware": {
                        "multi_hub": {
                            "per_hub": [
                                {
                                    "hub_entity": "Debbie",
                                    "audit_trace": {
                                        "trigger_content": "Debbie moved.",
                                        "affected_sample": [
                                            {"memory_id": "c", "content": "Accepted target."},
                                        ],
                                    },
                                }
                            ]
                        }
                    },
                }
            ]
        }

        items = sample_audit_items(result, max_items_per_bucket=10)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["bucket"], "bfs_reached_attr_blocked")
        self.assertEqual(items[1]["bucket"], "attr_reached")
        self.assertFalse(items[1]["bfs_reached"])
        self.assertEqual(items[1]["target_memory"], "Accepted target.")

    def test_round_robin_by_group_avoids_single_hub_prefix(self):
        items = [
            make_audit_item(0, "A", "s", f"a{i}", True, False)
            for i in range(3)
        ] + [
            make_audit_item(0, "B", "s", f"b{i}", True, False)
            for i in range(2)
        ]

        selected = _round_robin_by_group(items, max_items=4)

        self.assertEqual(
            [item["target_memory"] for item in selected],
            ["a0", "b0", "a1", "b1"],
        )


if __name__ == "__main__":
    unittest.main()
