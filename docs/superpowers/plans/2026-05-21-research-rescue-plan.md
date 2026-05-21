# Research Rescue and Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decide whether the graph-memory forgetting paper can become a credible preprint/top-tier submission, and if so rebuild it around claims that survive artifact checks, benchmark transfer, and controlled ground truth.

**Architecture:** Treat the workshop rejection as a claim-scope failure, not a dead project. Rebuild the research in three gates: (1) establish clean graph construction, (2) prove the mechanism on controlled data with known dependencies, (3) then return to real benchmarks as external validity checks. Do not spend more GPU time on real benchmark full runs until graph/template artifacts are controlled.

**Tech Stack:** Python experiment scripts under `experiments/`, tests under `tests/`, design notes under `docs/`, sanitized summaries under `docs/experiment_runs/`, paper outline under `paper/`.

---

## Current Diagnosis

The old workshop claim was too broad:

```text
BFS-style forgetting propagation causes collateral forgetting and degrades unrelated retrieval.
```

The evidence now supports a narrower and more interesting claim:

```text
Unfiltered propagation over co-occurrence-derived memory graphs can create large,
uncontrolled structural interventions. Retrieval accuracy can decrease or
increase, so task accuracy alone is not a sufficient safety metric for memory
maintenance.
```

Reviewer concerns that turned out to be real:

- raw hub artifacts exist (`And`, `She`, `But`, `Then`);
- LongMemEval has stronger template artifacts (`Chat Time`, `Here`, `Use`, `Make`, `Can`);
- clean full evidence is currently EventQA-family only;
- retrieval degradation is not invariant;
- ATTR-AWARE is a partial guardrail, not a complete solution.

Therefore the next work must not be “run more of the same.” It must test whether
the mechanism exists under cleaner graph construction and controlled dependency
ground truth.

---

## Go / No-Go Criteria

Continue toward preprint/top-tier only if all three gates pass:

1. **Clean Graph Gate:** after filtering template/function artifacts, top hubs are content entities in at least two settings.
2. **Controlled Mechanism Gate:** on synthetic controlled memory graphs, BFS creates higher blast radius than dependency-aware propagation while true dependency propagation is known.
3. **External Validity Gate:** at least one real benchmark setting shows the same structural-metric ordering after artifact controls.

If Gate 2 fails, stop and write this as an engineering postmortem, not a paper.

---

## Task 1: Claim Triage Memo

**Files:**
- Create: `docs/claim_triage_20260521.md`
- Modify: `docs/preprint_experiment_plan.md`

- [ ] **Step 1: Create claim triage memo**

Create `docs/claim_triage_20260521.md`:

```markdown
# Claim Triage Memo

## Claims That Survive Current Evidence

1. Unfiltered BFS over co-occurrence memory graphs creates large structural blast radius on EventQA-family settings.
2. Retrieval F1 is unstable and can move opposite to structural damage.
3. Named-entity hub filtering reduces raw artifact risk but does not solve graph-construction validity.
4. ATTR-AWARE usually reduces collateral and below-threshold damage, but needs under-propagation and affected-count audits.

## Claims That Do Not Survive

1. BFS always degrades retrieval.
2. Current evidence generalizes to graph memory systems broadly.
3. LongMemEval can be used as-is for headline replication.
4. ATTR-AWARE is cost-free.

## Rebuild Thesis

The paper should become a structural safety evaluation paper: memory maintenance
operations should be evaluated with graph-state metrics and dependency-grounded
audits, not only downstream retrieval accuracy.

## Required New Evidence

1. Template/artifact filtering for graph construction.
2. Controlled synthetic benchmark with known dependency graph.
3. Real-benchmark validation after graph sanity checks.
```

- [ ] **Step 2: Update tracker**

Add to `docs/preprint_experiment_plan.md`:

```markdown
## Rescue Gates

- [ ] Clean Graph Gate
- [ ] Controlled Mechanism Gate
- [ ] External Validity Gate
```

- [ ] **Step 3: Commit**

```bash
git add docs/claim_triage_20260521.md docs/preprint_experiment_plan.md
git commit -m "triage surviving research claims"
```

---

## Task 2: Template Artifact Filter

**Files:**
- Modify: `experiments/preprint_hubs.py`
- Modify: `tests/test_preprint_hubs.py`
- Create: `docs/template_artifact_filter_policy.md`

- [ ] **Step 1: Extend hub filter test**

Add this test to `tests/test_preprint_hubs.py`:

```python
    def test_filters_chat_template_artifacts(self):
        raw_hubs = [
            {"entity": "Chat Time", "degree": 7407},
            {"entity": "Here", "degree": 7087},
            {"entity": "Use", "degree": 5337},
            {"entity": "Make", "degree": 4316},
            {"entity": "Can", "degree": 6376},
            {"entity": "Debbie", "degree": 715},
            {"entity": "Paris", "degree": 296},
        ]

        filtered = filter_named_entity_hubs(raw_hubs, top_k=5)

        self.assertEqual([hub["entity"] for hub in filtered], ["Debbie", "Paris"])
```

- [ ] **Step 2: Run failing test**

Run:

```bash
.venv/bin/python -m unittest tests.test_preprint_hubs -v
```

Expected:

```text
FAIL because template artifacts are not all filtered yet.
```

- [ ] **Step 3: Update artifact set**

Modify `experiments/preprint_hubs.py` and add these normalized tokens to
`STOPWORDS_AND_PRONOUNS`:

```python
"avoid",
"can",
"chat time",
"check",
"here",
"make",
"remember",
"start",
"tips",
"use",
```

- [ ] **Step 4: Add filter policy doc**

Create `docs/template_artifact_filter_policy.md`:

```markdown
# Template Artifact Filter Policy

## Purpose

Long-context benchmarks can introduce instruction/template phrases that dominate
naive entity graphs. These phrases must not be used as semantic hub evidence.

## Filtered Template Hubs

`Chat Time`, `Here`, `Use`, `Make`, `Can`, `Tips`, `Start`, `Avoid`,
`Remember`, `Check`.

## Paper Policy

Report raw hub lists only as diagnostics. Headline claims must use content-entity
hubs after function-word, pronoun, and template-artifact filtering.
```

- [ ] **Step 5: Run tests**

Run:

```bash
.venv/bin/python -m unittest tests.test_preprint_hubs -v
.venv/bin/python -m py_compile experiments/preprint_hubs.py
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit**

```bash
git add experiments/preprint_hubs.py tests/test_preprint_hubs.py docs/template_artifact_filter_policy.md
git commit -m "filter template artifact hubs"
```

---

## Task 3: Re-run LongMemEval Dry Check After Filtering

**Files:**
- Create: `docs/experiment_runs/2026-05-21-longmemeval-filtered-dry-check.md`

- [ ] **Step 1: Run dry check**

Run:

```bash
.venv/bin/python experiments/benchmark_accurate_retrieval.py \
  --sub_dataset 'longmemeval_s*' \
  --max_samples 5 \
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
Dry check either produces content hubs or reveals additional dataset artifacts.
```

- [ ] **Step 2: Write dry-check report**

Create `docs/experiment_runs/2026-05-21-longmemeval-filtered-dry-check.md`:

```markdown
# 2026-05-21 LongMemEval Filtered Dry Check

## Result

Record top hubs after template filtering.

## Decision

If top hubs are content entities, LongMemEval can be scheduled for a full run.
If top hubs remain template artifacts, do not use LongMemEval for headline
evidence without stronger preprocessing.
```

- [ ] **Step 3: Commit**

```bash
git add docs/experiment_runs/2026-05-21-longmemeval-filtered-dry-check.md
git commit -m "record filtered longmemeval dry check"
```

---

## Task 4: Controlled Synthetic Benchmark Spec

**Files:**
- Create: `docs/controlled_synthetic_benchmark_spec.md`
- Create: `experiments/synthetic_memory_graph.py`
- Create: `tests/test_synthetic_memory_graph.py`

- [ ] **Step 1: Write synthetic benchmark test**

Create `tests/test_synthetic_memory_graph.py`:

```python
import unittest

from experiments.synthetic_memory_graph import build_synthetic_graph


class SyntheticMemoryGraphTests(unittest.TestCase):
    def test_builds_hub_with_known_dependencies(self):
        graph = build_synthetic_graph(num_entities=6, facts_per_entity=2)

        self.assertIn("E0", graph["entities"])
        self.assertGreater(len(graph["cooccurrence_edges"]), 0)
        self.assertGreater(len(graph["dependency_edges"]), 0)
        self.assertNotEqual(
            set(graph["cooccurrence_edges"]),
            set(graph["dependency_edges"]),
        )
```

- [ ] **Step 2: Implement minimal synthetic graph builder**

Create `experiments/synthetic_memory_graph.py`:

```python
from __future__ import annotations


def build_synthetic_graph(num_entities: int, facts_per_entity: int) -> dict:
    entities = [f"E{i}" for i in range(num_entities)]
    memories = []
    cooccurrence_edges = []
    dependency_edges = []

    hub = entities[0]
    for entity in entities:
        for fact_idx in range(facts_per_entity):
            memory_id = f"{entity}_fact_{fact_idx}"
            memories.append({
                "id": memory_id,
                "subject": entity,
                "attribute": f"attr_{fact_idx}",
                "text": f"{entity} has attr_{fact_idx}.",
            })
            if entity != hub:
                cooccurrence_edges.append((hub, entity))
            if fact_idx > 0:
                dependency_edges.append((f"{entity}_fact_0", memory_id))

    return {
        "entities": entities,
        "memories": memories,
        "cooccurrence_edges": cooccurrence_edges,
        "dependency_edges": dependency_edges,
    }
```

- [ ] **Step 3: Write benchmark spec**

Create `docs/controlled_synthetic_benchmark_spec.md`:

```markdown
# Controlled Synthetic Benchmark Spec

## Purpose

Create a benchmark where co-occurrence edges and true dependency edges are known
separately. This is the cleanest test of whether BFS over co-occurrence creates
over-propagation.

## Core Design

- Entities: `E0 ... En`
- Hub: `E0`
- Co-occurrence edges connect the hub to many entities.
- True dependency edges connect only facts whose validity logically depends on
  the changed fact.

## Metrics

- BFS false-positive propagation rate
- Dependency-aware false-negative rate
- Blast radius
- True dependency recall
- Collateral damage under known ground truth

## Paper Role

This should be the mechanism proof. Real benchmarks become external validity,
not the only source of truth.
```

- [ ] **Step 4: Run tests**

Run:

```bash
.venv/bin/python -m unittest tests.test_synthetic_memory_graph -v
.venv/bin/python -m py_compile experiments/synthetic_memory_graph.py
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```bash
git add docs/controlled_synthetic_benchmark_spec.md experiments/synthetic_memory_graph.py tests/test_synthetic_memory_graph.py
git commit -m "spec controlled synthetic benchmark"
```

---

## Task 5: Revised Paper Decision Memo

**Files:**
- Create: `docs/paper_decision_memo_20260521.md`

- [ ] **Step 1: Write decision memo**

Create `docs/paper_decision_memo_20260521.md`:

```markdown
# Paper Decision Memo

## Current Decision

Do not submit the current paper as a broad graph-memory vulnerability paper.
Continue only as a structural safety evaluation paper.

## Why

Reviewer concerns about artifacts and benchmark narrowness were correct. The
new results show that retrieval degradation is not invariant, but structural
blast radius is still a meaningful signal.

## Required Before Preprint

1. Controlled synthetic mechanism result.
2. Artifact-filtered real benchmark validation.
3. Graph construction variant table.
4. ATTR-AWARE missed-dependency audit.

## Kill Criteria

If synthetic controlled results do not show BFS over-propagation relative to
dependency-aware propagation, stop the paper.
```

- [ ] **Step 2: Commit**

```bash
git add docs/paper_decision_memo_20260521.md
git commit -m "record paper continuation criteria"
```

---

## Task 6: Final Verification and Push

**Files:**
- No new files.

- [ ] **Step 1: Run verification**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_preprint_hubs \
  tests.test_synthetic_memory_graph \
  -v
```

Expected:

```text
OK
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

- This plan does not pretend the previous evidence was stronger than it was.
- It puts controlled mechanism proof before more benchmark full runs.
- It uses LongMemEval only after artifact filtering.
- It includes explicit kill criteria, so the project does not drift indefinitely.
