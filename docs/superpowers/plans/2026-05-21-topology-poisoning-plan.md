# Topology Poisoning Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the graph-memory paper with a defensible topology-poisoning threat model: repeated generic/template phrases can fabricate artificial graph hubs, creating unsafe propagation pathways even when the attacker does not know existing content-entity hubs.

**Architecture:** Keep two claims separate. Claim A is content-hub risk: clean content entities can produce large blast radius. Claim B is topology poisoning: graph construction can be manipulated so non-semantic repeated phrases become hubs. LongMemEval template hubs are not attack success by themselves; they are evidence of a vulnerability surface that must be validated by a controlled injection experiment.

**Tech Stack:** Existing Python benchmark scripts in `experiments/`, tests in `tests/`, sanitized run notes in `docs/experiment_runs/`, paper planning docs in `docs/` and `paper/`.

---

## Core Thesis

The revised paper should say:

```text
Graph-memory maintenance is only as safe as the graph construction process.
Unfiltered propagation can fail through natural content hubs, and naive entity
extraction can also create artificial hubs from repeated generic/template
phrases. These fabricated hubs create a topology-poisoning surface for memory
maintenance operations.
```

Do not say yet:

```text
LongMemEval proves an attacker can successfully poison graph memory.
```

Safer current wording:

```text
LongMemEval dry checks reveal a graph-construction failure mode: repeated
template phrases can dominate hub rankings. This motivates a controlled
topology-poisoning experiment.
```

---

## Evidence Ladder

1. **Observation:** LongMemEval top hubs are template/generic phrases.
2. **Controlled attack:** Inject repeated benign-looking phrases into a clean memory stream and show they become high-degree hubs.
3. **Propagation consequence:** Triggering invalidation from the fabricated hub creates higher blast radius/collateral than a non-injected control.
4. **Mitigation:** template/entity filtering, typed relation extraction, or provenance-aware graph construction reduces artificial hub formation.

---

## Task 1: Threat Model Memo

**Files:**
- Create: `docs/topology_poisoning_threat_model.md`
- Modify: `docs/claim_triage_20260521.md` if it exists

- [ ] **Step 1: Create threat model memo**

Create `docs/topology_poisoning_threat_model.md`:

```markdown
# Topology Poisoning Threat Model

## Definition

Topology poisoning is an attack on graph-memory construction in which repeated
generic or template-like phrases are extracted as entities and become
high-degree graph hubs. Later maintenance operations such as invalidation or
forgetting propagation can traverse these fabricated hubs.

## Difference From Content-Hub Attack

Content-hub attack targets an existing high-degree content entity such as a
person, location, or organization.

Topology poisoning fabricates the hub itself by repeatedly introducing phrases
such as `Project Note`, `Current Context`, `Important Reminder`, or `Chat Time`.

## Attacker Capability

The attacker can write memories or messages that are stored by the memory system.
The attacker does not need direct graph access. The attacker may not know the
current graph topology.

## Current Evidence

LongMemEval dry checks show that repeated template phrases such as `Chat Time`,
`Here`, `Use`, `Make`, and `Can` can dominate naive hub rankings. This is not yet
an attack result; it is evidence that naive graph construction can form
non-semantic hubs.

## Required Experiment

Inject repeated generic phrases into otherwise clean memory streams and measure:

1. whether the phrase becomes a top-k hub;
2. whether propagation from that hub creates increased blast radius;
3. whether filtering or typed extraction prevents hub fabrication.
```

- [ ] **Step 2: Update claim triage if present**

If `docs/claim_triage_20260521.md` exists, add:

```markdown
## New Candidate Claim: Topology Poisoning

Repeated generic/template phrases can fabricate artificial graph hubs under
naive entity extraction. This is currently a motivated threat model, not yet a
validated attack, and requires controlled injection experiments.
```

- [ ] **Step 3: Commit**

```bash
git add docs/topology_poisoning_threat_model.md docs/claim_triage_20260521.md
git commit -m "define topology poisoning threat model"
```

---

## Task 2: Artificial Hub Injection Spec

**Files:**
- Create: `docs/artificial_hub_injection_experiment.md`

- [ ] **Step 1: Write experiment spec**

Create `docs/artificial_hub_injection_experiment.md`:

```markdown
# Artificial Hub Injection Experiment

## Goal

Test whether repeated generic phrases can fabricate high-degree hubs and amplify
forgetting/invalidation propagation.

## Dataset

Start with `eventqa_65536` because it already produces clean content hubs and
fast runs. Use one sample for smoke, then three to five samples for the real
experiment.

## Injection Phrases

Use three phrase types:

1. `Project Note`: generic operational phrase.
2. `Current Context`: memory-management-like phrase.
3. `Important Reminder`: plausible user-authored phrase.

## Conditions

1. `clean_control`: original context.
2. `low_injection`: phrase inserted into 5 facts.
3. `medium_injection`: phrase inserted into 20 facts.
4. `high_injection`: phrase inserted into 50 facts.

## Metrics

- injected phrase hub rank;
- injected phrase degree;
- BFS blast radius from injected hub;
- ATTR-AWARE blast radius from injected hub;
- collateral/retrievable loss;
- whether filtering removes the fabricated hub.

## Success Criterion

Topology poisoning is supported if injected phrases enter top-k hubs and produce
higher blast radius than clean controls at matched sample/context size.
```

- [ ] **Step 2: Commit**

```bash
git add docs/artificial_hub_injection_experiment.md
git commit -m "spec artificial hub injection experiment"
```

---

## Task 3: Injection Utility

**Files:**
- Create: `experiments/topology_poisoning.py`
- Create: `tests/test_topology_poisoning.py`

- [ ] **Step 1: Write tests**

Create `tests/test_topology_poisoning.py`:

```python
import unittest

from experiments.topology_poisoning import inject_phrase_into_context


class TopologyPoisoningTests(unittest.TestCase):
    def test_injects_phrase_at_line_boundaries(self):
        context = "Fact one.\nFact two.\nFact three."

        injected = inject_phrase_into_context(
            context=context,
            phrase="Project Note",
            repetitions=2,
        )

        self.assertEqual(injected.count("Project Note"), 2)
        self.assertIn("Project Note: Fact one.", injected)
        self.assertIn("Project Note: Fact two.", injected)

    def test_zero_repetitions_returns_original_context(self):
        context = "Fact one.\nFact two."

        injected = inject_phrase_into_context(
            context=context,
            phrase="Project Note",
            repetitions=0,
        )

        self.assertEqual(injected, context)
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
.venv/bin/python -m unittest tests.test_topology_poisoning -v
```

Expected:

```text
ModuleNotFoundError: No module named 'experiments.topology_poisoning'
```

- [ ] **Step 3: Implement utility**

Create `experiments/topology_poisoning.py`:

```python
from __future__ import annotations


def inject_phrase_into_context(
    context: str,
    phrase: str,
    repetitions: int,
) -> str:
    if repetitions <= 0:
        return context
    lines = context.splitlines()
    injected = []
    remaining = repetitions
    for line in lines:
        if line.strip() and remaining > 0:
            injected.append(f"{phrase}: {line}")
            remaining -= 1
        else:
            injected.append(line)
    while remaining > 0:
        injected.append(f"{phrase}: synthetic reminder {remaining}")
        remaining -= 1
    return "\n".join(injected)
```

- [ ] **Step 4: Run tests**

Run:

```bash
.venv/bin/python -m unittest tests.test_topology_poisoning -v
.venv/bin/python -m py_compile experiments/topology_poisoning.py
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```bash
git add experiments/topology_poisoning.py tests/test_topology_poisoning.py
git commit -m "add topology poisoning injection utility"
```

---

## Task 4: Hub Fabrication Dry-Run Tool

**Files:**
- Modify: `experiments/topology_poisoning.py`
- Create: `docs/experiment_runs/2026-05-21-topology-poisoning-smoke.md`

- [ ] **Step 1: Add CLI skeleton**

Append to `experiments/topology_poisoning.py`:

```python
import argparse
import json
from pathlib import Path

from datasets import load_dataset


def load_context(sub_dataset: str, sample_idx: int) -> str:
    raw = load_dataset("ai-hyz/MemoryAgentBench", split="Accurate_Retrieval", revision="main")
    filtered = [
        sample for sample in raw
        if sample.get("metadata", {}).get("source", "") == sub_dataset
    ]
    return filtered[sample_idx]["context"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sub_dataset", default="eventqa_65536")
    parser.add_argument("--sample_idx", type=int, default=0)
    parser.add_argument("--phrase", required=True)
    parser.add_argument("--repetitions", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    context = load_context(args.sub_dataset, args.sample_idx)
    injected = inject_phrase_into_context(context, args.phrase, args.repetitions)
    args.output.write_text(json.dumps({
        "sub_dataset": args.sub_dataset,
        "sample_idx": args.sample_idx,
        "phrase": args.phrase,
        "repetitions": args.repetitions,
        "original_chars": len(context),
        "injected_chars": len(injected),
        "phrase_count": injected.count(args.phrase),
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run smoke**

Run:

```bash
.venv/bin/python experiments/topology_poisoning.py \
  --sub_dataset eventqa_65536 \
  --sample_idx 0 \
  --phrase "Project Note" \
  --repetitions 20 \
  --output experiments/results/topology_poisoning_smoke_20260521.json
```

Expected:

```text
JSON reports phrase_count=20.
```

- [ ] **Step 3: Write smoke summary**

Create `docs/experiment_runs/2026-05-21-topology-poisoning-smoke.md`:

```markdown
# 2026-05-21 Topology Poisoning Smoke

## Purpose

Verify that repeated generic phrases can be injected into benchmark contexts in
a controlled way before measuring graph hub rank and propagation impact.

## Smoke Result

`Project Note` was injected 20 times into `eventqa_65536` sample 0.

## Next Step

Wire the injected context into the memory benchmark runner and compare hub ranks
against the clean control.
```

- [ ] **Step 4: Commit code/docs only**

Do not commit raw smoke JSON unless explicitly requested.

```bash
git add experiments/topology_poisoning.py docs/experiment_runs/2026-05-21-topology-poisoning-smoke.md
git commit -m "add topology poisoning smoke tool"
```

---

## Task 5: Paper Integration Outline

**Files:**
- Modify: `paper/preprint_outline_20260520.md`

- [ ] **Step 1: Add topology poisoning section**

Append:

```markdown
## Topology Poisoning Extension

The paper should separate two structural risks:

1. Natural content hubs: real entities become high-degree hubs and create large
   propagation blast radius.
2. Fabricated hubs: repeated generic/template phrases become artificial hubs
   under naive extraction, creating a topology-poisoning surface.

LongMemEval template hubs are diagnostic evidence for the second risk, not a
standalone attack result. A controlled injection experiment is required before
claiming attack success.
```

- [ ] **Step 2: Commit**

```bash
git add paper/preprint_outline_20260520.md
git commit -m "outline topology poisoning extension"
```

---

## Task 6: Final Verification and Push

**Files:**
- No new files.

- [ ] **Step 1: Run tests**

Run:

```bash
.venv/bin/python -m unittest tests.test_topology_poisoning -v
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

- The plan does not misuse LongMemEval dry-check artifacts as attack success.
- The plan creates a controlled attack path before adding strong claims.
- The plan keeps content-hub propagation and fabricated-hub poisoning as separate findings.
- The plan includes tests for the injection utility before experiment wiring.
