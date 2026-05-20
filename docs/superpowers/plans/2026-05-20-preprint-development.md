# Graph Memory Forgetting Preprint Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the rejected SCALE workshop submission into a stronger preprint by widening the evidence base, foregrounding practical harm, and clarifying the proactive failure-mode contribution.

**Architecture:** Keep the core thesis unchanged: unfiltered invalidation propagation over co-occurrence memory graphs creates a structural failure mode because co-occurrence is not dependency. Strengthen the paper by adding targeted replications, moving downstream retrieval impact into the main story, measuring ATTR-AWARE false negatives, and reframing nonzero decay as blast radius rather than practical harm.

**Tech Stack:** Python experiment scripts under `experiments/`, MemoryAgentBench-derived data/results under `experiments/results/`, LaTeX paper under `paper/`, review notes under `paper/review_response_notes_20260511.md`, narrative summary under `paper/submission_logic_summary.md`.

---

## Strategic Thesis

The next version should not become a generic attack paper. It should be framed as:

> A proactive systems-safety study for scalable agent memory: when graph-based memory systems add propagation-style consistency maintenance, unfiltered traversal over co-occurrence graphs creates predictable collateral forgetting; lightweight dependency-aware propagation can reduce the blast radius, but must be evaluated for both over-propagation and under-propagation.

This framing aligns with the pattern seen in many strong papers: they identify a plausible failure mode before it becomes standard deployment practice, quantify it, and propose design guidance.

## What the Reviews Taught Us

The reviews did not reject the idea. They rejected the evidence breadth.

Reviewer consensus:

- The problem is novel and timely.
- Co-occurrence vs. dependency is a strong conceptual distinction.
- The paper is readable and scoped honestly.
- ATTR-AWARE is attractive as a lightweight guardrail.
- The empirical evidence is too narrow for broad claims.
- Nonzero decay should not be the practical-harm headline.
- Cross-task contamination is the strongest result and should not live in the appendix.
- ATTR-AWARE false negatives need measurement.

## Target Outcome

The preprint should be strong enough that a reviewer can no longer say:

1. "This is only one benchmark and one pipeline."
2. "Damage is just any nonzero decay."
3. "The strongest retrieval result is too small and hidden."
4. "The defense may miss real dependencies and the paper does not measure that."
5. "BFS is just an obvious strawman."

---

## Files and Responsibilities

- `paper/workshop.tex` or a new `paper/preprint.tex`: revised manuscript.
- `paper/review_response_notes_20260511.md`: source of reviewer objections and response strategy.
- `paper/submission_logic_summary.md`: source of current thesis and experiment roles.
- `experiments/benchmark_accurate_retrieval.py`: likely entry point for expanding cross-task retrieval evaluation.
- `experiments/graph_forgetting.py`: likely entry point for propagation mechanics and graph construction variants.
- `experiments/reviewer_experiments.py` / `experiments/reviewer3_experiments.py`: existing baseline/ablation logic.
- `experiments/results/`: store new JSON outputs with clear date/version names.
- `docs/preprint_experiment_plan.md`: create this as a human-readable experiment tracker before running large jobs.

---

## Phase 1: Paper Reframing Without New Experiments

### Task 1: Reframe the Core Contribution

**Files:**
- Modify: `paper/workshop.tex` or new `paper/preprint.tex`
- Modify: `paper/submission_logic_summary.md`
- Create: `docs/preprint_experiment_plan.md`

- [ ] **Step 1: Write the new one-paragraph thesis**

Use this as the target thesis:

```text
Graph-augmented agent memories increasingly expose the infrastructure needed for propagation-style consistency maintenance, but co-occurrence graphs do not encode dependency. We study unfiltered BFS propagation as a stress test for this plausible design step, not as a claim about current deployment. Across benchmark-derived memory graphs, unfiltered propagation creates a large reachability blast radius, and in hub-triggered settings this structural damage translates into unrelated retrieval degradation. We show that dependency-aware propagation can reduce over-propagation, then evaluate the remaining cost: under-propagation and missed true dependencies.
```

- [ ] **Step 2: Update contribution bullets**

Use this structure:

```text
1. Structural risk characterization: quantify the reachability blast radius of unfiltered propagation over co-occurrence memory graphs.
2. Practical harm measurement: report severe damage, kill rates, and expanded cross-task retrieval degradation separately from nonzero decay.
3. Structural amplification: show how hub-targeted writes can amplify the maintenance mechanism under gray-box/white-box access.
4. Dependency-aware maintenance: evaluate ATTR-AWARE and threshold/typed baselines, including both over-propagation reduction and false-negative cost.
```

- [ ] **Step 3: Create the experiment tracker**

Create `docs/preprint_experiment_plan.md` with this skeleton:

```markdown
# Preprint Experiment Tracker

## Required before preprint

- [ ] Expanded cross-task contamination: more hubs and queries
- [ ] ATTR-AWARE false-negative audit
- [ ] Graph construction replication: filtered/NER/typed variant
- [ ] Practical-harm metric table: nonzero/severe/kill/retrieval

## Optional if time allows

- [ ] Second model or extraction pipeline
- [ ] Mem0/Zep-style schema approximation
- [ ] Synthetic controlled graph stress test
```

- [ ] **Step 4: Commit**

```bash
git add paper/workshop.tex paper/submission_logic_summary.md docs/preprint_experiment_plan.md
git commit -m "plan preprint reframing"
```

---

## Phase 2: Move Cross-task Contamination to the Center

### Task 2: Expand Cross-task Evaluation

**Files:**
- Modify: `experiments/benchmark_accurate_retrieval.py`
- Modify or create: `experiments/cross_task_contamination.py`
- Output: `experiments/results/cross_task_named_hubs_<date>.json`
- Modify: `paper/workshop.tex` or `paper/preprint.tex`

- [ ] **Step 1: Define the target experiment**

Required design:

```text
Dataset: EventQA / Accurate Retrieval split already used in the workshop paper
Hub selection: top named-entity hubs after filtering function words/pronouns
Hub count: target 10-20 hubs, minimum 5 if time-constrained
Queries: target >=300 unrelated retrieval queries, minimum 100 if constrained
Methods: No propagation, BFS, ATTR-AWARE, Weighted BFS theta=0.3
Metrics: F1, EM, affected memory count, severe damage, kill rate
```

- [ ] **Step 2: Add result schema**

Each result JSON should contain:

```json
{
  "experiment": "cross_task_named_hubs",
  "date": "YYYY-MM-DD",
  "hub_filter": "named_entity_no_stopword_pronoun",
  "num_hubs": 10,
  "num_queries": 300,
  "methods": ["no_propagation", "bfs", "attr_aware", "weighted_bfs_0_3"],
  "per_hub": [
    {
      "hub": "United States",
      "degree": 298,
      "affected_memories_bfs": 3381,
      "f1_no_propagation": 70.9,
      "f1_bfs": 59.0,
      "f1_attr_aware": 70.9,
      "f1_weighted_bfs": 69.8
    }
  ],
  "summary": {
    "mean_f1_drop_bfs": -10.8,
    "bootstrap_ci_95": [-13.2, -8.1]
  }
}
```

- [ ] **Step 3: Run a small smoke test**

Run on 2 hubs and 20 queries first.

Expected:

```text
JSON written to experiments/results/
Each method has EM/F1 and damage metrics
No raw function-word/pronoun hubs in per_hub
```

- [ ] **Step 4: Run the full experiment**

Run target setting after smoke test succeeds.

Expected:

```text
At least 5 named-entity hubs
At least 100 unrelated queries
BFS and ATTR-AWARE both reported
```

- [ ] **Step 5: Rewrite main paper result**

Move cross-task contamination from appendix to main results. The new headline should be retrieval-based, not nonzero-decay-based.

Target phrasing:

```text
The strongest practical signal is cross-task retrieval contamination: across N named-entity hubs and M unrelated queries, BFS reduces F1 by X pp on average, while ATTR-AWARE remains within Y pp of the no-propagation baseline.
```

- [ ] **Step 6: Commit**

```bash
git add experiments/benchmark_accurate_retrieval.py experiments/cross_task_contamination.py experiments/results/cross_task_named_hubs_*.json paper/workshop.tex
git commit -m "expand cross-task contamination evaluation"
```

---

## Phase 3: Measure ATTR-AWARE False Negatives

### Task 3: Manual Dependency Audit

**Files:**
- Create: `experiments/false_negative_audit.py`
- Output: `experiments/results/attr_aware_false_negative_audit_<date>.json`
- Create: `docs/attr_aware_labeling_protocol.md`
- Modify: `paper/workshop.tex` or `paper/preprint.tex`

- [ ] **Step 1: Define labeling categories**

Use three labels:

```text
SHOULD_PROPAGATE: the target memory depends on the invalidated fact.
SHOULD_NOT_PROPAGATE: the target memory merely co-occurs or is independent.
BORDERLINE: dependency is plausible but not clear from the stored text.
```

- [ ] **Step 2: Write labeling protocol**

Create `docs/attr_aware_labeling_protocol.md`:

```markdown
# ATTR-AWARE Dependency Labeling Protocol

Label a pair `(invalidated_fact, candidate_memory)`.

Use SHOULD_PROPAGATE when changing the invalidated fact would make the candidate memory stale or unsupported.

Use SHOULD_NOT_PROPAGATE when both facts share an entity but the candidate remains true after the invalidated fact changes.

Use BORDERLINE when the candidate may depend on the invalidated fact but the dependency requires unstated assumptions.

Report:
- false negative: SHOULD_PROPAGATE but ATTR-AWARE does not propagate
- false positive: SHOULD_NOT_PROPAGATE but ATTR-AWARE propagates
- borderline separately, not folded into either rate
```

- [ ] **Step 3: Sample candidate pairs**

Sample:

```text
50 pairs reached by BFS but not ATTR-AWARE
50 pairs reached by ATTR-AWARE
50 random co-occurring pairs
```

- [ ] **Step 4: Label manually**

Store labels in JSON:

```json
{
  "invalidated_fact": "the CEO of Acme is Alice",
  "candidate_memory": "Alice approves Acme milestones",
  "bfs_reaches": true,
  "attr_aware_reaches": true,
  "label": "SHOULD_PROPAGATE",
  "rationale": "Alice's approval role depends on her CEO status."
}
```

- [ ] **Step 5: Compute rates**

Report:

```text
ATTR-AWARE false negative rate among SHOULD_PROPAGATE pairs
ATTR-AWARE false positive rate among SHOULD_NOT_PROPAGATE pairs
Borderline fraction
```

- [ ] **Step 6: Add paper paragraph**

Target phrasing:

```text
ATTR-AWARE trades over-propagation for possible under-propagation. In a manual audit of N labeled dependency pairs, it missed X% of SHOULD_PROPAGATE pairs while reducing false positives from Y% to Z%. This confirms that ATTR-AWARE is a lightweight guardrail rather than a complete dependency reasoner.
```

- [ ] **Step 7: Commit**

```bash
git add experiments/false_negative_audit.py experiments/results/attr_aware_false_negative_audit_*.json docs/attr_aware_labeling_protocol.md paper/workshop.tex
git commit -m "measure attr-aware false negatives"
```

---

## Phase 4: Add Graph Construction Replication

### Task 4: NER/Filtered/Typed Graph Variants

**Files:**
- Modify: `experiments/graph_forgetting.py`
- Modify or create: `experiments/graph_construction_variants.py`
- Output: `experiments/results/graph_construction_variants_<date>.json`
- Modify: `paper/workshop.tex` or `paper/preprint.tex`

- [ ] **Step 1: Define graph variants**

Minimum variants:

```text
raw_rule_based: current extraction
stopword_pronoun_filtered: remove function words and pronouns from entity nodes
typed_relation_only: subject -> object edges, no co-occurrence cliques
```

Optional:

```text
ner_normalized: normalize named entities if an NER pipeline is available
mem0_zep_approx: approximate a production-style schema from available fact metadata
```

- [ ] **Step 2: Run same propagation metrics**

For each variant report:

```text
nodes
edges
top hubs
BFS nonzero damage
BFS severe damage
BFS kill rate
ATTR-AWARE damage
cross-task F1 drop if available
```

- [ ] **Step 3: Add result table**

Target table:

```text
Graph Variant | Nodes | Edges | Top hubs content? | BFS Damage | Kill | Attr Damage
Raw rule-based | ... | ... | mixed/content | ... | ... | ...
Stopword/pronoun filtered | ... | ... | content | ... | ... | ...
Typed relation only | ... | ... | content | ... | ... | ...
```

- [ ] **Step 4: Interpret conservatively**

Target phrasing:

```text
The absolute damage rate varies with graph construction, but the qualitative pattern remains: unfiltered propagation creates a much larger blast radius than dependency-aware filtering. This supports the structural nature of the failure mode while avoiding a claim of graph-construction invariance.
```

- [ ] **Step 5: Commit**

```bash
git add experiments/graph_forgetting.py experiments/graph_construction_variants.py experiments/results/graph_construction_variants_*.json paper/workshop.tex
git commit -m "replicate propagation across graph construction variants"
```

---

## Phase 5: Metric Reframing

### Task 5: Rewrite Result Tables Around Practical Harm

**Files:**
- Modify: `paper/workshop.tex` or `paper/preprint.tex`
- Modify: `paper/submission_logic_summary.md`

- [ ] **Step 1: Rename nonzero damage in text**

Use:

```text
nonzero decay / reachability blast radius
```

Avoid:

```text
damage
```

when referring only to `w < 1.0`.

- [ ] **Step 2: Create a practical harm summary table**

Target columns:

```text
Setting | Nonzero decay | Severe | Kill | Retrieval F1 drop | Interpretation
```

- [ ] **Step 3: Rewrite abstract headline**

Target structure:

```text
Unfiltered BFS reaches 69--79% of valid memories, but practical harm depends on severity: hub-triggered settings produce X% kill-level decay and Y pp unrelated retrieval degradation.
```

- [ ] **Step 4: Update conclusion**

Target structure:

```text
Nonzero decay is best interpreted as blast radius. Severe/kill rates and cross-task degradation measure practical harm. Across both views, dependency-aware propagation substantially reduces risk.
```

- [ ] **Step 5: Commit**

```bash
git add paper/workshop.tex paper/submission_logic_summary.md
git commit -m "reframe metrics around practical harm"
```

---

## Phase 6: Decide Preprint Timing

### Task 6: Preprint Readiness Gate

**Files:**
- Create: `docs/preprint_readiness_checklist.md`

- [ ] **Step 1: Create checklist**

Use:

```markdown
# Preprint Readiness Checklist

- [ ] Expanded cross-task contamination has at least 5 named hubs and 100 unrelated queries.
- [ ] ATTR-AWARE false-negative audit exists and is discussed.
- [ ] At least one graph-construction replication exists.
- [ ] Nonzero decay is framed as blast radius, not direct corruption.
- [ ] Severe/kill/retrieval metrics are summarized in main text.
- [ ] BFS is framed as stress test, not deployed baseline.
- [ ] Limitations explicitly mention remaining single-benchmark/single-model scope if not solved.
- [ ] Abstract and conclusion do not overclaim production generality.
```

- [ ] **Step 2: Decide route**

Use this rule:

```text
If only text polishing is done: do not preprint yet.
If cross-task expansion + false-negative audit are done: preprint is reasonable.
If graph-construction replication is also done: preprint is strong.
```

- [ ] **Step 3: Commit**

```bash
git add docs/preprint_readiness_checklist.md
git commit -m "add preprint readiness checklist"
```

---

## Recommended Execution Order

1. Phase 1: Reframe thesis and create tracker.
2. Phase 2: Expand cross-task contamination.
3. Phase 3: Measure ATTR-AWARE false negatives.
4. Phase 5: Reframe metrics around practical harm.
5. Phase 4: Add graph construction variants.
6. Phase 6: Run readiness gate.

Phase 2 and Phase 3 are the highest-impact upgrades. If time is limited, do those before adding a second LLM.

## Self-review

Spec coverage:

- Addresses proactive failure-mode framing.
- Addresses reviewer concern about narrow evaluation.
- Addresses practical harm vs nonzero decay.
- Addresses cross-task contamination being too small/hidden.
- Addresses ATTR-AWARE false negatives.
- Avoids unnecessary title/story rewrite.

Placeholder scan:

- The plan uses concrete target files, schemas, metrics, and commands.
- No experiment is left as "TBD"; optional items are explicitly marked optional.

Risk:

- Some file names may need adjustment after inspecting current scripts.
- Manual labeling requires disciplined protocol; otherwise it can create a new reviewer attack surface.

---

# Higher-Venue Development Program

The preprint plan above is sufficient for a stronger public version. A higher-venue version needs a more fundamental contribution: not just "BFS is bad," but a general evaluation framework for safe propagation in agent memory graphs.

## Fundamental Claim Hierarchy

The next manuscript should make four claims, in this order. Each claim needs its own evidence.

1. **Structural blast radius:** In co-occurrence memory graphs, unfiltered propagation has a predictable reachability problem driven by hubness, depth, and heavy-tailed entity frequency.
2. **Practical harm separation:** Reachability blast radius is not the same as user-visible harm; practical harm must be measured through severe decay, kill-level decay, and retrieval degradation.
3. **Over-propagation vs under-propagation tradeoff:** Dependency-aware propagation reduces collateral invalidation but can miss true dependencies, so it must be evaluated with both false-positive and false-negative metrics.
4. **Safe maintenance desiderata:** A memory propagation policy should be judged by a safety frontier: minimize unrelated decay while preserving necessary dependency closure under realistic graph construction noise.

The paper should not claim that ATTR-AWARE solves dependency reasoning. It should claim that ATTR-AWARE is a simple point on the safety frontier that exposes the right evaluation problem.

## Research Questions for a Main-Conference Version

- [ ] **RQ1: How large is the structural blast radius of propagation over co-occurrence memory graphs, and what graph properties predict it?**
- [ ] **RQ2: When does structural blast radius become practical harm in retrieval and task performance?**
- [ ] **RQ3: How sensitive are the findings to graph construction pipeline, entity normalization, relation typing, and LLM extractor?**
- [ ] **RQ4: What is the precision/recall tradeoff of dependency-aware propagation policies?**
- [ ] **RQ5: Can synthetic graphs with known dependencies reproduce the same failure mode and explain when it disappears?**
- [ ] **RQ6: Do realistic memory-architecture approximations, such as provenance closure or typed-edge invalidation, avoid the failure without giving up maintenance utility?**

## Experimental Pillars

### Pillar 1: Multi-pipeline Graph Replication

Purpose: remove the "one rule-based pipeline" objection.

- [ ] Run `raw_rule_based`, `stopword_pronoun_filtered`, `ner_normalized`, `typed_relation_only`, and `mem0_zep_schema_approx` graph variants.
- [ ] For every graph variant, report node count, edge count, degree distribution, top hubs, nonzero blast radius, severe decay, kill rate, and ATTR-AWARE reduction.
- [ ] Keep the conclusion conservative: absolute rates vary by construction, but unsafe co-occurrence traversal remains systematically larger than dependency-aware alternatives if the pattern holds.

Minimum acceptance standard:

```text
At least three graph construction pipelines show the same qualitative ranking:
BFS blast radius > weighted/threshold baselines > dependency-aware or typed/provenance-aware propagation.
```

### Pillar 2: Multi-model / Multi-extractor Replication

Purpose: remove the "single LLM / Gemma-only" objection.

- [ ] Separate two factors: answer-generation LLM and memory-graph extraction pipeline.
- [ ] Use the current Gemma setup as the baseline condition.
- [ ] Add at least two extraction conditions, ideally one local and one API-based if budget permits.
- [ ] Candidate local models: Qwen, Llama, Gemma family variant.
- [ ] Candidate API models: GPT or Claude, if available and cost is acceptable.
- [ ] Log exact model IDs, dates, prompts, decoding parameters, extraction schema, and cost.

Do not let external LLMs become unlabeled oracles. If LLMs are used to verify dependency labels, audit a sample manually and report disagreement.

### Pillar 3: Cross-task Retrieval at Scale

Purpose: turn the strongest practical-harm result into a main result.

- [ ] Evaluate 10-20 named-entity hubs, not raw hubs.
- [ ] Use at least 300 unrelated retrieval queries if feasible.
- [ ] Report per-hub results, mean drop, median drop, bootstrap confidence intervals, and worst-case drop.
- [ ] Compare No Propagation, BFS, Weighted BFS, thresholded propagation, ATTR-AWARE, and any realistic baseline available.
- [ ] Move this result to the main paper, not appendix.

Minimum acceptance standard:

```text
The paper should be able to state:
"Across N named-entity hubs and M unrelated queries, unfiltered propagation causes X pp F1 degradation, while dependency-aware propagation remains within Y pp of no-propagation."
```

### Pillar 4: False-negative / Under-propagation Audit

Purpose: answer the strongest criticism of ATTR-AWARE.

- [ ] Build a labeled set of candidate dependency pairs.
- [ ] Include pairs reached by BFS only, reached by ATTR-AWARE, and random co-occurring controls.
- [ ] Label `SHOULD_PROPAGATE`, `SHOULD_NOT_PROPAGATE`, and `BORDERLINE`.
- [ ] Compute false-positive and false-negative rates for every propagation policy.
- [ ] If possible, do a second blind labeling pass or second annotator pass.

The goal is not to make ATTR-AWARE look perfect. The goal is to show the tradeoff clearly enough that the paper becomes a benchmark/evaluation contribution, not only a defense proposal.

### Pillar 5: Synthetic Controllable Benchmark

Purpose: make the result fundamental rather than benchmark-specific.

- [ ] Generate synthetic memory graphs with known true dependencies and noisy co-occurrence edges.
- [ ] Vary degree distribution: uniform, power-law, hub-injected, community-structured.
- [ ] Vary dependency sparsity: dense dependency chains vs sparse true dependencies.
- [ ] Vary propagation depth and decay.
- [ ] Measure over-propagation, under-propagation, severe decay, and retrieval-proxy loss.

The synthetic benchmark should answer:

```text
When does co-occurrence propagation fail?
When is BFS actually acceptable?
Which graph statistics predict risk before deployment?
```

This is the fastest path to a fundamental paper because it lets the manuscript make conditional claims instead of anecdotal empirical claims.

### Pillar 6: Realistic Memory Architecture Emulation

Purpose: remove the "BFS strawman" objection.

- [ ] Add baselines that a systems reviewer would consider realistic:
  - retrieval-only invalidation
  - provenance-based closure
  - typed-edge propagation
  - semantic-similarity threshold
  - LLM verifier before propagation
  - degree-capped propagation
- [ ] Map each baseline to an existing design pattern in graph memory systems, without claiming current deployed systems use naive BFS.
- [ ] Report runtime and LLM-call cost, because scalable memory maintenance is a systems question.

Target contribution:

```text
Not "BFS is bad."
Instead: "safe memory maintenance requires an explicit propagation policy; here is how common policy families trade off blast radius, missed dependencies, retrieval harm, and runtime cost."
```

### Pillar 7: Analytical Framing

Purpose: make the work conceptually durable.

- [ ] Define reachability blast radius:

```text
B_D(v) = |{u : dist_G(v,u) <= D and u is valid}| / |V_valid|
```

- [ ] Define weighted blast radius under decay threshold `tau`.
- [ ] Define over-propagation and under-propagation relative to a hidden dependency graph `G_dep`.
- [ ] State the core mismatch:

```text
G_cooccur is observable and cheap, but G_dep is the graph needed for correct invalidation.
```

- [ ] Derive or empirically test a simple prediction: high-degree nodes and low-diameter components dominate propagation risk.
- [ ] Use theory as a lens, not as overclaiming. A small proposition plus empirical validation is enough.

## External LLM and CSP Usage Plan

External LLMs and cloud compute can help, but they should be used as controlled experimental conditions.

- [ ] Use external LLMs for extraction, dependency labeling assistance, and LLM-verifier baselines.
- [ ] Keep every model condition reproducible: model ID, provider, date, prompt, decoding parameters, schema, retry logic, and cost.
- [ ] Do not store API keys, private credentials, or provider tokens in the repo.
- [ ] Use CSPs for batch extraction/evaluation only after the local smoke test passes.
- [ ] Write configs first, then run jobs. Avoid ad hoc notebook-only runs.
- [ ] Store raw outputs under `experiments/results/raw/` and summarized tables under `experiments/results/processed/`.

Recommended grid:

```text
Graph extraction:
- current rule-based extractor
- filtered/normalized rule-based extractor
- local LLM extractor
- API LLM extractor, if budget permits

Propagation policies:
- no propagation
- unfiltered BFS
- degree-capped BFS
- weighted BFS / thresholded propagation
- typed-edge propagation
- provenance closure
- ATTR-AWARE
- LLM verifier, if budget permits
```

## Readiness Tiers

Use these gates to decide when to release or submit.

### Tier 1: Minimum Preprint

- [ ] Expanded named-entity cross-task contamination.
- [ ] ATTR-AWARE false-negative audit.
- [ ] Nonzero decay reframed as blast radius.
- [ ] Reviewer-response limitations clearly incorporated.

This is enough for a credible arXiv preprint if the results hold.

### Tier 2: Strong Preprint / Workshop Resubmission

- [ ] Tier 1 complete.
- [ ] At least three graph construction variants.
- [ ] Practical-harm table in main text.
- [ ] Realistic baselines beyond BFS and ATTR-AWARE.

This is the target for a stronger workshop or short-paper venue.

### Tier 3: Main-conference Candidate

- [ ] Tier 2 complete.
- [ ] Multi-model or multi-extractor replication.
- [ ] Synthetic controllable benchmark with known dependencies.
- [ ] Cross-task retrieval evaluation at meaningful scale.
- [ ] Runtime/cost analysis for propagation policies.

This is the minimum bar for aiming at a strong ML/systems/agents venue.

### Tier 4: Strong Main-conference Candidate

- [ ] Tier 3 complete.
- [ ] Analytical model predicts risk from graph statistics.
- [ ] Realistic memory architecture emulation is convincing.
- [ ] Dependency labeling has either multiple annotators or a carefully audited protocol.
- [ ] The paper presents a reusable benchmark/evaluation harness, not only one set of results.

This is the version that can survive the "obvious BFS strawman" and "single benchmark" critiques.

## Timeline

### Week 1: Foundation Repair

- [ ] Create `docs/preprint_experiment_plan.md`.
- [ ] Move cross-task contamination design into the main narrative.
- [ ] Implement false-negative audit protocol.
- [ ] Run local smoke tests for expanded cross-task evaluation.

### Week 2: Evidence Expansion

- [ ] Run expanded cross-task retrieval.
- [ ] Complete first manual dependency audit.
- [ ] Add graph construction variants.
- [ ] Produce practical-harm summary table.

### Weeks 3-4: Generalization

- [ ] Add at least one additional extractor or LLM condition.
- [ ] Add realistic propagation baselines.
- [ ] Run multi-pipeline replication.
- [ ] Rewrite the paper around the claim hierarchy.

### Weeks 5-8: Higher-venue Push

- [ ] Build synthetic controllable benchmark.
- [ ] Add analytical framing and graph-statistic predictors.
- [ ] Run final cross-condition experiments.
- [ ] Package code and reproducibility artifacts.
- [ ] Decide target venue and submission format.

## Candidate Titles

Use a title that foregrounds memory maintenance, not only attack.

- `Co-occurrence Is Not Dependency: Structural Failure Modes in Graph-Based Agent Memory Maintenance`
- `Safe Propagation for Agent Memory: Measuring and Mitigating Collateral Forgetting in Co-occurrence Graphs`
- `Collateral Forgetting in Graph-Based Agent Memory`
- `When Memory Graphs Forget Too Much: Propagation Safety for Long-Term Agent Memory`

## Stop Conditions

Do not rush to preprint if any of these remain true:

- [ ] Practical harm is still supported only by the small original cross-task experiment.
- [ ] ATTR-AWARE has no false-negative measurement.
- [ ] All results depend on one raw rule-based graph pipeline.
- [ ] The manuscript still treats nonzero decay as equivalent to user-visible corruption.
- [ ] The paper sells ATTR-AWARE as a complete dependency reasoner rather than a lightweight guardrail.

Do preprint if:

- [ ] The expanded cross-task result holds.
- [ ] The false-negative audit gives an honest tradeoff.
- [ ] At least one graph-construction replication supports the structural claim.
- [ ] The framing is "safe propagation policy evaluation," not "current systems are broken."
