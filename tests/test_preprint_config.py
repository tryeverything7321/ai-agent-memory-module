import json
import tempfile
import unittest
from pathlib import Path

from experiments.preprint_config import load_experiment_config, write_manifest


class PreprintConfigTests(unittest.TestCase):
    def test_loads_valid_config_and_normalizes_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({
                "experiment_name": "cross_task_named_hubs_smoke",
                "dataset": {
                    "name": "ai-hyz/MemoryAgentBench",
                    "split": "Accurate_Retrieval",
                    "sub_dataset": "eventqa_65536",
                    "max_samples": 1,
                    "max_queries": 20
                },
                "hub_selection": {
                    "top_k": 2,
                    "named_entity_only": True,
                    "exclude_stopwords_pronouns": True
                },
                "policies": ["no_propagation", "bfs", "attr_aware"],
                "metrics": ["em", "f1", "blast_radius", "severe_decay", "kill_rate"],
                "models": {
                    "llm_model": "google/gemma-4-31B-it",
                    "embedding_model": "BAAI/bge-m3"
                },
                "output_dir": "experiments/results/preprint"
            }))

            config = load_experiment_config(path)

            self.assertEqual(config.experiment_name, "cross_task_named_hubs_smoke")
            self.assertEqual(config.dataset.split, "Accurate_Retrieval")
            self.assertEqual(config.hub_selection.top_k, 2)
            self.assertIn("bfs", config.policies)
            self.assertEqual(config.output_dir, Path("experiments/results/preprint"))

    def test_rejects_raw_hub_headline_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({
                "experiment_name": "unsafe_raw_hubs",
                "dataset": {
                    "name": "ai-hyz/MemoryAgentBench",
                    "split": "Accurate_Retrieval",
                    "sub_dataset": "eventqa_65536",
                    "max_samples": 1,
                    "max_queries": 20
                },
                "hub_selection": {
                    "top_k": 5,
                    "named_entity_only": False,
                    "exclude_stopwords_pronouns": False
                },
                "policies": ["bfs"],
                "metrics": ["f1"],
                "models": {
                    "llm_model": "google/gemma-4-31B-it",
                    "embedding_model": "BAAI/bge-m3"
                },
                "output_dir": "experiments/results/preprint"
            }))

            with self.assertRaisesRegex(ValueError, "named-entity"):
                load_experiment_config(path)

    def test_writes_manifest_without_endpoint_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = tmp_path / "config.json"
            config_path.write_text(json.dumps({
                "experiment_name": "cross_task_named_hubs_smoke",
                "dataset": {
                    "name": "ai-hyz/MemoryAgentBench",
                    "split": "Accurate_Retrieval",
                    "sub_dataset": "eventqa_65536",
                    "max_samples": 1,
                    "max_queries": 20
                },
                "hub_selection": {
                    "top_k": 2,
                    "named_entity_only": True,
                    "exclude_stopwords_pronouns": True
                },
                "policies": ["no_propagation", "bfs", "attr_aware"],
                "metrics": ["em", "f1", "blast_radius", "severe_decay", "kill_rate"],
                "models": {
                    "llm_model": "google/gemma-4-31B-it",
                    "embedding_model": "BAAI/bge-m3"
                },
                "output_dir": str(tmp_path / "results")
            }))
            config = load_experiment_config(config_path)

            manifest_path = write_manifest(
                config,
                command=["python3", "experiments/run_preprint_setup.py", "--dry-run"],
                dry_run=True,
                extra={"llm_url": "https://example.invalid/secret/workload/v1"},
            )

            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["experiment_name"], "cross_task_named_hubs_smoke")
            self.assertTrue(manifest["run_id"].startswith("cross_task_named_hubs_smoke_"))
            self.assertIn("git_commit", manifest)
            self.assertEqual(manifest["config"]["dataset"]["split"], "Accurate_Retrieval")
            self.assertEqual(manifest["dry_run"], True)
            self.assertNotIn("llm_url", json.dumps(manifest))


if __name__ == "__main__":
    unittest.main()
