# Preprint Next Tasks

Date: 2026-05-22

## Current Position

The paper should no longer be framed as "BFS forgetting damages memory" alone.
The stronger revised thesis is:

> Propagation-style memory maintenance is unsafe when co-occurrence topology is
> used as a proxy for dependency.  Controlled graphs isolate the mechanism,
> EventQA and LongMemEval show real-data stress, and topology artifacts show
> graph construction itself is a safety-critical component.

## Priority 1: Finish ATTR-AWARE Under-Propagation Audit

Status: candidate generation done, manual labels needed.

Inputs:

- `experiments/results/attr_audit_balanced_candidates_20260522.json`
- `docs/attr_aware_labeling_protocol.md`

Needed output:

- labeled JSON/CSV with `SHOULD_PROPAGATE`, `SHOULD_NOT_PROPAGATE`,
  `BORDERLINE`;
- false-negative rate for `bfs_reached_attr_blocked`;
- accepted-propagation precision for `attr_reached`.

Why it matters:

This directly answers the reviewer concern that ATTR-AWARE may reduce collateral
damage by missing true dependencies.

## Priority 2: Graph Construction Variant Table

Needed variants:

- raw rule-based graph;
- stopword/pronoun/template-filtered graph;
- structured turn-level LongMemEval graph;
- typed-relation approximation if available.

Needed metrics:

- node/edge count;
- top hubs;
- BFS blast radius;
- ATTR-AWARE collateral;
- support-retrieval hit@K where retrieval is meaningful.

Why it matters:

This turns the artifact issue into a paper contribution: graph construction is a
first-class safety surface.

## Priority 3: Evidence Matrix for the Paper

Create one table that maps each experiment to the claim it supports:

- synthetic sweep: mechanism and false-positive/false-negative tradeoff;
- EventQA named hubs: real-data structural blast radius;
- LongMemEval clean gate: raw conversation artifacts;
- LongMemEval structured propagation: cross-family structural replication;
- LongMemEval support retrieval: retrieval-side harm without LLM generation;
- artificial hub injection: topology poisoning surface.

Why it matters:

The next manuscript needs to read as a coherent systems-safety study, not a pile
of post-rejection experiments.

## Priority 4: Rewrite Manuscript Skeleton

Recommended section order:

1. Problem and threat model: co-occurrence is not dependency.
2. Controlled mechanism study.
3. Real-data structural blast radius.
4. Graph construction as a safety boundary.
5. Retrieval-side support degradation.
6. Guardrail tradeoff and false-negative audit.
7. Limitations and deployment guidance.

## Do Not Spend Time On Yet

- full end-to-end LongMemEval QA claims before baseline retrieval is fixed;
- new LLM/VLM benchmark runs that do not target a reviewer objection;
- more raw hub experiments without clean graph-gate checks.
