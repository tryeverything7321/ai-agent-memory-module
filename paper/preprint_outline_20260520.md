# Preprint Outline

## Title Direction

Structural Safety Risks in Graph-Based Agent Memory Maintenance

## Abstract Shape

1. Graph-augmented memory systems invite propagation-style maintenance.
2. Co-occurrence graphs do not encode dependency.
3. Controlled synthetic graphs show that BFS is safe only when co-occurrence
   aligns with dependency; noisy and hub-heavy co-occurrence creates high
   false-positive invalidation.
4. EventQA named-entity hubs show large real-data structural blast radius.
5. Retrieval accuracy can move up or down, showing accuracy alone is insufficient.
6. LongMemEval and artificial hub injection show that graph construction itself
   can become a memory-maintenance risk surface.
7. Dependency-aware guardrails reduce collateral structural damage but introduce
   measurable missed-dependency tradeoffs.

## Main Findings

Finding 1: In controlled graphs, co-occurrence BFS has perfect behavior when
co-occurrence and dependency align, but high false-positive invalidation when
noise or generic hubs decouple topology from dependency.

Finding 2: EventQA named-entity hubs create large real-data structural blast
radius under unfiltered propagation.

Finding 3: Retrieval effects are unstable, not monotonically harmful.

Finding 4: Artificial generic phrases can create triggerable topology-poisoning
surfaces; high repetition can enter raw top-hub diagnostics.

Finding 5: LongMemEval fails the clean graph gate under the current extractor,
showing that graph construction artifacts are part of the safety problem.

Finding 6: Guardrails reduce false positives but must be evaluated for
under-propagation.

## Main Tables

1. Controlled synthetic precision/recall table.
2. EventQA practical-harm summary table.
3. Artificial hub injection dose-response table.
4. Clean graph gate / LongMemEval diagnostic table.
5. ATTR-AWARE audit table.

## Narrative Change From Workshop Version

The workshop version was centered on collateral forgetting and cross-task
retrieval degradation. The revised version should be centered on memory
maintenance safety: unfiltered propagation can make broad structural changes,
and retrieval metrics can either expose or hide those changes.

## Evidence Still Needed

1. Larger controlled synthetic sweep across graph size, noise, and hub strength.
2. Graph construction variant results.
3. Balanced ATTR-AWARE audit with both blocked and accepted propagation examples.
4. Full-context EventQA run scheduled as a long job, not an interactive
   foreground run.
5. A clean non-EventQA replication only after graph construction passes a clean
   hub gate.

## Controlled Mechanism Section

This should be the first empirical section in the preprint.

Claim:

> Co-occurrence propagation fails when topology diverges from dependency.

Evidence:

- clean synthetic graph: BFS matches oracle dependency propagation;
- noisy graph: BFS keeps recall but introduces high false-positive invalidation;
- hub-heavy graph: false-positive blast radius increases further;
- guardrails reduce false positives but expose missed-dependency costs.

This answers reviewer concerns about artifacts and ATTR-AWARE false negatives
without pretending synthetic results are deployment evidence.

## Real-Data Stress Section

EventQA should be framed as real-data stress testing:

- named-entity hubs avoid raw `And`/`She`/`But` artifact claims;
- structural blast radius is the headline;
- retrieval F1 is a secondary and unstable downstream signal.

## Negative Transfer Section

LongMemEval should not be used as successful replication under the current
extractor. It should be presented as a clean graph gate failure:

- raw template hubs dominate;
- expanded stoplists remove many artifacts but often leave no actionable content
  hub;
- therefore graph construction is itself a safety-critical component.

## Topology Poisoning Extension

The paper should separate two structural risks:

1. Natural content hubs: real entities become high-degree hubs and create large
   propagation blast radius.
2. Fabricated hubs: repeated generic/template phrases become artificial hubs
   under naive extraction, creating a topology-poisoning surface.

LongMemEval template hubs are diagnostic evidence for the second risk, not a
standalone attack result. A controlled injection experiment is required before
claiming attack success.
