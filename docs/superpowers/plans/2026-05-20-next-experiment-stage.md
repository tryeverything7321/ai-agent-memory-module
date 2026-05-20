# Next Experiment Stage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current 5-sample named-hub result into a stronger preprint evidence package by measuring variance, explaining the sample-4 retrieval reversal, auditing ATTR-AWARE false negatives, and preparing a practical-harm table.

**Architecture:** Keep the current `research/20260520-preprint-followup` branch. Treat structural collateral damage and downstream retrieval F1 as separate outputs: collateral damage is the stable mechanism-level signal, while retrieval F1 is the practical-risk signal that must be reported with variance and exceptions. Add small, inspectable analysis scripts and commit only sanitized summaries, not raw endpoint-bearing JSON.

**Tech Stack:** Python 3.9 virtualenv at `.venv/`, experiment runners under `experiments/`, JSON results under `experiments/results/`, summaries under `docs/experiment_runs/`, manuscript planning under `docs/preprint_experiment_plan.md`.

---

## Current Baseline State

Completed and pushed:

- Branch: `research/20260520-preprint-followup`
- Commit: `bb3f485 harden named hub smoke selection`
- Commit: `662be64 record five-sample named hub run`
- Main result file: `experiments/results/accurate_retrieval_eventqa_65536_1779261391.json`
- Summary: `docs/experiment_runs/2026-05-20-cross-task-5sample-named-hubs.md`

Current result:

| Arm | EM | F1 | Avg collateral |
|---|---:|---:|---:|
| Baseline | 11.8 | 54.4 | 0.0 |
| BFS | 10.8 | 51.6 | 41.5 |
| ATTR-AWARE | 11.8 | 53.6 | 1.2 |

Interpretation locked in:

```text
Named-entity hub propagation consistently creates large collateral structural changes. Downstream retrieval harm appears in most sampled settings, but not all; retrieval impact is query- and graph-dependent.
```

---

## Files and Responsibilities

- Modify: `experiments/benchmark_accurate_retrieval.py`
  - Keep named-entity hub selection stable.
  - Add result fields only if needed for deeper per-query/per-memory analysis.
- Create: `experiments/analyze_cross_task_results.py`
  - Read existing result JSON.
  - Produce per-sample deltas, bootstrap intervals, and sample-4 diagnostics.
- Create: `experiments/sample_attr_false_negative_audit.py`
  - Sample BFS-reached but ATTR-AWARE-blocked memory pairs for manual labeling.
- Create: `docs/attr_aware_labeling_protocol.md`
  - Define label categories and decision rules.
- Create: `docs/experiment_runs/2026-05-20-cross-task-analysis.md`
  - Sanitized analysis summary with no private endpoints.
- Modify: `docs/preprint_experiment_plan.md`
  - Mark completed work and record next required experiments.

---

## Task 1: Add Cross-Task Result Analysis Script

**Files:**
- Create: `experiments/analyze_cross_task_results.py`
- Create: `tests/test_analyze_cross_task_results.py`

- [ ] **Step 1: Write the test**

Create `tests/test_analyze_cross_task_results.py`:

```python
import unittest

from experiments.analyze_cross_task_results import (
    compute_arm_deltas,
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
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
.venv/bin/python -m unittest tests.test_analyze_cross_task_results -v
```

Expected:

```text
ModuleNotFoundError: No module named 'experiments.analyze_cross_task_results'
```

- [ ] **Step 3: Implement the analysis script**

Create `experiments/analyze_cross_task_results.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any


def _metric(arm: dict[str, Any], name: str) -> float:
    return float(arm["metrics"][name])


def summarize_sample(sample: dict[str, Any]) -> dict[str, Any]:
    baseline_f1 = _metric(sample["baseline"], "f1")
    bfs_f1 = _metric(sample["bfs"], "f1")
    attr_f1 = _metric(sample["attribute_aware"], "f1")
    bfs_collateral = float(sample["bfs"].get("collateral_damage", 0.0))
    attr_collateral = float(sample["attribute_aware"].get("collateral_damage", 0.0))
    hubs = [
        str(hub["entity"])
        for hub in sample["baseline"].get("all_hubs", [])[:5]
    ]
    return {
        "sample_idx": int(sample["sample_idx"]),
        "hubs": hubs,
        "baseline_f1": round(baseline_f1, 1),
        "bfs_f1": round(bfs_f1, 1),
        "attr_f1": round(attr_f1, 1),
        "bfs_f1_delta": round(bfs_f1 - baseline_f1, 1),
        "attr_f1_delta": round(attr_f1 - baseline_f1, 1),
        "bfs_collateral": round(bfs_collateral, 1),
        "attr_collateral": round(attr_collateral, 1),
        "collateral_reduction": round(bfs_collateral - attr_collateral, 1),
    }


def compute_arm_deltas(sample_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    bfs_deltas = [float(sample["bfs_f1_delta"]) for sample in sample_summaries]
    attr_deltas = [float(sample["attr_f1_delta"]) for sample in sample_summaries]
    return {
        "n_samples": len(sample_summaries),
        "mean_bfs_f1_delta": round(mean(bfs_deltas), 1),
        "mean_attr_f1_delta": round(mean(attr_deltas), 1),
        "bfs_retrieval_drop_count": sum(delta < 0 for delta in bfs_deltas),
        "bfs_retrieval_gain_count": sum(delta > 0 for delta in bfs_deltas),
        "attr_retrieval_drop_count": sum(delta < 0 for delta in attr_deltas),
        "attr_retrieval_gain_count": sum(delta > 0 for delta in attr_deltas),
    }


def analyze(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    samples = [summarize_sample(sample) for sample in data["per_sample"]]
    return {
        "source_file": str(path),
        "aggregate": data["aggregate"],
        "per_sample": samples,
        "deltas": compute_arm_deltas(samples),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_json", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze(args.result_json)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test and py_compile**

Run:

```bash
.venv/bin/python -m unittest tests.test_analyze_cross_task_results -v
.venv/bin/python -m py_compile experiments/analyze_cross_task_results.py
```

Expected:

```text
OK
```

- [ ] **Step 5: Run analysis on the current 5-sample result**

Run:

```bash
.venv/bin/python experiments/analyze_cross_task_results.py \
  experiments/results/accurate_retrieval_eventqa_65536_1779261391.json \
  --output experiments/results/cross_task_analysis_20260520.json
```

Expected:

```text
experiments/results/cross_task_analysis_20260520.json exists and contains aggregate, per_sample, and deltas.
```

- [ ] **Step 6: Commit script and test only**

Do not commit raw JSON unless explicitly requested.

```bash
git add experiments/analyze_cross_task_results.py tests/test_analyze_cross_task_results.py
git commit -m "add cross-task result analysis"
```

---

## Task 2: Document the 5-Sample Result as a Claim Update

**Files:**
- Create: `docs/experiment_runs/2026-05-20-cross-task-analysis.md`
- Modify: `docs/preprint_experiment_plan.md`

- [ ] **Step 1: Create the sanitized result summary**

Create `docs/experiment_runs/2026-05-20-cross-task-analysis.md`:

```markdown
# 2026-05-20 Cross-Task Analysis

## Claim Update

The artifact-aware named-hub experiment strengthens the structural collateral
damage claim but narrows the retrieval degradation claim.

## Main Numbers

| Arm | F1 | Avg collateral |
|---|---:|---:|
| Baseline | 54.4 | 0.0 |
| BFS | 51.6 | 41.5 |
| ATTR-AWARE | 53.6 | 1.2 |

## Interpretation

BFS produces large collateral structural changes across all five samples.
Retrieval F1 drops in four samples and improves in one sample. The paper should
therefore present retrieval degradation as a practical risk observed in most
sampled settings, not as a deterministic consequence of BFS propagation.

## Revised Paper Claim

> Unfiltered propagation over named-entity hubs consistently expands the
> structural blast radius. Downstream retrieval degradation appears in most
> sampled settings, while ATTR-AWARE sharply reduces collateral damage and keeps
> aggregate retrieval close to baseline.
```

- [ ] **Step 2: Update the experiment tracker**

In `docs/preprint_experiment_plan.md`, change:

```markdown
- [ ] Expanded cross-task contamination over named-entity hubs.
```

to:

```markdown
- [x] Initial expanded cross-task contamination over named-entity hubs: 5 samples, 5 hubs/sample, 100 queries/sample.
- [ ] Larger cross-task contamination run with more samples or graph families.
```

- [ ] **Step 3: Commit docs**

```bash
git add docs/experiment_runs/2026-05-20-cross-task-analysis.md docs/preprint_experiment_plan.md
git commit -m "document cross-task claim update"
```

---

## Task 3: Investigate Sample 4 Retrieval Reversal

**Files:**
- Modify: `experiments/analyze_cross_task_results.py`
- Create: `docs/experiment_runs/2026-05-20-sample4-reversal.md`

- [ ] **Step 1: Add query-level reversal extraction**

Extend `experiments/analyze_cross_task_results.py` with:

```python
def query_level_deltas(sample: dict[str, Any]) -> list[dict[str, Any]]:
    baseline_queries = sample["baseline"].get("per_query", [])
    bfs_queries = sample["bfs"].get("per_query", [])
    rows = []
    for baseline, bfs in zip(baseline_queries, bfs_queries):
        baseline_f1 = float(baseline.get("f1", 0.0))
        bfs_f1 = float(bfs.get("f1", 0.0))
        rows.append({
            "question": baseline.get("question", ""),
            "answer": baseline.get("answer", ""),
            "baseline_prediction": baseline.get("prediction", ""),
            "bfs_prediction": bfs.get("prediction", ""),
            "baseline_f1": baseline_f1,
            "bfs_f1": bfs_f1,
            "delta": round(bfs_f1 - baseline_f1, 3),
        })
    return rows
```

- [ ] **Step 2: Add a CLI flag**

Add:

```python
parser.add_argument("--sample-idx", type=int)
parser.add_argument("--query-deltas", action="store_true")
```

If `--query-deltas` is provided, output only `query_level_deltas()` for the matching sample.

- [ ] **Step 3: Run sample 4 extraction**

Run:

```bash
.venv/bin/python experiments/analyze_cross_task_results.py \
  experiments/results/accurate_retrieval_eventqa_65536_1779261391.json \
  --sample-idx 4 \
  --query-deltas \
  --output experiments/results/sample4_query_deltas_20260520.json
```

Expected:

```text
JSON contains query-level baseline and BFS predictions with per-query F1 delta.
```

- [ ] **Step 4: Manually inspect top changes**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
rows = json.loads(Path("experiments/results/sample4_query_deltas_20260520.json").read_text())
for row in sorted(rows, key=lambda x: x["delta"], reverse=True)[:10]:
    print("DELTA", row["delta"])
    print("Q:", row["question"])
    print("A:", row["answer"])
    print("BASE:", row["baseline_prediction"])
    print("BFS:", row["bfs_prediction"])
    print()
PY
```

Expected:

```text
Top improved queries are visible for manual diagnosis.
```

- [ ] **Step 5: Write the reversal note**

Create `docs/experiment_runs/2026-05-20-sample4-reversal.md`:

```markdown
# 2026-05-20 Sample 4 Retrieval Reversal

## Observation

Sample 4 is the exception in the 5-sample named-hub run: BFS increases F1 from
43.7 to 55.2 while still causing high collateral damage.

## Working Interpretation

This does not refute the structural collateral-damage claim. It shows that
retrieval F1 can improve when broad downweighting suppresses distractor memories.
The paper should therefore avoid equating nonzero structural damage with direct
retrieval failure.

## Paper Implication

Report retrieval outcomes as practical-risk evidence with variance, and use
structural blast radius as the mechanism-level metric.
```

- [ ] **Step 6: Commit**

```bash
git add experiments/analyze_cross_task_results.py docs/experiment_runs/2026-05-20-sample4-reversal.md
git commit -m "analyze retrieval reversal case"
```

---

## Task 4: Prepare ATTR-AWARE False-Negative Audit

**Files:**
- Create: `docs/attr_aware_labeling_protocol.md`
- Create: `experiments/sample_attr_false_negative_audit.py`
- Create: `tests/test_sample_attr_false_negative_audit.py`

- [ ] **Step 1: Write the labeling protocol**

Create `docs/attr_aware_labeling_protocol.md`:

```markdown
# ATTR-AWARE Dependency Labeling Protocol

## Labels

`SHOULD_PROPAGATE`: the target memory depends on the invalidated fact; failing
to propagate would leave stale or contradictory memory.

`SHOULD_NOT_PROPAGATE`: the target memory only co-occurs with the invalidated
fact or shares an entity without depending on it.

`BORDERLINE`: dependency cannot be determined from the stored memory text alone.

## Decision Rules

Label `SHOULD_PROPAGATE` when the target memory states an attribute, event, or
relationship whose truth would change if the source fact is invalidated.

Label `SHOULD_NOT_PROPAGATE` when the target memory mentions the same entity but
describes an independent fact, unrelated event, or different relationship.

Label `BORDERLINE` when the target memory could depend on the source fact but
the dependency requires unstated background knowledge.
```

- [ ] **Step 2: Write sampler test**

Create `tests/test_sample_attr_false_negative_audit.py`:

```python
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
```

- [ ] **Step 3: Implement minimal sampler utility**

Create `experiments/sample_attr_false_negative_audit.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def make_audit_item(
    sample_idx: int,
    hub: str,
    source_memory: str,
    target_memory: str,
    bfs_reached: bool,
    attr_reached: bool,
) -> dict[str, Any]:
    if bfs_reached and not attr_reached:
        bucket = "bfs_reached_attr_blocked"
    elif bfs_reached and attr_reached:
        bucket = "attr_reached"
    else:
        bucket = "random_cooccurring"
    return {
        "sample_idx": sample_idx,
        "hub": hub,
        "source_memory": source_memory,
        "target_memory": target_memory,
        "bfs_reached": bfs_reached,
        "attr_reached": attr_reached,
        "bucket": bucket,
        "label": "",
        "notes": "",
    }


def write_template(output: Path) -> None:
    template = [
        make_audit_item(
            sample_idx=0,
            hub="Debbie",
            source_memory="Replace with invalidated memory text.",
            target_memory="Replace with candidate dependent memory text.",
            bfs_reached=True,
            attr_reached=False,
        )
    ]
    output.write_text(json.dumps(template, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_template(args.output)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

Run:

```bash
.venv/bin/python -m unittest tests.test_sample_attr_false_negative_audit -v
.venv/bin/python -m py_compile experiments/sample_attr_false_negative_audit.py
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit audit scaffolding**

```bash
git add docs/attr_aware_labeling_protocol.md experiments/sample_attr_false_negative_audit.py tests/test_sample_attr_false_negative_audit.py
git commit -m "scaffold attr-aware false-negative audit"
```

---

## Task 5: Run One Larger Cross-Task Replication

**Files:**
- Output only: `experiments/results/accurate_retrieval_eventqa_65536_<timestamp>.json`
- Create: `docs/experiment_runs/2026-05-20-cross-task-10sample-named-hubs.md`

- [ ] **Step 1: Run hub-list dry check**

Run:

```bash
.venv/bin/python experiments/benchmark_accurate_retrieval.py \
  --sub_dataset eventqa_65536 \
  --max_samples 10 \
  --max_queries 0 \
  --num_hubs 5 \
  --named_entity_hubs \
  --mock_embedding \
  --llm_model google/gemma-4-26B-A4B-it \
  --disable_graph_persist \
  --list_hubs_only
```

Expected:

```text
Every sample reports 5 hubs. No hubs are function words, pronouns, or obvious sentence artifacts.
```

- [ ] **Step 2: Run the 10-sample experiment if the dry check is clean**

Run:

```bash
.venv/bin/python experiments/benchmark_accurate_retrieval.py \
  --sub_dataset eventqa_65536 \
  --max_samples 10 \
  --max_queries 100 \
  --num_hubs 5 \
  --named_entity_hubs \
  --llm_url https://doogpu.doosan.com/standard/workspace/ws-94c8469a-43a7-4573-a455-2926fa446865/workload/wl-831a629b-4336-480d-8e5e-13f45a796ae6/reserved3/v1 \
  --llm_model google/gemma-4-26B-A4B-it \
  --embed_url https://doogpu.doosan.com/standard/workspace/ws-94c8469a-43a7-4573-a455-2926fa446865/workload/wl-831a629b-4336-480d-8e5e-13f45a796ae6/reserved9/v1 \
  --embed_model BAAI/bge-m3 \
  --disable_graph_persist
```

Expected:

```text
Result JSON is written under experiments/results/.
Aggregate metrics include baseline, bfs, and attribute_aware.
```

- [ ] **Step 3: Summarize without committing raw JSON**

Create `docs/experiment_runs/2026-05-20-cross-task-10sample-named-hubs.md` with:

```markdown
# 2026-05-20 Cross-Task Named-Hub Run: 10 Samples

## Configuration

- Dataset: `Accurate_Retrieval / eventqa_65536`
- Samples: 10
- Queries per sample: 100
- Hubs per sample: 5
- Hub selection: named-entity-like + triggerable fact required
- LLM: `google/gemma-4-26B-A4B-it`
- Embedding model: `BAAI/bge-m3`

## Aggregate Result

Fill this table from the run output:

| Arm | EM | F1 | Avg collateral |
|---|---:|---:|---:|
| Baseline | 0.0 | 0.0 | 0.0 |
| BFS | 0.0 | 0.0 | 0.0 |
| ATTR-AWARE | 0.0 | 0.0 | 0.0 |

## Interpretation

Compare against the 5-sample run. State whether the structural collateral
damage result replicated and whether retrieval F1 remains mixed.
```

- [ ] **Step 4: Commit the sanitized summary**

```bash
git add docs/experiment_runs/2026-05-20-cross-task-10sample-named-hubs.md
git commit -m "record ten-sample named hub run"
```

---

## Task 6: Push the Branch

**Files:**
- No file changes required.

- [ ] **Step 1: Run final checks**

Run:

```bash
.venv/bin/python -m unittest tests.test_preprint_config tests.test_preprint_hubs tests.test_analyze_cross_task_results tests.test_sample_attr_false_negative_audit -v
git status --short --branch
```

Expected:

```text
All tests pass.
Only raw result JSONs and local PDFs are untracked.
```

- [ ] **Step 2: Push**

Run:

```bash
git push
```

Expected:

```text
research/20260520-preprint-followup pushed to origin.
```

---

## Self-Review

- Spec coverage: This plan addresses the next concrete gaps after the 5-sample run: variance, retrieval reversal, false-negative audit scaffolding, larger replication, and sanitized documentation.
- Placeholder scan: The only intentionally fillable section is the 10-sample result table after the run finishes; all commands and file paths are concrete.
- Type consistency: New functions use plain dictionaries and JSON to match the existing experiment result format.
