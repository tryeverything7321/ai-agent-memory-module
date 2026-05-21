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
2. Cross-family or larger-scale replication table.
3. Graph construction variant table.
4. ATTR-AWARE audit table.

## Narrative Change From Workshop Version

The workshop version was centered on collateral forgetting and cross-task
retrieval degradation. The revised version should be centered on memory
maintenance safety: unfiltered propagation can make broad structural changes,
and retrieval metrics can either expose or hide those changes.

## Evidence Still Needed

1. A clean non-EventQA replication or a controlled synthetic benchmark.
2. Graph construction variant results.
3. Balanced ATTR-AWARE audit with both blocked and accepted propagation examples.
4. Full-context run scheduled as a long job, not an interactive foreground run.

## Topology Poisoning Extension

The paper should separate two structural risks:

1. Natural content hubs: real entities become high-degree hubs and create large
   propagation blast radius.
2. Fabricated hubs: repeated generic/template phrases become artificial hubs
   under naive extraction, creating a topology-poisoning surface.

LongMemEval template hubs are diagnostic evidence for the second risk, not a
standalone attack result. A controlled injection experiment is required before
claiming attack success.
