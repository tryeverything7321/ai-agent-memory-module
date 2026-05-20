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
