import unittest

from experiments.sample_attr_false_negative_audit import make_audit_item


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


if __name__ == "__main__":
    unittest.main()
