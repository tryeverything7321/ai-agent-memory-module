# Preprint Experiment Tracker

This tracker turns the SCALE reviews into executable experiment work. The goal is to make the next version defensible as a study of safe propagation policies for graph-based agent memory, not only a critique of naive BFS.

## Current Thesis

The current invariant is structural blast radius, not retrieval degradation.
Future experiments should test whether the blast-radius gap between BFS and
guarded propagation survives across dataset families and graph construction
variants.

## Required Before Preprint

- [x] Initial expanded cross-task contamination over named-entity hubs: 5 samples, 5 hubs/sample, 100 queries/sample.
- [x] Larger-context named-hub replication: EventQA 131K, 5 samples, 5 hubs/sample, 100 queries/sample.
- [ ] Cross-family contamination replication on a clean non-EventQA source.
- [x] Cross-family dry check: LongMemEval currently dominated by chat-template hubs; EventQA full is clean but same-family.
- [~] ATTR-AWARE false-negative audit candidate set: balanced 50/50 candidate
  file generated; manual labels still needed.
- [ ] Graph construction variants: raw, stopword/pronoun filtered, typed relation, and NER-normalized if available.
- [ ] Practical-harm summary table separating blast radius from severe decay, kill-level decay, and retrieval F1 drop.

## Experiment Standards

- Every run must write a manifest with config, git commit, timestamp, command, model IDs, dataset split, graph mode, propagation policies, and output files.
- Raw function-word and pronoun hubs must not be used for headline cross-task claims.
- Nonzero weight decay must be reported as `blast_radius`, not direct corruption.
- ATTR-AWARE must be reported with both over-propagation reduction and missed-dependency risk.
- External LLM or CSP runs must record model ID, provider, prompt version, date, cost estimate, and decoding parameters.

## Experiment 1: Expanded Cross-task Contamination

Target:

- Dataset: `MemoryAgentBench / Accurate_Retrieval / eventqa_65536`
- Hubs: top 10 named-entity hubs if feasible, minimum 5
- Queries: 300 unrelated retrieval queries if feasible, minimum 100
- Policies: `no_propagation`, `bfs`, `weighted_bfs_0_3`, `attr_aware`
- Metrics: EM, F1, nonzero blast radius, severe decay, kill-level decay, affected memories

Success criterion:

```text
The main paper can report cross-task retrieval degradation over named-entity hubs, with per-hub results and bootstrap confidence intervals.
```

## Experiment 2: ATTR-AWARE False-negative Audit

Target samples:

- 50 BFS-reached but ATTR-AWARE-blocked pairs
- 50 ATTR-AWARE-reached pairs
- 50 random co-occurring pairs

Labels:

- `SHOULD_PROPAGATE`
- `SHOULD_NOT_PROPAGATE`
- `BORDERLINE`

Success criterion:

```text
The paper can report false-positive and false-negative rates for each propagation policy instead of presenting ATTR-AWARE as cost-free.
```

## Experiment 3: Graph Construction Variants

Variants:

- `raw_rule_based`
- `stopword_pronoun_filtered`
- `typed_relation_only`
- `ner_normalized` if the dependency is available
- `mem0_zep_schema_approx` if enough schema information can be reconstructed

Metrics:

- node count
- edge count
- top hubs
- BFS blast radius
- BFS severe decay
- BFS kill rate
- ATTR-AWARE blast radius
- cross-task F1 drop if available

Success criterion:

```text
The qualitative ordering remains stable across at least three graph construction variants.
```

## Experiment 4: Practical-harm Summary

Create a single table for the paper:

```text
Setting | Policy | Blast radius | Severe decay | Kill rate | Retrieval F1 drop | Interpretation
```

Success criterion:

```text
The paper no longer relies on "any nonzero decay" as the practical-harm headline.
```

## Execution Order

1. Build config and manifest tooling.
2. Run local dry-run to verify config/manifest generation.
3. Add expanded cross-task runner.
4. Run a 2-hub / 20-query smoke test.
5. Run the full cross-task experiment.
6. Add false-negative audit sampler. `[done: balanced sampler committed]`
7. Label the audit set.
8. Add graph construction variants.
9. Rewrite the paper around the new evidence.
