# Controlled Synthetic Memory Graph Benchmark

Date: 2026-05-21

## Purpose

This benchmark tests the core mechanism independently of benchmark-specific
entity extraction artifacts:

> Co-occurrence is proximity, not dependency. Propagation over co-occurrence
> graphs can create false-positive invalidation when co-occurrence diverges from
> true memory dependency.

Synthetic results are a mechanism proof, not a replacement for real benchmark
evidence. EventQA remains the real-data stress test; LongMemEval remains a graph
construction failure case under the current extractor.

## Synthetic World

Each generated world contains:

- entities: named objects `E000`, `E001`, ...
- memories: fact nodes with one subject entity and one object entity;
- true dependency graph: directed fact-to-fact edges that represent which
  memories should be invalidated when a trigger memory changes;
- co-occurrence graph: undirected fact-to-fact edges induced by entity
  co-occurrence or injected noisy/hub connections.

The benchmark intentionally separates true dependency edges from co-occurrence
edges. This lets us measure false-positive and false-negative propagation
directly.

## Graph Variants

1. `clean`: co-occurrence edges mostly align with true dependency chains.
2. `noisy`: additional random co-occurrence edges connect unrelated memories.
3. `hub_heavy`: a generic hub entity connects many otherwise unrelated memories.

## Algorithms

1. `oracle_dependency`: propagate only over true dependency edges.
2. `bfs_cooccurrence`: unfiltered BFS over the co-occurrence graph.
3. `degree_capped_bfs`: BFS over co-occurrence but refuses expansion through
   nodes above a degree cap.
4. `weighted_bfs`: BFS over co-occurrence with high-degree penalties.
5. `attr_like`: propagates over co-occurrence only when the next memory shares
   the trigger subject or matches a true dependency edge. This is not intended
   as a perfect model of ATTR-AWARE; it is a controlled heuristic for measuring
   the precision/recall tradeoff.

## Metrics

For each trigger memory:

- true positives: propagated memories that are true dependencies;
- false positives: propagated memories that are not true dependencies;
- false negatives: true dependencies missed by the algorithm;
- precision, recall, F1;
- blast radius: number of propagated memories excluding the trigger;
- false-positive rate over non-dependent memories.

Aggregate reports average metrics across trigger memories.

## Success Criteria

The mechanism is supported if:

1. `bfs_cooccurrence` false positives and blast radius increase from `clean` to
   `noisy` to `hub_heavy`.
2. `oracle_dependency` has perfect precision and recall by construction.
3. `degree_capped_bfs`, `weighted_bfs`, or `attr_like` reduce false positives
   relative to BFS.
4. At least one non-oracle guardrail exposes a recall cost, quantifying the
   under-propagation concern reviewers raised.

## Failure Criteria

If BFS does not produce higher false-positive propagation under noisy or
hub-heavy co-occurrence graphs, the revised paper should not claim a structural
mechanism. It should instead be written as an EventQA-specific engineering
postmortem.
