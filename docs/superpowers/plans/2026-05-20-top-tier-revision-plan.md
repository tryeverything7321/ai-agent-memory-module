# Top-Tier Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the rejected workshop paper into a stronger preprint or top-tier submission by turning the current finding into a defensible systems-safety claim: graph-memory maintenance can create uncontrolled structural interventions that retrieval accuracy alone may hide.

**Architecture:** Separate the project into four evidence layers: thesis/narrative, cross-family replication, graph-construction robustness, and mitigation cost. Do not make retrieval degradation the central invariant. The invariant is structural blast radius under unfiltered co-occurrence propagation; retrieval is a downstream behavior that can degrade or improve depending on query and distractor conditions.

**Tech Stack:** Python experiment scripts in `experiments/`, tests in `tests/`, raw local results in `experiments/results/`, sanitized summaries in `docs/experiment_runs/`, manuscript planning in `docs/preprint_experiment_plan.md`, paper source in `paper/`.

---

## Current State

Known results:

| Dataset | Policy | Blast radius | Collateral | Below threshold | F1 delta |
|---|---|---:|---:|---:|---:|
| EventQA 64K | BFS | 3245.2 | 41.5 | 327.6 | -2.8 |
| EventQA 64K | ATTR-AWARE | 791.2 | 1.2 | 2.0 | -0.7 |
| EventQA 131K | BFS | 6327.3 | 33.4 | 708.0 | +7.2 |
| EventQA 131K | ATTR-AWARE | 3221.6 | 1.8 | 7.8 | +0.7 |

Locked interpretation:

```text
Unfiltered BFS propagation reliably creates a large structural blast radius.
Downstream retrieval accuracy is unstable: it can decrease or increase, so F1
alone is not a sufficient safety metric for graph-memory maintenance.
```

Do not return to the old headline:

```text
BFS always degrades retrieval.
```

---

## Decision Principles

1. **Invariant first:** prioritize results that repeat across settings.
2. **Artifact defense second:** avoid raw function-word hubs and test graph construction variants.
3. **Practical harm third:** report blast radius, collateral, below-threshold memories, retrievable loss, and F1 separately.
4. **Defense honesty:** ATTR-AWARE is a guardrail, not a free improvement; measure over-propagation and missed-dependency risk.
5. **No premature manual labeling:** label only after the trace pipeline and buckets are stable.

---

## Task 1: Thesis Memo and Paper Reframing

**Files:**
- Create: `docs/revision_thesis_memo_20260520.md`
- Modify: `docs/preprint_experiment_plan.md`

- [ ] **Step 1: Create thesis memo**

Create `docs/revision_thesis_memo_20260520.md`:

```markdown
# Revision Thesis Memo

## One-Sentence Claim

Graph-based memory maintenance over co-occurrence structures can create large,
uncontrolled structural interventions; retrieval accuracy may hide or invert
these interventions, so memory-maintenance safety needs structural metrics in
addition to downstream task accuracy.

## What Changed After New Experiments

The original workshop submission framed cross-task F1 degradation as a central
practical harm. The new 64K and 131K results show that this is too narrow:
BFS decreases F1 on EventQA 64K but increases F1 on EventQA 131K. The invariant
is not retrieval degradation; the invariant is large structural blast radius.

## Revised Findings

1. Unfiltered BFS over co-occurrence memory graphs creates a large structural
   blast radius under named-entity hub triggers.
2. Retrieval impact is unstable: broad propagation can degrade retrieval or
   improve apparent F1 by suppressing distractors/refusals.
3. ATTR-AWARE sharply reduces collateral and below-threshold damage, but larger
   contexts show it can still affect many memories for some hubs.
4. Accuracy-only evaluation is insufficient for graph-memory maintenance safety.

## Claims to Avoid

- BFS always degrades retrieval.
- Nonzero decay equals corruption.
- ATTR-AWARE is cost-free.
- EventQA results establish broad generality.

## Target Paper Framing

This is not primarily an attack paper. It is a systems-safety paper about
maintenance operations in long-term agent memory.
```

- [ ] **Step 2: Update tracker with thesis state**

Add this section to `docs/preprint_experiment_plan.md` after the intro:

```markdown
## Current Thesis

The current invariant is structural blast radius, not retrieval degradation.
Future experiments should test whether the blast-radius gap between BFS and
guarded propagation survives across dataset families and graph construction
variants.
```

- [ ] **Step 3: Commit**

```bash
git add docs/revision_thesis_memo_20260520.md docs/preprint_experiment_plan.md
git commit -m "record revised structural safety thesis"
```

---

## Task 2: Cross-Family Replication

**Files:**
- No code changes expected.
- Output: raw JSON under `experiments/results/`
- Create: `docs/experiment_runs/2026-05-20-cross-task-longmemeval-named-hubs.md`
- Modify: `docs/experiment_runs/2026-05-20-practical-harm-summary.md`

- [ ] **Step 1: Dry-check LongMemEval hubs**

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
5 samples loaded. Each sample has 5 named/actionable hubs. No obvious function-word or pronoun artifacts appear.
```

- [ ] **Step 2: If hubs are clean, run LongMemEval**

Run:

```bash
.venv/bin/python experiments/benchmark_accurate_retrieval.py \
  --sub_dataset 'longmemeval_s*' \
  --max_samples 5 \
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
Result JSON is written. Aggregate includes baseline, bfs, and attribute_aware.
```

- [ ] **Step 3: Generate practical-harm row**

Run:

```bash
.venv/bin/python experiments/summarize_practical_harm.py \
  experiments/results/accurate_retrieval_eventqa_65536_1779261391.json \
  experiments/results/accurate_retrieval_eventqa_131072_1779265059.json \
  experiments/results/<LONGMEMEVAL_RESULT>.json \
  --format markdown \
  --output experiments/results/practical_harm_summary_with_longmemeval_20260520.md
```

Expected:

```text
Markdown table includes EventQA 64K, EventQA 131K, and LongMemEval rows.
```

- [ ] **Step 4: Write sanitized summary**

Create `docs/experiment_runs/2026-05-20-cross-task-longmemeval-named-hubs.md`:

```markdown
# 2026-05-20 Cross-Task Named-Hub Run: LongMemEval

## Configuration

- Dataset: `Accurate_Retrieval / longmemeval_s*`
- Samples: 5
- Queries per sample: 100
- Hubs per sample: 5
- Hub selection: named-entity-like + triggerable fact required
- LLM: `google/gemma-4-26B-A4B-it`
- Embedding model: `BAAI/bge-m3`

## Aggregate Result

Paste aggregate table from the run.

## Interpretation

State whether the structural blast-radius gap replicated outside EventQA.
Do not overclaim retrieval degradation unless F1 consistently drops.
```

- [ ] **Step 5: Commit**

```bash
git add docs/experiment_runs/2026-05-20-cross-task-longmemeval-named-hubs.md docs/experiment_runs/2026-05-20-practical-harm-summary.md
git commit -m "record longmemeval cross-family replication"
```

---

## Task 3: Graph Construction Variant Design

**Files:**
- Create: `docs/graph_construction_variant_design.md`
- Create: `experiments/graph_variant_config.py`
- Create: `tests/test_graph_variant_config.py`

- [ ] **Step 1: Write variant design doc**

Create `docs/graph_construction_variant_design.md`:

```markdown
# Graph Construction Variant Design

## Purpose

The paper must show that the blast-radius result is not only an artifact of one
rule-based extraction pipeline.

## Variants

1. `raw_rule_based`: current graph construction.
2. `stopword_pronoun_filtered`: remove function-word and pronoun entity nodes.
3. `named_entity_actionable`: current headline hub selection; graph unchanged.
4. `typed_relation_only`: propagate only over facts with explicit subject:attribute keys.

## Minimum Acceptance Criterion

The qualitative BFS > ATTR-AWARE blast-radius gap should survive at least
`raw_rule_based`, `stopword_pronoun_filtered`, and `typed_relation_only`.

## Paper Use

If graph variants reduce absolute blast radius but preserve ordering, the paper
can claim the failure mode is not solely caused by extraction artifacts.
```

- [ ] **Step 2: Write config test**

Create `tests/test_graph_variant_config.py`:

```python
import unittest

from experiments.graph_variant_config import GRAPH_VARIANTS, validate_variant


class GraphVariantConfigTests(unittest.TestCase):
    def test_expected_variants_exist(self):
        self.assertIn("raw_rule_based", GRAPH_VARIANTS)
        self.assertIn("stopword_pronoun_filtered", GRAPH_VARIANTS)
        self.assertIn("typed_relation_only", GRAPH_VARIANTS)

    def test_validate_variant_rejects_unknown(self):
        with self.assertRaises(ValueError):
            validate_variant("unknown")
```

- [ ] **Step 3: Implement minimal config**

Create `experiments/graph_variant_config.py`:

```python
GRAPH_VARIANTS = {
    "raw_rule_based": {
        "description": "Current graph construction without additional filtering.",
        "filter_entities": False,
        "typed_edges_only": False,
    },
    "stopword_pronoun_filtered": {
        "description": "Remove function-word/pronoun entity nodes before analysis.",
        "filter_entities": True,
        "typed_edges_only": False,
    },
    "typed_relation_only": {
        "description": "Restrict propagation analysis to subject:attribute-style facts.",
        "filter_entities": True,
        "typed_edges_only": True,
    },
}


def validate_variant(name: str) -> dict:
    if name not in GRAPH_VARIANTS:
        raise ValueError(f"Unknown graph variant: {name}")
    return GRAPH_VARIANTS[name]
```

- [ ] **Step 4: Run tests**

Run:

```bash
.venv/bin/python -m unittest tests.test_graph_variant_config -v
.venv/bin/python -m py_compile experiments/graph_variant_config.py
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```bash
git add docs/graph_construction_variant_design.md experiments/graph_variant_config.py tests/test_graph_variant_config.py
git commit -m "design graph construction variants"
```

---

## Task 4: Trace-Enabled Audit Candidate Run

**Files:**
- Output: raw JSON under `experiments/results/`
- Output: audit candidates under `experiments/results/`
- Create: `docs/experiment_runs/2026-05-20-attr-audit-candidates.md`

- [ ] **Step 1: Run trace-enabled no-query candidate generation**

Run:

```bash
.venv/bin/python experiments/benchmark_accurate_retrieval.py \
  --sub_dataset eventqa_65536 \
  --max_samples 3 \
  --max_queries 0 \
  --num_hubs 5 \
  --named_entity_hubs \
  --mock_embedding \
  --llm_model google/gemma-4-26B-A4B-it \
  --disable_graph_persist \
  --include_audit_trace \
  --audit_trace_limit 100
```

Expected:

```text
Trace-enabled result JSON is written.
```

- [ ] **Step 2: Generate audit candidates**

Run:

```bash
.venv/bin/python experiments/sample_attr_false_negative_audit.py \
  --result-json experiments/results/<TRACE_RESULT>.json \
  --max-items-per-bucket 50 \
  --output experiments/results/attr_audit_candidates_20260520.json
```

Expected:

```text
Candidate JSON contains bfs_reached_attr_blocked items and, if available, attr_reached items.
```

- [ ] **Step 3: Write sanitized audit candidate summary**

Create `docs/experiment_runs/2026-05-20-attr-audit-candidates.md`:

```markdown
# 2026-05-20 ATTR-AWARE Audit Candidates

## Purpose

Prepare a balanced manual audit set for measuring ATTR-AWARE missed-dependency
risk.

## Candidate Buckets

- `bfs_reached_attr_blocked`: potential false negatives for ATTR-AWARE.
- `attr_reached`: accepted propagation controls.

## Next Labeling Step

Use `docs/attr_aware_labeling_protocol.md` and label each item as
`SHOULD_PROPAGATE`, `SHOULD_NOT_PROPAGATE`, or `BORDERLINE`.
```

- [ ] **Step 4: Commit code/docs only**

Do not commit raw candidate JSON unless explicitly requested.

```bash
git add docs/experiment_runs/2026-05-20-attr-audit-candidates.md
git commit -m "record attr audit candidate generation"
```

---

## Task 5: Paper Outline Rewrite

**Files:**
- Create: `paper/preprint_outline_20260520.md`

- [ ] **Step 1: Write outline**

Create `paper/preprint_outline_20260520.md`:

```markdown
# Preprint Outline

## Title Direction

Structural Safety Risks in Graph-Based Agent Memory Maintenance

## Abstract Shape

1. Graph-augmented memory systems invite propagation-style maintenance.
2. Co-occurrence graphs do not encode dependency.
3. Unfiltered BFS creates large structural blast radius across named-entity hubs.
4. Retrieval accuracy can move up or down, showing accuracy alone is insufficient.
5. ATTR-AWARE reduces collateral structural damage but requires missed-dependency audit.

## Main Findings

Finding 1: BFS creates large structural blast radius.
Finding 2: Retrieval effects are unstable, not monotonically harmful.
Finding 3: ATTR-AWARE reduces collateral and below-threshold damage.
Finding 4: Guardrails must be evaluated for under-propagation.

## Main Tables

1. Practical-harm summary table.
2. Cross-family replication table.
3. Graph construction variant table.
4. ATTR-AWARE audit table.
```

- [ ] **Step 2: Commit**

```bash
git add paper/preprint_outline_20260520.md
git commit -m "outline revised preprint narrative"
```

---

## Task 6: Final Verification and Push

**Files:**
- No new files.

- [ ] **Step 1: Run tests**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_preprint_config \
  tests.test_preprint_hubs \
  tests.test_analyze_cross_task_results \
  tests.test_sample_attr_false_negative_audit \
  tests.test_summarize_practical_harm \
  tests.test_graph_variant_config \
  -v
```

Expected:

```text
OK
```

- [ ] **Step 2: Check git state**

Run:

```bash
git status --short --branch
```

Expected:

```text
Branch is ahead only by committed changes, with raw result JSONs still untracked.
```

- [ ] **Step 3: Push**

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

- This plan prioritizes thesis correction before more labeling.
- It addresses the strongest remaining reviewer risks: EventQA-only evidence, graph extraction artifact, broad damage metric, and ATTR-AWARE cost.
- It avoids premature manual labeling until trace generation and buckets are stable.
- It does not treat retrieval degradation as the central invariant.
