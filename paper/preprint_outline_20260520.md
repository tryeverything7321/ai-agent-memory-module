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

Finding 3: Raw LLM answer F1 is an unstable downstream signal, but
decay-weighted support retrieval shows a cleaner harm channel: BFS can push
answer-support memories out of top-k retrieval while ATTR-AWARE largely
preserves them.

Finding 4: Artificial generic phrases can create triggerable topology-poisoning
surfaces; high repetition can enter raw top-hub diagnostics.

Finding 5: LongMemEval fails the clean graph gate under the current extractor,
but structured turn-level construction recovers content hubs and reproduces the
structural collateral pattern.

Finding 6: Guardrails reduce false positives but must be evaluated for
under-propagation.

Latest audit-set status:

- EventQA 64K trace-enabled run now yields a balanced dependency-labeling set;
- 50 `bfs_reached_attr_blocked` candidates measure possible ATTR-AWARE false
  negatives;
- 50 `attr_reached` controls measure accepted-propagation precision;
- the set is stratified across sample/hub groups, not filled from one hub;
- no false-negative rate should be claimed until manual labels are completed.

## Main Tables

1. Controlled synthetic precision/recall table.
2. EventQA practical-harm summary table.
3. Artificial hub injection dose-response table.
4. LongMemEval raw-vs-structured graph gate table.
5. LongMemEval structured propagation table.
6. ATTR-AWARE audit table.

## Narrative Change From Workshop Version

The workshop version was centered on collateral forgetting and cross-task
retrieval degradation. The revised version should be centered on memory
maintenance safety: unfiltered propagation can make broad structural changes,
and retrieval metrics can either expose or hide those changes.

## Evidence Still Needed

1. Larger controlled synthetic sweep across graph size, noise, and hub strength.
2. Graph construction variant results.
3. Manual labels for the balanced ATTR-AWARE audit set.  The sampler now
   produces 50 blocked candidates and 50 accepted-propagation controls, but the
   paper still needs `SHOULD_PROPAGATE` / `SHOULD_NOT_PROPAGATE` labels before
   reporting a false-negative rate.
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

Latest sweep:

- 540 synthetic worlds across 30/100/300 entities, three noise levels, three hub
  strengths, and 20 seeds;
- clean graphs: BFS FP = 0 and blast radius = 2 across sizes;
- high-noise/no-hub graphs: BFS FP rises to 33.09, 49.65, and 54.29 for
  30/100/300 entities;
- high-noise/high-hub graphs: BFS FP rises further to 49.69, 70.66, and 76.64;
- ATTR-like filtering keeps FP below 1 in all reported cells but recall stays
  around 0.5-0.66, making the under-propagation tradeoff explicit.

This answers reviewer concerns about artifacts and ATTR-AWARE false negatives
without pretending synthetic results are deployment evidence.

## Real-Data Stress Section

EventQA should be framed as real-data stress testing:

- named-entity hubs avoid raw `And`/`She`/`But` artifact claims;
- structural blast radius is the headline;
- retrieval F1 is a secondary and unstable downstream signal.

## Negative Transfer Section

LongMemEval should not be used as successful replication under raw serialized
context construction. It should be presented as a graph construction diagnostic:

- raw template hubs dominate;
- expanded stoplists remove many artifacts but can leave too few actionable
  content hubs under raw context;
- structured metadata modes recover content hubs: user-turn and
  answer-session-user graph construction pass a first clean hub gate on 5/5
  samples;
- therefore graph construction is itself a safety-critical component, not just a
  preprocessing detail.

Next paper decision: LongMemEval propagation experiments should use
`answer_session_user_turns`, not raw context.

Latest structured propagation result:

- 4/5 LongMemEval samples produced actionable content hubs under
  `answer_session_user_turns`;
- BFS mean collateral across successful samples: 59.3 memories;
- ATTR-AWARE mean collateral across successful samples: 1.25 memories;
- this structural result used disabled queries and mock embeddings.

Latest support-retrieval result:

- metric: decay-weighted vector support hit@K, not LLM generation F1;
- 5 LongMemEval samples, first 20 queries per sample, top-2 named/actionable
  hubs per successful sample;
- 4/5 samples produced actionable hubs, yielding 8 hub runs;
- support hit@5: baseline 26.25%, BFS 16.25% (-10.0pp), ATTR-AWARE 26.25%
  (+0.0pp);
- support hit@20: baseline 32.50%, BFS 20.00% (-12.5pp), ATTR-AWARE 31.88%
  (-0.62pp).

This replaces the weaker LongMemEval raw LLM-F1 story.  The paper should say
that answer-generation quality remains a separate evaluation problem, while
propagation has a measurable retrieval-ranking effect once support evidence is
used as the target.

## Topology Poisoning Extension

The paper should separate two structural risks:

1. Natural content hubs: real entities become high-degree hubs and create large
   propagation blast radius.
2. Fabricated hubs: repeated generic/template phrases become artificial hubs
   under naive extraction, creating a topology-poisoning surface.

LongMemEval template hubs are diagnostic evidence for the second risk, not a
standalone attack result. A controlled injection experiment is required before
claiming attack success.
