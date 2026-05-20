# Preprint Experiment Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the initial experiment setup layer for the stronger preprint: a tracked experiment plan, typed config loader, manifest writer, and smoke-test command that does not require GPU/API access.

**Architecture:** Keep the setup layer separate from heavy MemoryAgentBench runs. `experiments/preprint_config.py` owns config validation and manifest generation using only the Python standard library. `experiments/configs/preprint_smoke.json` defines the first dry-run experiment profile, and later runners can consume the same schema.

**Tech Stack:** Python 3 standard library, JSON config files, `unittest` for dependency-free tests, existing `experiments/results/` output convention.

---

## File Structure

- Create: `docs/preprint_experiment_plan.md`  
  Human-facing tracker for the research program.
- Create: `experiments/preprint_config.py`  
  Dataclasses, config loading, validation, deterministic run-id creation, and manifest writing.
- Create: `experiments/configs/preprint_smoke.json`  
  First smoke-test config for expanded cross-task work.
- Create: `experiments/run_preprint_setup.py`  
  CLI that validates a config and writes a manifest without running GPU/API experiments.
- Create: `tests/test_preprint_config.py`  
  Dependency-free tests for config validation and manifest generation.

## Task 1: Config Validation

**Files:**
- Create: `tests/test_preprint_config.py`
- Create: `experiments/preprint_config.py`

- [ ] **Step 1: Write failing tests**

```python
import json
import tempfile
import unittest
from pathlib import Path

from experiments.preprint_config import load_experiment_config


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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m unittest tests.test_preprint_config -v
```

Expected: import failure because `experiments.preprint_config` does not exist yet.

- [ ] **Step 3: Implement config loader**

Create `experiments/preprint_config.py` with dataclasses and validation.

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m unittest tests.test_preprint_config -v
```

Expected: 2 tests pass.

## Task 2: Manifest Writer and Dry-run CLI

**Files:**
- Modify: `tests/test_preprint_config.py`
- Modify: `experiments/preprint_config.py`
- Create: `experiments/configs/preprint_smoke.json`
- Create: `experiments/run_preprint_setup.py`

- [ ] **Step 1: Add failing manifest test**

Test that `write_manifest` creates a JSON file with experiment name, run id, git commit, config, and no secrets.

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m unittest tests.test_preprint_config -v
```

Expected: failure because `write_manifest` does not exist.

- [ ] **Step 3: Implement manifest writer**

Add `make_run_id`, `get_git_commit`, `to_manifest_dict`, and `write_manifest`.

- [ ] **Step 4: Add smoke config and CLI**

Add `experiments/configs/preprint_smoke.json` and `experiments/run_preprint_setup.py`.

- [ ] **Step 5: Run smoke command**

```bash
python3 experiments/run_preprint_setup.py --config experiments/configs/preprint_smoke.json --dry-run
```

Expected: prints config summary and writes one manifest under `experiments/results/preprint/`.

## Task 3: Commit Setup

**Files:**
- Add all files from Tasks 1-2.

- [ ] **Step 1: Run dependency-free tests**

```bash
python3 -m unittest tests.test_preprint_config -v
```

Expected: all tests pass.

- [ ] **Step 2: Check git status**

```bash
git status --short
```

Expected: only intended setup files plus pre-existing untracked `paper/workshop_20260428.pdf`.

- [ ] **Step 3: Commit**

```bash
git add docs/preprint_experiment_plan.md docs/superpowers/plans/2026-05-20-experiment-setup.md experiments/preprint_config.py experiments/configs/preprint_smoke.json experiments/run_preprint_setup.py tests/test_preprint_config.py
git commit -m "set up preprint experiment tracking"
```

## Self-review

- Spec coverage: covers plan creation, experiment setup, config validation, manifest generation, and dry-run execution.
- Placeholder scan: no placeholder tasks; every command and file path is concrete.
- Type consistency: config field names match the smoke JSON and tests.
